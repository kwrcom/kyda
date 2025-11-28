# HashiCorp Vault Integration Guide

## Overview

This document describes the HashiCorp Vault integration for secure secrets management in the KYDA fraud detection system. All sensitive credentials (PostgreSQL passwords, MinIO access keys, JWT secrets, etc.) are stored in Vault instead of being hardcoded in configuration files.

## Architecture

### Vault Deployment

- **Mode**: Development mode (in-memory storage)
- **Port**: 8200
- **Root Token**: `root` (for development only)
- **Storage Backend**: In-memory (not for production!)

⚠️ **Warning**: The current configuration uses Vault in dev mode, which is **NOT suitable for production**. For production deployments:
- Use a persistent storage backend (Consul, etcd, or filesystem)
- Enable TLS/SSL
- Use proper authentication methods (AppRole, Kubernetes auth, etc.)
- Implement auto-unsealing
- Enable audit logging

### Secrets Organization

Secrets are stored in KV v2 (Key-Value version 2) secrets engine at path `secret/`:

```
secret/
├── backend/           # Backend service secrets
│   ├── postgres_user
│   ├── postgres_password
│   ├── postgres_db
│   ├── minio_access_key
│   ├── minio_secret_key
│   └── jwt_algorithm
│
└── airflow/          # Airflow service secrets
    ├── postgres_user
    ├── postgres_password
    ├── postgres_db
    ├── fernet_key
    ├── webserver_secret_key
    ├── minio_access_key
    └── minio_secret_key
```

### Access Policies

Two policies are configured to control access:

1. **backend-policy**: Grants read access to `secret/data/backend`
2. **airflow-policy**: Grants read access to `secret/data/airflow`

## Service Integration

### Backend Service

**File**: `services/backend/main.py`

The backend retrieves secrets at startup using the `get_vault_secrets()` function:

```python
def get_vault_secrets(max_retries=5, retry_delay=2):
    """
    Retrieve secrets from Vault with retry logic
    Vault might not be immediately available during startup
    """
    vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8200')
    vault_token = os.getenv('VAULT_TOKEN', 'root')
    
    client = hvac.Client(url=vault_addr, token=vault_token)
    secret_response = client.secrets.kv.v2.read_secret_version(path='backend')
    return secret_response['data']['data']
```

**Environment Variables**:
- `VAULT_ADDR`: Vault server address (default: `http://vault:8200`)
- `VAULT_TOKEN`: Vault authentication token (default: `root`)

**Dependencies**:
- `hvac==1.1.1` (HashiCorp Vault client)

### Airflow Services

**File**: `airflow/dags/vault_helper.py`

Airflow DAGs use a centralized `vault_helper` module that provides:
- Connection pooling (singleton pattern)
- Retry logic with exponential backoff
- Secret caching to reduce API calls
- Consistent error handling

**Usage in DAGs**:

```python
from vault_helper import get_airflow_secrets

# Get all Airflow secrets
secrets = get_airflow_secrets()

POSTGRES_PASSWORD = secrets['postgres_password']
MINIO_ACCESS_KEY = secrets['minio_access_key']
MINIO_SECRET_KEY = secrets['minio_secret_key']
```

**Environment Variables**:
- `VAULT_ADDR`: Vault server address
- `VAULT_TOKEN`: Vault authentication token

## Docker Compose Configuration

### Vault Service

```yaml
vault:
  image: hashicorp/vault:latest
  container_name: vault
  ports:
    - "8200:8200"
  environment:
    VAULT_DEV_ROOT_TOKEN_ID: root
    VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
  cap_add:
    - IPC_LOCK
  command: server -dev -dev-root-token-id=root
  healthcheck:
    test: ["CMD", "vault", "status"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### Vault Initialization Service

The `vault-init` service runs once at startup to:
1. Enable KV v2 secrets engine
2. Store all secrets
3. Create access policies

```yaml
vault-init:
  image: hashicorp/vault:latest
  depends_on:
    vault:
      condition: service_healthy
  entrypoint: >
    /bin/sh -c "
      export VAULT_ADDR=http://vault:8200 &&
      export VAULT_TOKEN=root &&
      vault secrets enable -path=secret kv-v2 || true &&
      vault kv put secret/backend ... &&
      vault kv put secret/airflow ... &&
      vault policy write backend-policy - <<< '...' &&
      vault policy write airflow-policy - <<< '...' &&
      echo 'Vault initialization completed!'
    "
```

### Service Dependencies

Services that need secrets depend on `vault-init`:

```yaml
backend:
  depends_on:
    vault-init:
      condition: service_completed_successfully
```

## Secrets Removed

The following secrets have been **removed** from configuration files:

### From docker-compose.yml:
- ✅ PostgreSQL credentials (both MLflow and Airflow databases)
- ✅ MinIO access keys and secrets
- ✅ Airflow Fernet key
- ✅ Airflow webserver secret key
- ✅ JWT algorithm configuration

### From .env files:
- ✅ All `.env` files are in `.gitignore`
- ✅ Database passwords
- ✅ API keys and tokens

## Verification

### Health Check Script

Run the Vault health check to verify the installation:

```bash
# Install hvac if not already installed
pip install hvac

