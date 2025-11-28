"""
Decision Engine service
- consumes level1.actions and level2.verdicts
- applies business rules to produce final decision: Allow | Block | Escalate
- writes manual review rows for Escalate into PostgreSQL table manual_reviews
- writes feedback_labels when operator decisions are received via backend
- publishes final decisions to topic final.decisions
"""
import os
import time
import json
from kafka import KafkaConsumer, KafkaProducer
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from datetime import datetime

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:password@postgres:5432/mlflow")

# Topics
TOPIC_L1 = os.getenv("KAFKA_TOPIC_L1", "level1.actions")
TOPIC_L2 = os.getenv("KAFKA_TOPIC_L2", "level2.verdicts")
TOPIC_FINAL = os.getenv("KAFKA_TOPIC_FINAL", "final.decisions")

# Connect to Postgres
engine = None
for _ in range(10):
    try:
        engine = create_engine(POSTGRES_URL, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        break
    except OperationalError:
        print("Postgres not ready, retrying...")
        time.sleep(2)

if engine is None:
    raise RuntimeError("Could not connect to Postgres DB")

# Ensure tables exist
create_manual_reviews_sql = """
CREATE TABLE IF NOT EXISTS manual_reviews (
    id SERIAL PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    user_id TEXT,
    device_id TEXT,
    amount DOUBLE PRECISION,
    detection_path JSONB,
    level1_score DOUBLE PRECISION,
    level2_score DOUBLE PRECISION,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
"""

create_feedback_sql = """
CREATE TABLE IF NOT EXISTS feedback_labels (
    id SERIAL PRIMARY KEY,
    review_id INTEGER REFERENCES manual_reviews(id) ON DELETE SET NULL,
    transaction_id TEXT,
    operator_id TEXT,
    verdict TEXT,
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
"""

with engine.begin() as conn:
    conn.execute(text(create_manual_reviews_sql))
    conn.execute(text(create_feedback_sql))

create_final_sql = """
CREATE TABLE IF NOT EXISTS final_decisions (
    id SERIAL PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    final_verdict TEXT,
    reason TEXT,
    detection_path JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
"""

with engine.begin() as conn:
    conn.execute(text(create_final_sql))

# Simple in-memory store of partial messages
store = {}

# Retry logic for Kafka connection
max_retries = 10
retry_delay = 5

producer = None
consumer = None

for attempt in range(max_retries):
    try:
        print(f"Connecting to Kafka (attempt {attempt + 1}/{max_retries})...")
        producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP.split(","), linger_ms=5)
        
        import uuid
        # use a unique group id per run so we read from earliest for testing/dev
        group = f"decision-engine-{uuid.uuid4().hex[:8]}"
        print("Starting kafka consumer with group:", group)
        consumer = KafkaConsumer(TOPIC_L1, TOPIC_L2, bootstrap_servers=KAFKA_BOOTSTRAP.split(","),
                                 auto_offset_reset='earliest', enable_auto_commit=True, group_id=group)
        print("Successfully connected to Kafka")
        break
    except Exception as e:
        print(f"Failed to connect to Kafka: {e}")
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
        else:
            raise RuntimeError("Could not connect to Kafka after multiple attempts")

print("Decision Engine started. Subscribed to:", TOPIC_L1, TOPIC_L2)


