#!/bin/bash
# Vault Setup and Verification Script for Linux
# Reason: Automates the deployment and verification of Vault integration

echo "========================================"
echo "HashiCorp Vault Setup and Verification"
echo "========================================"
echo ""

# Reason: Check if Docker is running
echo "[1/6] Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker."
    exit 1
fi
echo "✓ Docker is running"
echo ""

# Reason: Stop any existing containers
echo "[2/6] Stopping existing containers..."
docker-compose down
echo "✓ Containers stopped"
echo ""

# Reason: Start Vault and vault-init first
echo "[3/6] Starting Vault services..."
docker-compose up -d vault
sleep 5
docker-compose up -d vault-init
echo "✓ Vault services started"
echo ""

# Reason: Wait for vault-init to complete
echo "[4/6] Waiting for Vault initialization..."
sleep 10

# Reason: Check vault-init logs
docker logs vault-init
echo ""

# Reason: Start all other services
echo "[5/6] Starting all services..."
docker-compose up -d
echo "✓ All services started"
echo ""

# Reason: Wait for services to be ready
echo "[6/6] Waiting for services to be ready (30 seconds)..."
sleep 30
echo ""

# Reason: Show running services
echo "========================================"
echo "Running Services:"
echo "========================================"
docker-compose ps
echo ""

echo "========================================"
echo "Next Steps:"
echo "========================================"
echo "1. Install Python dependencies: pip install hvac"
echo "2. Run health check: python3 scripts/vault_health_check.py"
echo "3. Run integration tests: python3 scripts/test_vault_integration.py"
echo "4. Access Vault UI: http://localhost:8200 (token: root)"
echo "5. Check backend logs: docker logs backend"
echo "6. Check Airflow logs: docker logs airflow-webserver"
echo ""
echo "Setup complete!"
