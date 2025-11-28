"""
FastAPI Backend Application

Reason: Main application with JWT authentication, protected endpoints, and WebSocket support
"""

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from datetime import datetime
import time
import json
import os
import hvac
from kafka import KafkaProducer
import redis
from jsonschema import validate as jsonschema_validate, ValidationError

from utils.bloom import RedisBackedBloom
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from models import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    Transaction,
    TransactionListResponse,
    WebSocketMessage
)
from auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token
)

# Reason: Retrieve secrets from HashiCorp Vault with retry logic
# This ensures the backend waits for Vault to be ready before starting
def get_vault_secrets(max_retries=5, retry_delay=2):
    """
    Retrieve secrets from Vault with retry logic
    Supports both Token auth (Dev) and AppRole auth (Prod)
    """
    import time
    
    vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8200')
    # Auth methods
    vault_token = os.getenv('VAULT_TOKEN')
    vault_role_id = os.getenv('VAULT_ROLE_ID')
    vault_secret_id = os.getenv('VAULT_SECRET_ID')
    
    for attempt in range(max_retries):
        try:
            print(f"Attempting to connect to Vault at {vault_addr} (attempt {attempt + 1}/{max_retries})")
            client = hvac.Client(url=vault_addr)
            
            # Authentication Logic
            if vault_role_id and vault_secret_id:
                print("Authenticating via AppRole...")
                client.auth.approle.login(
                    role_id=vault_role_id,
                    secret_id=vault_secret_id
                )
            elif vault_token:
                print("Authenticating via Token...")
                client.token = vault_token
            else:
                # Try default token (e.g. root for dev) if nothing specified
                client.token = 'root'
            
            # Reason: Check if Vault is sealed/accessible
            if not client.is_authenticated():
                raise Exception("Vault authentication failed")
            
            # Reason: Retrieve backend secrets from KV v2 storage
            secret_response = client.secrets.kv.v2.read_secret_version(path='backend')
            secrets = secret_response['data']['data']
            
            print("Successfully retrieved secrets from Vault")
            return secrets
            
        except Exception as e:
            print(f"Failed to connect to Vault: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Max retries reached. Exiting...")
                raise Exception("Could not connect to Vault after multiple attempts")

# Reason: Get secrets from Vault at startup
secrets = get_vault_secrets()

# Reason: Extract individual secrets for use in the application
POSTGRES_USER = secrets.get('postgres_user', 'postgres')
POSTGRES_PASSWORD = secrets.get('postgres_password')
POSTGRES_DB = secrets.get('postgres_db', 'mlflow')
MINIO_ACCESS_KEY = secrets.get('minio_access_key')
MINIO_SECRET_KEY = secrets.get('minio_secret_key')
JWT_ALGORITHM = secrets.get('jwt_algorithm', 'RS256')

# Reason: Configuration constants (now using secrets from Vault)
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
# Reason: Construct PostgreSQL URL from Vault secrets instead of hardcoding
POSTGRES_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@postgres:5432/{POSTGRES_DB}"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


# Reason: Initialize FastAPI application with metadata
app = FastAPI(
    title="KYDA Fraud Detection API",
    description="Backend API for fraud detection system with JWT authentication",
    version="1.0.0"
)

# Reason: Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Reason: HTTP Bearer token security scheme
security = HTTPBearer()

# Reason: In-memory user database (replace with real database in production)
# Password is hashed using bcrypt
USERS_DB = {
    "admin": {
        "username": "admin",
        "hashed_password": get_password_hash("admin123"),
        "email": "admin@kyda.tech"
    }
}

# Reason: In-memory transaction storage (will be populated from Kafka)
transactions_db: List[Transaction] = []

# Reason: Active WebSocket connections for real-time notifications
active_connections: List[WebSocket] = []


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to validate JWT token and extract user info
    
    Reason: Protects endpoints by verifying access token
    """
    token = credentials.credentials
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username = payload.get("sub")
    if username not in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return USERS_DB[username]


@app.get("/")
async def root():
    """
    Root endpoint
    
    Reason: Health check and API information
    """
    return {
        "message": "KYDA Fraud Detection API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Login endpoint - issues JWT tokens
    
    Reason: Authenticates user and returns access + refresh tokens
    """
    # Reason: Verify user exists
    user = USERS_DB.get(request.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Reason: Verify password
    if not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Reason: Create tokens with username in payload
    access_token = create_access_token(data={"sub": user["username"]})
    refresh_token = create_refresh_token(data={"sub": user["username"]})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest):
    """
    Token refresh endpoint
    
    Reason: Issues new access token using valid refresh token
    """
    # Reason: Verify refresh token
    payload = verify_token(request.refresh_token, token_type="refresh")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    username = payload.get("sub")
    
    # Reason: Create new tokens
    access_token = create_access_token(data={"sub": username})
    refresh_token = create_refresh_token(data={"sub": username})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@app.get("/transactions/", response_model=TransactionListResponse)
