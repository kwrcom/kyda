# Vault Deployment and Verification Guide

## Quick Start

Follow these steps to deploy and verify the HashiCorp Vault integration:

### Step 1: Start the Services

```bash
# Start all services including Vault
docker-compose up -d

# Wait for services to be healthy (about 30 seconds)
docker-compose ps
```

### Step 2: Verify Vault Health

```bash
# Install Python dependencies
pip install hvac

# Run the health check script
python scripts/vault_health_check.py
```

Expected output:
```
✅ Vault is accessible and authenticated
✅ All backend secrets present
✅ All Airflow secrets present
✅ All policies exist
✅ All Vault health checks passed!
```

### Step 3: Run Integration Tests

```bash
# Run comprehensive integration tests
python scripts/test_vault_integration.py
```

Expected output:
```
🚀 Vault Integration Test Suite
✅ PASS - KV Engine
✅ PASS - Backend Secrets
✅ PASS - Airflow Secrets
✅ PASS - Policies
✅ PASS - Secret Versioning
✅ PASS - Policy Enforcement
✅ PASS - Connection Resilience

Total: 7/7 tests passed
🎉 All tests passed! Vault integration is working correctly.
```

### Step 4: Verify Services Are Running

```bash
# Check that backend can access secrets
docker logs backend 2>&1 | grep "Successfully retrieved secrets"

# Check that Airflow webserver is running
docker logs airflow-webserver 2>&1 | grep "Airflow secrets loaded"

# Verify no hardcoded secrets in environment
docker inspect backend | grep -i "postgres_password"
# Should return empty (secret not in environment)
```

## Manual Verification

### Access Vault UI

1. Open browser to `http://localhost:8200`
2. Login with method: **Token**
3. Token: `root`

### Browse Secrets via UI

1. Navigate to **Secrets** → **secret/**
2. Click on **backend/** to view backend secrets
3. Click on **airflow/** to view Airflow secrets

### Use Vault CLI

```bash
# Access Vault container
docker exec -it vault sh

# Set environment variables
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'

# List secrets
vault kv list secret/

# Read backend secrets
vault kv get secret/backend

# Read Airflow secrets  
vault kv get secret/airflow

# View policies
vault policy list
vault policy read backend-policy
vault policy read airflow-policy
```

## Troubleshooting

### Services won't start

**Check Vault initialization:**
```bash
docker logs vault-init
```

If you see errors, Vault may not have initialized properly. Try:
```bash
docker-compose down
docker-compose up -d vault
# Wait 10 seconds
docker-compose up -d vault-init
docker-compose up -d
```

### Backend can't connect to Vault

**Check logs:**
```bash
docker logs backend
```

Look for connection errors. Verify:
- Vault service is running: `docker ps | grep vault`
- Environment variables are set: `docker exec backend env | grep VAULT`

**Restart backend:**
```bash
docker-compose restart backend
```

### Airflow DAGs fail

**Check DAG logs:**
```bash
docker logs airflow-webserver
docker logs airflow-scheduler
```

**Verify vault_helper.py is accessible:**
```bash
docker exec airflow-webserver ls -la /opt/airflow/dags/vault_helper.py
```

**Try manually loading secrets:**
```bash
docker exec airflow-webserver python3 -c "
from vault_helper import get_airflow_secrets
secrets = get_airflow_secrets()
print(list(secrets.keys()))
"
```

### Vault shows as unhealthy

**Check Vault status:**
```bash
docker exec vault vault status
```

If sealed, initialize and unseal (dev mode should auto-unseal):
```bash
docker-compose restart vault
```

## Testing Secret Rotation

### Rotate a Secret

```bash
# Update backend postgres password
docker exec vault vault kv put secret/backend \
  postgres_user=postgres \
  postgres_password=new_password_123 \
  postgres_db=mlflow \
  minio_access_key=minioadmin \
  minio_secret_key=minioadmin \
  jwt_algorithm=RS256

# Restart backend to pick up new secret
docker-compose restart backend

# Verify new secret is being used
docker logs backend 2>&1 | grep "Successfully retrieved secrets"
```

## Cleanup

### Remove all secrets

```bash
docker exec vault vault kv delete secret/backend
docker exec vault vault kv delete secret/airflow
```

### Destroy secret metadata (including versions)

```bash
docker exec vault vault kv metadata delete secret/backend
docker exec vault vault kv metadata delete secret/airflow
```

### Remove Vault data and restart fresh

```bash
docker-compose down
docker volume rm kyda_vault-data
docker-compose up -d
```

## Next Steps

### For Development
- ✅ Vault is configured in dev mode
- ✅ All secrets are centralized
- ✅ Services retrieve secrets at startup

### For Production (Required Changes)

1. **Switch to Production Mode**
   - Use persistent storage backend (Consul, etcd, or filesystem)
   - Enable TLS/SSL
   - Use strong authentication (AppRole, Kubernetes auth)
   - See `docs/VAULT_INTEGRATION.md` for details

2. **Security Hardening**
   - Rotate the root token
   - Enable audit logging
   - Implement secret rotation policies
   - Use least-privilege access policies

3. **High Availability**
   - Deploy Vault cluster (3+ nodes)
   - Use distributed storage backend
   - Configure load balancer

4. **Monitoring**
   - Enable Prometheus metrics
   - Set up alerting for seal/unseal events
   - Monitor secret access patterns

## References

- Full documentation: `docs/VAULT_INTEGRATION.md`
- Vault documentation: https://www.vaultproject.io/docs
- Production hardening: https://learn.hashicorp.com/tutorials/vault/production-hardening

## Success Criteria ✅

Your Vault integration is successful if:

- ✅ `docker-compose up -d` starts all services without errors
- ✅ `python scripts/vault_health_check.py` passes all checks
- ✅ `python scripts/test_vault_integration.py` shows 7/7 tests passed
- ✅ Backend logs show "Successfully retrieved secrets from Vault"
- ✅ Airflow logs show "Airflow secrets loaded"
- ✅ No passwords visible in `docker-compose ps` or `docker inspect`
- ✅ Vault UI accessible at `http://localhost:8200`
