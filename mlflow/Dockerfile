# Reason: Custom MLflow Dockerfile to install psycopg2 for PostgreSQL connectivity
# The base MLflow image doesn't include the PostgreSQL driver by default
FROM ghcr.io/mlflow/mlflow:latest

# Reason: Install PostgreSQL adapter (psycopg2-binary) for connecting to PostgreSQL backend
# Also install boto3 for S3/MinIO artifact storage support
RUN pip install --no-cache-dir psycopg2-binary boto3

# Reason: Set working directory for MLflow operations
WORKDIR /mlflow

# Reason: Use the default MLflow entrypoint from the base image
# CMD will be overridden by docker-compose command