async def get_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Get transactions (protected endpoint)
    
    Reason: Returns paginated transaction list, requires valid JWT
    """
    # Reason: Calculate pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    # Reason: Get paginated transactions
    paginated_transactions = transactions_db[start_idx:end_idx]
    
    return TransactionListResponse(
        transactions=paginated_transactions,
        total=len(transactions_db),
        page=page,
        page_size=page_size
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """
    WebSocket endpoint for real-time notifications
    
    Reason: Provides real-time fraud alerts and transaction updates
    Requires JWT token as query parameter
    """
    # Reason: Verify JWT token before accepting connection
    payload = verify_token(token, token_type="access")
    
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Reason: Accept WebSocket connection
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Reason: Send welcome message
        welcome_msg = WebSocketMessage(
            type="system",
            data={"message": "Connected to fraud detection system"},
            timestamp=datetime.utcnow()
        )
        await websocket.send_json(welcome_msg.dict())
        
        # Reason: Keep connection alive and listen for messages
        while True:
            data = await websocket.receive_text()
            # Echo back for now (can implement commands later)
            await websocket.send_text(f"Received: {data}")
            
    except WebSocketDisconnect:
        # Reason: Remove connection when client disconnects
        active_connections.remove(websocket)


async def broadcast_message(message: WebSocketMessage):
    """
    Broadcast message to all connected WebSocket clients
    
    Reason: Sends fraud alerts and updates to all connected clients
    """
    for connection in active_connections:
        try:
            await connection.send_json(message.dict())
        except Exception:
            # Reason: Remove dead connections
            active_connections.remove(connection)


# Basic JSON schema for transactions (pre-ingest)
transaction_json_schema = {
    "type": "object",
    "required": ["transaction_id", "user_id", "amount", "timestamp", "device_id"],
    "properties": {
        "transaction_id": {"type": "string"},
        "user_id": {"type": "string"},
        "device_id": {"type": "string"},
        "amount": {"type": "number", "minimum": 0},
        "merchant_category": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "location": {"type": "string"}
    },
    "additionalProperties": True
}


@app.post("/api/v1/transaction/validate")
async def validate_transaction(request: Request):
    """Pre-ingest validation endpoint (Level 0)

    Fast checks performed:
      - JSON schema validation using jsonschema
      - Bloom filter checks for user_id and device_id using Redis-backed Bloom
      - Logs an event to Kafka topic `gatekeeping.events` with the Level 0 verdict

    Designed to be extremely fast — do minimal work synchronously to keep latency low.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # JSON schema validation (fast pre-check)
    try:
        jsonschema_validate(instance=body, schema=transaction_json_schema)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"JSON schema validation failed: {e.message}")

    tx_id = body.get("transaction_id")
    user_id = body.get("user_id")
    device_id = body.get("device_id")

    # Bloom check: user_id OR device_id matches blacklist => quarantine
    bloom: RedisBackedBloom = app.state.bloom
    verdict = "Allow"
    reason = "passed"

    if user_id and bloom.contains(user_id):
        verdict = "Quarantine"
        reason = "user_id_blacklist"
    elif device_id and bloom.contains(device_id):
        verdict = "Quarantine"
        reason = "device_id_blacklist"

    event = {
        "level": 0,
        "transaction_id": tx_id,
        "user_id": user_id,
        "device_id": device_id,
        "verdict": verdict,
        "reason": reason,
        "payload": body,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    # Fire-and-forget produce to Kafka topic gatekeeping.events
    try:
        app.state.kafka_producer.send("gatekeeping.events", json.dumps(event).encode("utf-8"))
    except Exception:
        # de-prioritize producer failures to keep pre-ingest fast
        pass

    # Short-circuit: if quarantine, indicate that the transaction will be escalated
    # If quarantined at Level 0, also forward to Level 2 topic for heavy processing
    if verdict == "Quarantine":
        try:
            app.state.kafka_producer.send("transactions.level2", json.dumps(event).encode("utf-8"))
        except Exception:
            pass

    response = {"transaction_id": tx_id, "level": 0, "verdict": verdict, "reason": reason}

    return response


# Reason: Background task to simulate transaction processing
# In production, this would consume from Kafka
@app.on_event("startup")
async def startup_event():
    """
    Startup event handler
    
    Reason: Initialize application resources
    """
    print("Starting KYDA Fraud Detection API")
    print("Swagger UI available at: /docs")
    print("ReDoc available at: /redoc")
    # Initialize Redis and Kafka clients used for pre-ingest checks
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    # non-blocking producer
    app.state.kafka_producer = KafkaProducer(bootstrap_servers=kafka_servers.split(","), linger_ms=5)

    redis_url = os.getenv("REDIS_URL", "redis://airflow-redis:6379/0")
    app.state.redis = redis.from_url(redis_url)
    # Bloom used for blacklist checks (user_id/device_id)
    app.state.bloom = RedisBackedBloom(app.state.redis, key="bloom:blacklist", size_bits=2_000_000, num_hashes=5)

    # Connect to Postgres for manual reviews/feedback
    postgres_url = os.getenv("POSTGRES_URL", "postgresql://postgres:password@postgres:5432/mlflow")
    # create engine and ensure tables exist
    engine = None
    for _ in range(5):
        try:
            engine = create_engine(postgres_url, future=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except OperationalError:
            print("Postgres not ready, retrying")
            time.sleep(1)

    if engine is None:
        print("Warning: Could not connect to Postgres for manual reviews")
        app.state.db_engine = None
    else:
        app.state.db_engine = engine
        # create tables if necessary
        create_manual_reviews = """
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
        create_feedback = """
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
            conn.execute(text(create_manual_reviews))
            conn.execute(text(create_feedback))


@app.get("/manual_reviews/")
async def list_manual_reviews():
    """Return pending manual reviews queue"""
    engine = app.state.db_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, transaction_id, user_id, device_id, amount, detection_path, level1_score, level2_score, created_at FROM manual_reviews WHERE status='pending' ORDER BY created_at ASC"))
        rows = [dict(r._mapping) for r in res]

    return {"reviews": rows}


@app.post("/manual_reviews/{review_id}/judge")
async def judge_review(review_id: int, payload: dict):
    """Operator judges a manual review - store feedback and mark resolved"""
    engine = app.state.db_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    verdict = payload.get("verdict")
    operator_id = payload.get("operator_id")
    comment = payload.get("comment")

    if verdict not in ("Allow", "Block", "Escalate"):
        raise HTTPException(status_code=400, detail="Invalid verdict")

    # ensure review exists
    with engine.begin() as conn:
        r = conn.execute(text("SELECT transaction_id FROM manual_reviews WHERE id=:id"), {"id": review_id}).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="review not found")
        txid = r[0]

        # insert feedback
        conn.execute(text("INSERT INTO feedback_labels (review_id, transaction_id, operator_id, verdict, comment) VALUES (:rid, :tx, :op, :v, :c)"),
                     {"rid": review_id, "tx": txid, "op": operator_id, "v": verdict, "c": comment})

        # mark review resolved
        conn.execute(text("UPDATE manual_reviews SET status='resolved', updated_at=now() WHERE id=:id"), {"id": review_id})

    # Optionally send feedback to kafka for training
    try:
        app.state.kafka_producer.send("feedback.labels", json.dumps({"review_id": review_id, "transaction_id": txid, "operator_id": operator_id, "verdict": verdict, "comment": comment}).encode("utf-8"))
    except Exception:
        pass

    return {"status": "ok", "review_id": review_id}


@app.get("/alerts/")
async def list_alerts():
    """Return recent final decisions (alerts) with detection_level"""
    engine = app.state.db_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, transaction_id, final_verdict, reason, detection_path, created_at FROM final_decisions ORDER BY created_at DESC LIMIT 100"))
        rows = []
        for r in res:
            rec = dict(r._mapping)
            # detection_level detection
            path = rec.get('detection_path') or {}
            detection_level = 2 if path.get('level2') else 1 if path.get('level1') else 0
            rec['detection_level'] = detection_level
            rows.append(rec)

    return {"alerts": rows}


@app.get("/alerts/{transaction_id}")
async def alert_detail(transaction_id: str):
    engine = app.state.db_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, transaction_id, final_verdict, reason, detection_path, created_at FROM final_decisions WHERE transaction_id = :tx ORDER BY created_at DESC LIMIT 1"), {"tx": transaction_id}).fetchone()
        if not res:
            raise HTTPException(status_code=404, detail="alert not found")
        rec = dict(res._mapping)

    return rec


@app.on_event("shutdown")
async def shutdown_event():
    """
    Shutdown event handler
    
    Reason: Clean up resources on shutdown
    """
    # Reason: Close all WebSocket connections
    for connection in active_connections:
        await connection.close()
    
    print("KYDA Fraud Detection API shutdown complete")
    try:
        if hasattr(app.state, "kafka_producer"):
            app.state.kafka_producer.flush(timeout=3)
            app.state.kafka_producer.close()
    except Exception:
        pass
