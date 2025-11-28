#!/usr/bin/env python3
"""
Vault Helper for Airflow Services

Reason: This module provides functions to retrieve secrets from HashiCorp Vault
and export them as environment variables for Airflow services to use.
"""

import os
import sys
import time
import hvac


def get_vault_secrets(secret_path='airflow', max_retries=5, retry_delay=2):
    """
    Retrieve secrets from Vault with retry logic
    
    Args:
        secret_path: Path to secrets in Vault (default: 'airflow')
        max_retries: Maximum number of connection attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        dict: Dictionary containing secrets from Vault
    
    Reason: Vault might not be immediately available during startup,
    so we retry the connection to ensure secrets are retrieved successfully
    """
    vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8200')
    vault_token = os.getenv('VAULT_TOKEN', 'root')
    
    for attempt in range(max_retries):
        try:
            print(f"[Vault Helper] Attempting to connect to Vault at {vault_addr} (attempt {attempt + 1}/{max_retries})")
            client = hvac.Client(url=vault_addr, token=vault_token)
            
            # Reason: Check if Vault is sealed/accessible
            if not client.is_authenticated():
                raise Exception("Vault authentication failed")
            
            # Reason: Retrieve secrets from KV v2 storage
            secret_response = client.secrets.kv.v2.read_secret_version(path=secret_path)
            secrets = secret_response['data']['data']
            
            print(f"[Vault Helper] Successfully retrieved secrets from Vault path: {secret_path}")
            return secrets
            
        except Exception as e:
            print(f"[Vault Helper] Failed to connect to Vault: {e}")
            if attempt < max_retries - 1:
                print(f"[Vault Helper] Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("[Vault Helper] Max retries reached. Exiting...")
                sys.exit(1)


def export_airflow_secrets():
    """
    Retrieve Airflow secrets from Vault and export as environment variables
    
    Reason: Airflow services need these environment variables to connect to
    PostgreSQL, Redis, and other services with proper credentials
    """
    secrets = get_vault_secrets('airflow')
    
    # Reason: Extract and export database credentials
    postgres_user = secrets.get('postgres_user', 'airflow')
    postgres_password = secrets.get('postgres_password')
    postgres_db = secrets.get('postgres_db', 'airflow')
    
    # Reason: Export Airflow configuration
    os.environ['AIRFLOW__DATABASE__SQL_ALCHEMY_CONN'] = \
        f"postgresql+psycopg2://{postgres_user}:{postgres_password}@airflow-postgres:5432/{postgres_db}"
    os.environ['AIRFLOW__CELERY__RESULT_BACKEND'] = \
        f"db+postgresql://{postgres_user}:{postgres_password}@airflow-postgres:5432/{postgres_db}"
    
    # Reason: Export Fernet key for encryption
    fernet_key = secrets.get('fernet_key')
    if fernet_key:
        os.environ['AIRFLOW__CORE__FERNET_KEY'] = fernet_key
    
    # Reason: Export webserver secret key
    webserver_secret = secrets.get('webserver_secret_key')
    if webserver_secret:
        os.environ['AIRFLOW__WEBSERVER__SECRET_KEY'] = webserver_secret
    
    # Reason: Export MinIO credentials for artifact storage
    minio_access_key = secrets.get('minio_access_key')
    minio_secret_key = secrets.get('minio_secret_key')
    if minio_access_key:
        os.environ['AWS_ACCESS_KEY_ID'] = minio_access_key
    if minio_secret_key:
        os.environ['AWS_SECRET_ACCESS_KEY'] = minio_secret_key
    
    print("[Vault Helper] Successfully exported Airflow secrets as environment variables")
    print(f"[Vault Helper] Database connection: postgresql+psycopg2://{postgres_user}:***@airflow-postgres:5432/{postgres_db}")


if __name__ == '__main__':
    # Reason: When run as a script, export secrets and print confirmation
    export_airflow_secrets()
    print("[Vault Helper] Airflow secrets loaded successfully")
