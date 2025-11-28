#!/bin/bash
# Airflow Entrypoint with Vault Integration
#
# Reason: This script fetches secrets from Vault before starting Airflow services
# It ensures that all environment variables are properly set from Vault secrets

set -e

echo "[Entrypoint] Starting Airflow with Vault integration..."

# Reason: Install hvac library if not present (for Vault client)
pip install --quiet hvac 2>/dev/null || true

# Reason: Load secrets from Vault using the helper script
if [ -f "/opt/airflow/vault_helper.py" ]; then
    echo "[Entrypoint] Loading secrets from Vault..."
    python3 /opt/airflow/vault_helper.py
    
    # Reason: Source the environment variables exported by vault_helper
    # We need to re-export them in the current shell
    export $(python3 -c "
import sys
sys.path.insert(0, '/opt/airflow')
from vault_helper import get_vault_secrets

secrets = get_vault_secrets('airflow')
postgres_user = secrets.get('postgres_user', 'airflow')
postgres_password = secrets.get('postgres_password')
postgres_db = secrets.get('postgres_db', 'airflow')

print(f'AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://{postgres_user}:{postgres_password}@airflow-postgres:5432/{postgres_db}')
print(f'AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://{postgres_user}:{postgres_password}@airflow-postgres:5432/{postgres_db}')
print(f'AIRFLOW__CORE__FERNET_KEY={secrets.get(\"fernet_key\")}')
print(f'AIRFLOW__WEBSERVER__SECRET_KEY={secrets.get(\"webserver_secret_key\")}')
print(f'AWS_ACCESS_KEY_ID={secrets.get(\"minio_access_key\")}')
print(f'AWS_SECRET_ACCESS_KEY={secrets.get(\"minio_secret_key\")}')
" | xargs)
    
    echo "[Entrypoint] Secrets loaded successfully from Vault"
else
    echo "[Entrypoint] Warning: vault_helper.py not found, using environment variables"
fi

# Reason: Execute the original Airflow command passed as arguments
echo "[Entrypoint] Executing: $@"
exec "$@"
