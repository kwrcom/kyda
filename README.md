# KYDA - Advanced Fraud Detection System

![Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-orange)
![Vault](https://img.shields.io/badge/Vault-Secured-green)

KYDA is a comprehensive, real-time fraud detection system built with a modern microservices architecture. It leverages machine learning, stream processing, and secure infrastructure to detect and prevent fraudulent transactions.

## 🚀 Key Features

- **Real-time Fraud Detection**: Low-latency scoring of transactions using ML models.
- **Stream Processing**: Apache Spark & Kafka for high-throughput data processing.
- **Machine Learning Ops**: MLflow for experiment tracking and model registry.
- **Workflow Orchestration**: Apache Airflow for managing ML pipelines.
- **Secure Infrastructure**: HashiCorp Vault for centralized secrets management.
- **Interactive Dashboard**: React/Next.js frontend for monitoring and manual reviews.
- **Comprehensive Testing**: Integrated suites for load, security, and end-to-end testing.

## 🏗️ Architecture

### Core Services
- **Backend API**: FastAPI service for transaction ingestion and management.
- **Frontend**: Next.js application for the fraud dashboard.
- **Decision Engine**: Rule-based and ML-based decision making.
- **Spark Streaming**: Real-time feature engineering and processing.
- **Kafka**: Message broker for event-driven architecture.

### Infrastructure
- **HashiCorp Vault**: Secrets management (KV v2).
- **PostgreSQL**: Primary database for metadata and application data.
- **MinIO**: S3-compatible object storage for artifacts.
- **Redis**: Caching and message broker for Celery.
- **Traefik**: Reverse proxy and load balancer.

### MLOps
- **MLflow**: Model tracking and registry.
- **Airflow**: DAG orchestration for model training and maintenance.

## 🛠️ Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.9+ (for running scripts)

### Automated Setup (Recommended)

We provide an automated script to set up the entire environment, including Vault initialization.

```bash
# Windows
scripts\setup_vault.bat
```

### Manual Setup

1. **Start Services**
   ```bash
   docker-compose up -d
   ```

2. **Wait for Initialization**
   Wait about 30-60 seconds for all services to start and Vault to initialize.

3. **Verify Installation**
   ```bash
   pip install -r services/backend/requirements.txt
   python scripts/vault_health_check.py
   ```

## 🔒 Security & Vault Integration

All sensitive credentials (database passwords, API keys) are stored in **HashiCorp Vault**.

- **Vault UI**: http://localhost:8200 (Token: `root`)
- **Documentation**: [Vault Integration Guide](docs/VAULT_INTEGRATION.md)

To verify secrets are working:
```bash
python scripts/test_vault_integration.py
```

## 🧪 Testing

The project includes a comprehensive testing suite located in `tests/`.

### 1. Integration Testing
Tests the full pipeline: Auth -> Transaction -> Processing -> Review.
```bash
python tests/integration_test.py
```

### 2. Load Testing
Simulates high-concurrency transaction traffic.
```bash
python tests/load_test.py --threads 10 --transactions 100
```

### 3. Security Audit
Checks for vulnerabilities (SQLi, XSS, JWT issues, etc.).
```bash
python tests/security_audit.py
```

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

- [**Vault Architecture**](docs/VAULT_ARCHITECTURE.md): System diagrams and secret flow.
- [**Deployment Guide**](docs/VAULT_DEPLOYMENT.md): Step-by-step deployment instructions.
- [**Implementation Summary**](docs/VAULT_IMPLEMENTATION_SUMMARY.md): Status of the Vault integration.
- [**API Documentation**](http://localhost:8000/docs): Swagger UI for the Backend API.

## 🖥️ Access Points

| Service | URL | Credentials (Default) |
|---------|-----|----------------------|
| **Backend API** | http://localhost:8000 | - |
| **Swagger UI** | http://localhost:8000/docs | - |
| **Frontend** | http://localhost:5173 | - |
| **Vault UI** | http://localhost:8200 | Token: `root` |
| **Airflow** | http://localhost:8080 | `admin` / `admin` |
| **MLflow** | http://localhost:5000 | - |
| **MinIO** | http://localhost:9001 | `minioadmin` / `minioadmin` |
| **Traefik** | http://localhost:8090 | - |

## 📂 Project Structure

```
kyda/
├── airflow/                # Airflow DAGs and configuration
├── docs/                   # Project documentation
├── mlflow/                 # MLflow configuration
├── scripts/                # Utility and setup scripts
│   ├── setup_vault.bat     # Automated setup script
│   └── ...
├── services/               # Microservices source code
│   ├── backend/            # FastAPI backend
│   ├── frontend/           # Next.js frontend
│   ├── producer/           # Transaction generator
│   └── ...
├── tests/                  # Test suites
│   ├── integration_test.py
│   ├── load_test.py
│   └── security_audit.py
├── docker-compose.yml      # Main orchestration file
└── README.md               # This file
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## ⚠️ Security Note

This project is configured for **Development Mode**.
- Vault uses a root token and in-memory storage.
- SSL/TLS is not enabled by default.
- Default passwords are used for infrastructure services.

**DO NOT DEPLOY TO PRODUCTION WITHOUT HARDENING.**
Refer to `docs/VAULT_INTEGRATION.md` for production security guidelines.