# Run health check
python scripts/vault_health_check.py
```

Expected output:
```
Connecting to Vault at http://localhost:8200...
✅ Vault is accessible and authenticated

Checking backend secrets...
  ✅ postgres_user: pos***
  ✅ postgres_password: pas***
  ✅ postgres_db: mlf***
  ✅ minio_access_key: min***
  ✅ minio_secret_key: min***
  ✅ jwt_algorithm: RS2***

Checking Airflow secrets...
  ✅ postgres_user: air***
  ✅ postgres_password: air***
  ✅ postgres_db: air***
  ✅ fernet_key: ZmD***
  ✅ webserver_secret_key: air***
  ✅ minio_access_key: min***
  ✅ minio_secret_key: min***

Checking Vault policies...
  ✅ backend-policy exists
  ✅ airflow-policy exists

✅ All Vault health checks passed!
```

### Manual Verification

1. **Access Vault UI**: Navigate to `http://localhost:8200` and log in with token `root`

2. **List secrets via CLI**:
```bash
docker exec vault vault kv get secret/backend
docker exec vault vault kv get secret/airflow
```

3. **Check policies**:
```bash
docker exec vault vault policy read backend-policy
docker exec vault vault policy read airflow-policy
```

## Troubleshooting

### Issue: Services fail to start with "Could not connect to Vault"

**Cause**: Vault service is not ready yet

**Solution**: 
- Ensure `vault` service has a health check
- Services should depend on `vault-init` with `condition: service_completed_successfully`
- Implement retry logic in service startup (already implemented in `get_vault_secrets()`)

### Issue: "Authentication failed"

**Cause**: Incorrect `VAULT_TOKEN` environment variable

**Solution**:
- Verify `VAULT_TOKEN=root` is set in service environment
- Check vault logs: `docker logs vault`

### Issue: "Secret not found"

**Cause**: Secrets not initialized or wrong path

**Solution**:
- Check `vault-init` logs: `docker logs vault-init`
- Manually verify secrets: `docker exec vault vault kv get secret/backend`

### Issue: "Permission denied"

**Cause**: Incorrect policy configuration

**Solution**:
- Verify policies exist: `docker exec vault vault policy list`
- Check policy contents: `docker exec vault vault policy read backend-policy`

## Production Considerations

For production deployment, implement the following changes:

### 1. Use Persistent Storage

```hcl
storage "consul" {
  address = "consul:8500"
  path    = "vault/"
}
```

Or use filesystem storage:

```hcl
storage "file" {
  path = "/vault/data"
}
```

### 2. Enable TLS

```hcl
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_cert_file = "/vault/certs/vault.crt"
  tls_key_file  = "/vault/certs/vault.key"
}
```

### 3. Use AppRole Authentication

Instead of root token, use AppRole for service authentication:

```bash
# Enable AppRole
vault auth enable approle

# Create policy
vault policy write backend-policy backend-policy.hcl

# Create AppRole
vault write auth/approle/role/backend \
  secret_id_ttl=24h \
  token_ttl=1h \
  token_max_ttl=4h \
  policies="backend-policy"

# Get role_id and secret_id
vault read auth/approle/role/backend/role-id
vault write -f auth/approle/role/backend/secret-id
```

Update services to login with AppRole:

```python
client = hvac.Client(url=vault_addr)
client.auth.approle.login(
    role_id=os.getenv('VAULT_ROLE_ID'),
    secret_id=os.getenv('VAULT_SECRET_ID')
)
```

### 4. Enable Auto-Unseal

Use cloud KMS for auto-unsealing:

```hcl
seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "your-kms-key-id"
}
```

### 5. Enable Audit Logging

```bash
vault audit enable file file_path=/vault/logs/audit.log
```

### 6. Rotate Secrets Regularly

Implement secret rotation:
- Database passwords: Every 90 days
- API keys: Every 30 days
- JWT keys: Every 7 days

## Security Best Practices

1. ✅ **Never commit secrets to version control**
2. ✅ **Use specific policies** - Grant minimum required permissions
3. ✅ **Enable audit logging** - Track all secret access
4. ✅ **Rotate secrets regularly** - Implement automated rotation
5. ✅ **Use namespaces** - Isolate secrets for different environments
6. ✅ **Encrypt transit** - Always use TLS in production
7. ✅ **Monitor access** - Set up alerting for suspicious activity
8. ✅ **Backup Vault data** - Regular snapshots of storage backend

## References

- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [Vault Python Client (hvac)](https://hvac.readthedocs.io/)
- [Vault Production Hardening](https://learn.hashicorp.com/tutorials/vault/production-hardening)
- [Vault Best Practices](https://learn.hashicorp.com/tutorials/vault/pattern-approle)

## Support

For issues or questions:
1. Check service logs: `docker logs <service-name>`
2. Check Vault logs: `docker logs vault`
3. Run health check: `python scripts/vault_health_check.py`
4. Review this documentation
