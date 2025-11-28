"""Fast Scorer microservice

Loads a lightweight ONNX model (if provided) and reads "hot" features from Redis.
Provides /score endpoint which returns a score in [0,1] and a policy decision:
  score < 0.2 -> Allow
  score 0.2-0.6 -> Challenge
  score >= 0.6 -> Quarantine

If verdict==Quarantine, the service will forward the transaction to Kafka topic `transactions.level2`.
"""
from fastapi import FastAPI
from pydantic import BaseModel
import os
import redis
import json
from kafka import KafkaProducer

try:
    import onnxruntime as ort
except Exception:
    ort = None

app = FastAPI(title="Fast Scorer", version="0.1.0")

KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://airflow-redis:6379/0")
MODEL_PATH = os.getenv("ONNX_MODEL_PATH", "model.onnx")

redis_client = redis.from_url(REDIS_URL)
redis_client = redis.from_url(REDIS_URL)

# Retry logic for Kafka connection
import time
max_retries = 10
retry_delay = 5
producer = None

for attempt in range(max_retries):
    try:
        print(f"Connecting to Kafka (attempt {attempt + 1}/{max_retries})...")
        producer = KafkaProducer(bootstrap_servers=KAFKA_SERVERS.split(","), linger_ms=5)
        print("Successfully connected to Kafka")
        break
    except Exception as e:
        print(f"Failed to connect to Kafka: {e}")
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
        else:
            # Fallback: continue without Kafka (will just log errors on send) or raise
            print("WARNING: Could not connect to Kafka after multiple attempts. Running in degraded mode.")
            producer = None

# Load ONNX model if present
onnx_session = None
if ort and os.path.exists(MODEL_PATH):
    try:
        onnx_session = ort.InferenceSession(MODEL_PATH)
    except Exception:
        onnx_session = None


class Tx(BaseModel):
    transaction_id: str
    user_id: str
    device_id: str
    amount: float
    merchant_category: str | None = None
    timestamp: str | None = None
    location: str | None = None


def _fast_score_from_features(amount: float, tx_count_1min: int | None) -> float:
    """Fallback scoring logic when ONNX not present.

    Simple deterministic score normalized to [0,1] where higher is more suspicious.
    """
    count = tx_count_1min or 0
    # more transactions in 1 minute -> more suspicious
    score = min(1.0, (count / 10.0) + (0.5 if amount > 1000 else 0.0))
    return float(score)


def _compute_score(tx: Tx) -> float:
    # read features from Redis - hot features (stored by Spark jobs)
    # feature keys are namespaced by user_id/device_id
    try:
        tx_count_key = f"features:user:{tx.user_id}:tx_count_1min"
        raw = redis_client.get(tx_count_key)
        tx_count_1min = int(raw) if raw is not None else 0
    except Exception:
        tx_count_1min = 0

    # if ONNX model is loaded, form an input dict and run inference
    if onnx_session is not None:
        # Expect model input format like [amount, tx_count_1min]
        try:
            inp_name = onnx_session.get_inputs()[0].name
            import numpy as np
            arr = np.array([[tx.amount, tx_count_1min]], dtype=np.float32)
            out = onnx_session.run(None, {inp_name: arr})
            # model should return a score between 0 and 1
            score = float(out[0].tolist()[0][0])
            score = max(0.0, min(1.0, score))
            return score
        except Exception:
            # fallback
            return _fast_score_from_features(tx.amount, tx_count_1min)

    return _fast_score_from_features(tx.amount, tx_count_1min)


def policy_decision(score: float) -> str:
    if score < 0.2:
        return "Allow"
    if score < 0.6:
        return "Challenge"
    return "Quarantine"


@app.post("/score")
async def score(tx: Tx):
    # compute score quickly
    score_value = _compute_score(tx)
    verdict = policy_decision(score_value)

    # Always publish level1.action for downstream decision engine / auditing
    event = {
        "transaction_id": tx.transaction_id,
        "user_id": tx.user_id,
        "device_id": tx.device_id,
        "amount": tx.amount,
        "timestamp": tx.timestamp,
        "score": score_value,
        "verdict": verdict,
        "detection_level": 1
    }
    try:
        producer.send("level1.actions", json.dumps(event).encode("utf-8"))
        producer.flush(timeout=1)
    except Exception as e:
        print("fast-scorer: failed to send level1.actions", e)

    # If Quarantine -> forward to transactions.level2
    if verdict == "Quarantine":
        event = {
            "transaction_id": tx.transaction_id,
            "user_id": tx.user_id,
            "device_id": tx.device_id,
            "amount": tx.amount,
            "timestamp": tx.timestamp,
            "score": score_value,
            "verdict": verdict
        }
        try:
            producer.send("transactions.level2", json.dumps(event).encode("utf-8"))
            producer.flush(timeout=1)
        except Exception as e:
            print("fast-scorer: failed to send transactions.level2", e)

    return {"transaction_id": tx.transaction_id, "score": score_value, "verdict": verdict}


@app.on_event("shutdown")
def shutdown():
    try:
        producer.flush(timeout=3)
        producer.close()
    except Exception:
        pass
