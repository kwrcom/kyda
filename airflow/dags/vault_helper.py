"""
Vault Secrets Helper for Airflow DAGs

Reason: Centralized module for retrieving secrets from Vault in Airflow DAGs
This ensures consistent error handling and retry logic across all DAGs
"""

import os
import time
import hvac


# Reason: Singleton pattern to cache Vault client and avoid repeated connections
_vault_client = None
_secrets_cache = {}


def get_vault_client(max_retries=5, retry_delay=2):
    """
    Get or create Vault client with retry logic
    
    Reason: Vault might not be immediately available during Airflow startup,
    so we implement retry logic to handle temporary connection issues
    """
    global _vault_client
    
    # Reason: Return cached client if already connected
    if _vault_client is not None:
        try:
            if _vault_client.is_authenticated():
                return _vault_client
        except Exception:
            # Reason: Client became invalid, recreate it
            _vault_client = None
    
    vault_addr = os.getenv('VAULT_ADDR', 'http://vault:8200')
    
    # Auth methods
    vault_token = os.getenv('VAULT_TOKEN')
    vault_role_id = os.getenv('VAULT_ROLE_ID')
    vault_secret_id = os.getenv('VAULT_SECRET_ID')
    
    for attempt in range(max_retries):
        try:
            print(f"Connecting to Vault at {vault_addr} (attempt {attempt + 1}/{max_retries})")
            client = hvac.Client(url=vault_addr)
            
            # Authentication Logic
            if vault_role_id and vault_secret_id:
                print("Authenticating via AppRole...")
                client.auth.approle.login(
                    role_id=vault_role_id,
                    secret_id=vault_secret_id
                )
            elif vault_token:
                print("Authenticating via Token...")
                client.token = vault_token
            else:
                client.token = 'root'
            
            # Reason: Verify authentication before returning
            if not client.is_authenticated():
                raise Exception("Vault authentication failed")
            
            print("✅ Successfully connected to Vault")
            _vault_client = client
            return client
            
        except Exception as e:
            print(f"⚠️ Failed to connect to Vault: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise Exception(f"Could not connect to Vault after {max_retries} attempts")


def get_secrets(path, use_cache=True):
    """
    Retrieve secrets from Vault KV v2 storage
    
    Args:
        path: Secret path (e.g., 'backend', 'airflow')
        use_cache: Whether to use cached secrets (default: True)
    
    Returns:
        dict: Secret key-value pairs
    
    Reason: Provides caching to avoid repeated Vault API calls for the same secrets
    """
    global _secrets_cache
    
    # Reason: Return from cache if available and caching is enabled
    if use_cache and path in _secrets_cache:
        print(f"📦 Using cached secrets for path: {path}")
        return _secrets_cache[path]
    
    # Reason: Fetch from Vault
    client = get_vault_client()
    
    try:
        print(f"🔐 Fetching secrets from Vault: secret/{path}")
        secret_response = client.secrets.kv.v2.read_secret_version(path=path)
        secrets = secret_response['data']['data']
        
        # Reason: Cache the secrets for future use
        _secrets_cache[path] = secrets
        
        print(f"✅ Successfully retrieved {len(secrets)} secrets from {path}")
        return secrets
        
    except Exception as e:
        raise Exception(f"Failed to retrieve secrets from path '{path}': {e}")


def get_airflow_secrets():
    """
    Get Airflow-specific secrets from Vault
    
    Returns:
        dict: Airflow secrets including postgres credentials, fernet key, etc.
    
    Reason: Convenience method for Airflow DAGs to get their secrets
    """
    return get_secrets('airflow')


def get_backend_secrets():
    """
    Get backend-specific secrets from Vault
    
    Returns:
        dict: Backend secrets including postgres, minio, JWT config
    
    Reason: Convenience method for backend service secrets
    """
    return get_secrets('backend')


# Reason: Pre-load secrets at module import for Airflow DAGs
# This ensures secrets are available when DAGs are parsed
try:
    # Reason: Only pre-load if running in Airflow context
    if os.getenv('AIRFLOW__CORE__EXECUTOR'):
        print("🚀 Pre-loading Airflow secrets...")
        AIRFLOW_SECRETS = get_airflow_secrets()
        print(f"✅ Airflow secrets loaded: {list(AIRFLOW_SECRETS.keys())}")
except Exception as e:
    print(f"⚠️ Could not pre-load Airflow secrets: {e}")
    print("Secrets will be loaded on-demand")
    AIRFLOW_SECRETS = {}
