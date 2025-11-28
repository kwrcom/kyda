# KYDA MLOps Infrastructure

## Overview
Complete MLOps infrastructure stack for ML experiment tracking and workflow orchestration.

## Architecture

### Services
- **MLflow**: Experiment tracking and model registry
- **Airflow**: Workflow orchestration with CeleryExecutor
- **PostgreSQL**: Database for MLflow and Airflow metadata
- **MinIO**: S3-compatible artifact storage
- **Redis**: Message broker for Airflow Celery
- **Traefik**: Reverse proxy with domain routing

### Access Points
- **MLflow UI**: http://mlflow.kyda.tech (or http://localhost:5000)
- **Airflow UI**: http://airflow.kyda.tech (or http://localhost:8080)
- **Flower UI**: http://flower.kyda.tech (or http://localhost:5555)
- **MinIO Console**: http://localhost:9001
- **Traefik Dashboard**: http://localhost:8090/dashboard/

### Default Credentials
- **Airflow**: admin / admin
- **MinIO**: minioadmin / minioadmin

## Quick Start

### 1. Start All Services
```bash
docker-compose up -d
```

### 2. Check Service Status
```bash
docker-compose ps
```

### 3. View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f mlflow
docker-compose logs -f airflow-webserver
```

### 4. Stop Services
```bash
docker-compose down
```

### 5. Clean Up (including volumes)
```bash
docker-compose down -v
```

## Usage

### MLflow
1. Access MLflow UI at http://mlflow.kyda.tech
2. Create experiments via UI or API
3. Log parameters, metrics, and artifacts from your ML code

Example Python code:
```python
import mlflow

mlflow.set_tracking_uri("http://mlflow.kyda.tech")
mlflow.set_experiment("my-experiment")

with mlflow.start_run():
    mlflow.log_param("param1", 5)
    mlflow.log_metric("metric1", 0.85)
    mlflow.log_artifact("model.pkl")
```

### Airflow
1. Access Airflow UI at http://airflow.kyda.tech
2. Login with admin / admin
3. Create DAGs in `airflow/dags/` directory
4. DAGs are automatically detected and loaded

### Flower (Celery Monitoring)
1. Access Flower UI at http://flower.kyda.tech
2. Monitor worker status and task execution

## Network Configuration

### For Local Testing
Add to your `hosts` file (C:\Windows\System32\drivers\etc\hosts):
```
127.0.0.1 mlflow.kyda.tech
127.0.0.1 airflow.kyda.tech
127.0.0.1 flower.kyda.tech
```

### For Production
Configure DNS A records:
- mlflow.kyda.tech → your-server-ip
- airflow.kyda.tech → your-server-ip
- flower.kyda.tech → your-server-ip

## Troubleshooting

### Services not starting
```bash
# Check logs
docker-compose logs

# Restart specific service
docker-compose restart mlflow
```

### Database initialization issues
```bash
# Reinitialize Airflow DB
docker-compose exec airflow-webserver airflow db reset
```

### Port conflicts
Check if ports are already in use:
- 80 (Traefik)
- 5000 (MLflow)
- 8080 (Airflow)
- 5555 (Flower)
- 9000, 9001 (MinIO)

## Project Structure
```
kyda/
├── docker-compose.yml      # Main orchestration file
├── .env                    # Environment variables
├── airflow/
│   ├── dags/              # Airflow DAG definitions
│   ├── logs/              # Airflow execution logs
│   └── plugins/           # Custom Airflow plugins
└── README.md              # This file
```

## Security Notes
⚠️ **Change default passwords in production!**
- Update Airflow admin password after first login
- Change MinIO credentials in .env and docker-compose.yml
- Use strong Fernet key for Airflow secrets encryption