def apply_business_rules(l1: dict | None, l2: dict | None) -> dict:
    """Return a final decision dict with keys: final_verdict, reason"""
    # simple rules:
    # - If L2 exists:
    #     - if l2.verdict == 'Quarantine' -> Block
    #     - if l2.verdict == 'Challenge' -> Escalate
    #     - if l2.verdict == 'Allow' -> Allow
    # - Otherwise, rely on L1:
    #     - Allow -> Allow
    #     - Challenge -> Escalate
    #     - Quarantine -> Escalate (send to Level2 — but here escalate for manual review)

    if l2:
        v = l2.get('verdict')
        if v == 'Quarantine':
            return {'final_verdict': 'Block', 'reason': 'level2_quarantine'}
        if v == 'Challenge':
            return {'final_verdict': 'Escalate', 'reason': 'level2_challenge'}
        return {'final_verdict': 'Allow', 'reason': 'level2_allow'}

    if l1:
        v = l1.get('verdict')
        if v == 'Allow':
            return {'final_verdict': 'Allow', 'reason': 'level1_allow'}
        if v == 'Challenge':
            return {'final_verdict': 'Escalate', 'reason': 'level1_challenge'}
        # Quarantine at L1 -> escalate to manual review pending level2
        return {'final_verdict': 'Escalate', 'reason': 'level1_quarantine'}

    # default
    return {'final_verdict': 'Allow', 'reason': 'no_info'}


def store_manual_review(tx, l1, l2, decision):
    detection_path = {
        'level1': l1,
        'level2': l2
    }
    with engine.begin() as conn:
        res = conn.execute(text(
            "INSERT INTO manual_reviews (transaction_id, user_id, device_id, amount, detection_path, level1_score, level2_score, status) "
            "VALUES (:tx, :user, :device, :amt, :path, :l1s, :l2s, 'pending') RETURNING id"
        ), {
            'tx': tx.get('transaction_id'),
            'user': tx.get('user_id'),
            'device': tx.get('device_id'),
            'amt': tx.get('amount'),
            'path': json.dumps(detection_path),
            'l1s': (l1 or {}).get('score'),
            'l2s': (l2 or {}).get('heavy_score_clamped') or (l2 or {}).get('score')
        })
        idrow = res.fetchone()
        if idrow:
            return idrow[0]
    return None


def process_combined(txid):
    entry = store.get(txid)
    if not entry:
        return
    l1 = entry.get('l1')
    l2 = entry.get('l2')
    # Apply rules
    dec = apply_business_rules(l1, l2)
    final = {
        'transaction_id': txid,
        'final_verdict': dec['final_verdict'],
        'reason': dec['reason'],
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'level1': l1,
        'level2': l2
    }

    # If decision requires manual review (Escalate) -> create DB record
    if dec['final_verdict'] == 'Escalate':
        # store manual review if not yet stored
        if not entry.get('manual_id'):
            tx = l1 or l2 or {}
            m_id = store_manual_review(tx, l1, l2, dec)
            entry['manual_id'] = m_id

    # publish final decision
    try:
        producer.send(TOPIC_FINAL, json.dumps(final).encode('utf-8'))
    except Exception:
        pass

    # persist final decision for UI / auditing
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO final_decisions (transaction_id, final_verdict, reason, detection_path) VALUES (:tx, :v, :r, :p)"
            ), {"tx": txid, "v": final['final_verdict'], "r": final['reason'], "p": json.dumps({'level1': l1, 'level2': l2})})
    except Exception as e:
        print('failed to persist final decision', e)

    # cleanup state for tx (optional): keep manual_id if present
    if entry.get('manual_id'):
        store[txid] = {'manual_id': entry['manual_id']}
    else:
        store.pop(txid, None)


# Kafka consumer loop
try:
    for msg in consumer:
        try:
            v = json.loads(msg.value.decode('utf-8'))
        except Exception:
            continue
        topic = msg.topic
        txid = v.get('transaction_id')
        if not txid:
            continue
        if txid not in store:
            store[txid] = {}
        if topic == TOPIC_L1:
            store[txid]['l1'] = v
            print(f"DecisionEngine: Received L1 for {txid} verdict={v.get('verdict')} score={v.get('score')}")
        elif topic == TOPIC_L2:
            store[txid]['l2'] = v
            print(f"DecisionEngine: Received L2 for {txid} verdict={v.get('verdict')} score={v.get('heavy_score_clamped') or v.get('score')}")

        # If we have enough info, process
        process_combined(txid)

except KeyboardInterrupt:
    print('shutting down')
finally:
    try:
        producer.flush()
        producer.close()
    except Exception:
        pass
    consumer.close()
