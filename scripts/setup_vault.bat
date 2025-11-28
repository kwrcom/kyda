@echo off
REM Vault Setup and Verification Script for Windows
REM Reason: Automates the deployment and verification of Vault integration

echo ========================================
echo HashiCorp Vault Setup and Verification
echo ========================================
echo.

REM Reason: Check if Docker is running
echo [1/6] Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running. Please start Docker Desktop.
    exit /b 1
)
echo ✓ Docker is running
echo.

REM Reason: Stop any existing containers
echo [2/6] Stopping existing containers...
docker-compose down
echo ✓ Containers stopped
echo.

REM Reason: Start Vault and vault-init first
echo [3/6] Starting Vault services...
docker-compose up -d vault
timeout /t 5 /nobreak >nul
docker-compose up -d vault-init
echo ✓ Vault services started
echo.

REM Reason: Wait for vault-init to complete
echo [4/6] Waiting for Vault initialization...
timeout /t 10 /nobreak >nul

REM Reason: Check vault-init logs
docker logs vault-init
echo.

REM Reason: Start all other services
echo [5/6] Starting all services...
docker-compose up -d
echo ✓ All services started
echo.

REM Reason: Wait for services to be ready
echo [6/6] Waiting for services to be ready (30 seconds)...
timeout /t 30 /nobreak >nul
echo.

REM Reason: Show running services
echo ========================================
echo Running Services:
echo ========================================
docker-compose ps
echo.

echo ========================================
echo Next Steps:
echo ========================================
echo 1. Install Python dependencies: pip install hvac
echo 2. Run health check: python scripts\vault_health_check.py
echo 3. Run integration tests: python scripts\test_vault_integration.py
echo 4. Access Vault UI: http://localhost:8200 (token: root)
echo 5. Check backend logs: docker logs backend
echo 6. Check Airflow logs: docker logs airflow-webserver
echo.
echo Setup complete!
