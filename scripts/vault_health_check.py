#!/usr/bin/env python3
"""
Vault Health Check Script

Reason: Verify that Vault is running, accessible, and contains all required secrets
This script validates the Vault setup before starting dependent services
"""

import hvac
import sys
import time


def check_vault_health(max_retries=10, retry_delay=2):
    """
    Check Vault health and verify secrets exist
    
    Reason: Ensures Vault is ready and all secrets are configured correctly
    """
    vault_addr = "http://localhost:8200"
    vault_token = "root"
    
    print(f"Connecting to Vault at {vault_addr}...")
    
    for attempt in range(max_retries):
        try:
            # Reason: Create Vault client
            client = hvac.Client(url=vault_addr, token=vault_token)
            
            # Reason: Check if Vault is accessible
            if not client.is_authenticated():
                print(f"❌ Vault authentication failed (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                continue
            
            print("✅ Vault is accessible and authenticated")
            
            # Reason: Check backend secrets
            print("\nChecking backend secrets...")
            try:
                backend_secrets = client.secrets.kv.v2.read_secret_version(path='backend')
                backend_data = backend_secrets['data']['data']
                
                required_backend_keys = [
                    'postgres_user', 'postgres_password', 'postgres_db',
                    'minio_access_key', 'minio_secret_key', 'jwt_algorithm'
                ]
                
                for key in required_backend_keys:
                    if key in backend_data:
                        print(f"  ✅ {key}: {backend_data[key][:3]}***" if len(backend_data[key]) > 3 else f"  ✅ {key}: ***")
                    else:
                        print(f"  ❌ Missing key: {key}")
                        return False
                        
            except Exception as e:
                print(f"  ❌ Failed to read backend secrets: {e}")
                return False
            
            # Reason: Check Airflow secrets
            print("\nChecking Airflow secrets...")
            try:
                airflow_secrets = client.secrets.kv.v2.read_secret_version(path='airflow')
                airflow_data = airflow_secrets['data']['data']
                
                required_airflow_keys = [
                    'postgres_user', 'postgres_password', 'postgres_db',
                    'fernet_key', 'webserver_secret_key',
                    'minio_access_key', 'minio_secret_key'
                ]
                
                for key in required_airflow_keys:
                    if key in airflow_data:
                        print(f"  ✅ {key}: {airflow_data[key][:3]}***" if len(airflow_data[key]) > 3 else f"  ✅ {key}: ***")
                    else:
                        print(f"  ❌ Missing key: {key}")
                        return False
                        
            except Exception as e:
                print(f"  ❌ Failed to read Airflow secrets: {e}")
                return False
            
            # Reason: Check policies
            print("\nChecking Vault policies...")
            try:
                policies = client.sys.list_policies()
                
                if 'backend-policy' in policies:
                    print("  ✅ backend-policy exists")
                else:
                    print("  ❌ backend-policy missing")
                    return False
                
                if 'airflow-policy' in policies:
                    print("  ✅ airflow-policy exists")
                else:
                    print("  ❌ airflow-policy missing")
                    return False
                    
            except Exception as e:
                print(f"  ❌ Failed to check policies: {e}")
                return False
            
            print("\n✅ All Vault health checks passed!")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    print(f"\n❌ Failed to connect to Vault after {max_retries} attempts")
    return False


if __name__ == "__main__":
    success = check_vault_health()
    sys.exit(0 if success else 1)
