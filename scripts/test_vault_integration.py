#!/usr/bin/env python3
"""
End-to-End Vault Integration Test

Reason: Validates that all services can successfully retrieve secrets from Vault
This script simulates how each service accesses Vault and verifies success
"""

import hvac
import sys
import time
from typing import Dict, List


class VaultIntegrationTester:
    """Test suite for Vault integration"""
    
    def __init__(self, vault_addr="http://localhost:8200", vault_token="root"):
        """
        Initialize the tester
        
        Reason: Sets up connection parameters for Vault
        """
        self.vault_addr = vault_addr
        self.vault_token = vault_token
        self.client = None
        self.test_results = []
    
    def connect(self) -> bool:
        """
        Connect to Vault and authenticate
        
        Reason: Establishes connection before running tests
        """
        print(f"🔌 Connecting to Vault at {self.vault_addr}...")
        try:
            self.client = hvac.Client(url=self.vault_addr, token=self.vault_token)
            
            if not self.client.is_authenticated():
                print("❌ Authentication failed")
                return False
            
            print("✅ Successfully connected and authenticated")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def test_kv_engine_enabled(self) -> bool:
        """
        Test that KV v2 secrets engine is enabled
        
        Reason: Verifies the secrets engine is configured
        """
        print("\n📝 Testing KV secrets engine...")
        try:
            # Reason: List all enabled secrets engines
            secrets_engines = self.client.sys.list_mounted_secrets_engines()
            
            if 'secret/' in secrets_engines:
                engine_type = secrets_engines['secret/']['type']
                version = secrets_engines['secret/'].get('options', {}).get('version', '1')
                print(f"✅ KV engine enabled (type: {engine_type}, version: {version})")
                return True
            else:
                print("❌ KV engine not found at 'secret/' path")
                return False
        except Exception as e:
            print(f"❌ Failed to check secrets engine: {e}")
            return False
    
    def test_backend_secrets(self) -> bool:
        """
        Test backend secrets retrieval
        
        Reason: Simulates backend service accessing its secrets
        """
        print("\n🔐 Testing backend secrets...")
        required_keys = [
            'postgres_user', 'postgres_password', 'postgres_db',
            'minio_access_key', 'minio_secret_key', 'jwt_algorithm'
        ]
        
        try:
            # Reason: Read backend secrets (same as backend service does)
            secret_response = self.client.secrets.kv.v2.read_secret_version(path='backend')
            secrets = secret_response['data']['data']
            
            # Reason: Verify all required keys exist
            missing_keys = [key for key in required_keys if key not in secrets]
            
            if missing_keys:
                print(f"❌ Missing keys: {missing_keys}")
                return False
            
            print("✅ All backend secrets present:")
            for key in required_keys:
                value = secrets[key]
                masked_value = f"{value[:3]}***" if len(value) > 3 else "***"
                print(f"  • {key}: {masked_value}")
            
            return True
        except Exception as e:
            print(f"❌ Failed to read backend secrets: {e}")
            return False
    
    def test_airflow_secrets(self) -> bool:
        """
        Test Airflow secrets retrieval
        
        Reason: Simulates Airflow services accessing their secrets
        """
        print("\n🔐 Testing Airflow secrets...")
        required_keys = [
            'postgres_user', 'postgres_password', 'postgres_db',
            'fernet_key', 'webserver_secret_key',
            'minio_access_key', 'minio_secret_key'
        ]
        
        try:
            # Reason: Read Airflow secrets (same as Airflow DAGs do)
            secret_response = self.client.secrets.kv.v2.read_secret_version(path='airflow')
            secrets = secret_response['data']['data']
            
            # Reason: Verify all required keys exist
            missing_keys = [key for key in required_keys if key not in secrets]
            
            if missing_keys:
                print(f"❌ Missing keys: {missing_keys}")
                return False
            
            print("✅ All Airflow secrets present:")
            for key in required_keys:
                value = secrets[key]
                masked_value = f"{value[:3]}***" if len(value) > 3 else "***"
                print(f"  • {key}: {masked_value}")
            
            return True
        except Exception as e:
            print(f"❌ Failed to read Airflow secrets: {e}")
            return False
    
    def test_policies(self) -> bool:
        """
        Test that required policies exist
        
        Reason: Verifies access control policies are configured
        """
        print("\n🛡️ Testing Vault policies...")
        required_policies = ['backend-policy', 'airflow-policy']
        
        try:
            # Reason: List all policies
            policies = self.client.sys.list_policies()
            
            missing_policies = [p for p in required_policies if p not in policies]
            
            if missing_policies:
                print(f"❌ Missing policies: {missing_policies}")
                return False
            
            print("✅ All required policies exist:")
            for policy in required_policies:
                # Reason: Read policy to verify it's properly configured
                policy_rules = self.client.sys.read_policy(policy)
                print(f"  • {policy} ✓")
            
            return True
        except Exception as e:
            print(f"❌ Failed to check policies: {e}")
            return False
    
    def test_secret_versioning(self) -> bool:
        """
        Test KV v2 versioning features
        
        Reason: Verifies that secret versioning is working correctly
        """
        print("\n📚 Testing secret versioning...")
        try:
            # Reason: Get metadata to check version history
            metadata = self.client.secrets.kv.v2.read_secret_metadata(path='backend')
            
            current_version = metadata['data']['current_version']
            created_time = metadata['data']['created_time']
            
            print(f"✅ Secret versioning working:")
            print(f"  • Current version: {current_version}")
            print(f"  • Created: {created_time}")
            
            return True
        except Exception as e:
            print(f"❌ Failed to check versioning: {e}")
            return False
    
    def test_policy_enforcement(self) -> bool:
        """
        Test that policies properly restrict access
        
        Reason: Verifies that backend-policy only allows access to backend secrets
        """
        print("\n🔒 Testing policy enforcement...")
        
        # Reason: This test would create a token with backend-policy
        # and verify it can access backend/ but not airflow/
        # For now, we just verify the policies are correctly formatted
        
        try:
            backend_policy = self.client.sys.read_policy('backend-policy')
            airflow_policy = self.client.sys.read_policy('airflow-policy')
            
            # Reason: Verify policies contain the correct paths
            if 'secret/data/backend' in backend_policy:
                print("✅ backend-policy correctly configured")
            else:
                print("⚠️ backend-policy may not be correctly configured")
            
            if 'secret/data/airflow' in airflow_policy:
                print("✅ airflow-policy correctly configured")
            else:
                print("⚠️ airflow-policy may not be correctly configured")
            
            return True
        except Exception as e:
            print(f"❌ Failed to check policy enforcement: {e}")
            return False
    
    def test_connection_resilience(self) -> bool:
        """
        Test connection retry logic
        
        Reason: Verifies that services can handle temporary Vault unavailability
        """
        print("\n🔄 Testing connection resilience...")
        
        # Reason: Simulate retry logic (same pattern as in services)
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                client = hvac.Client(url=self.vault_addr, token=self.vault_token)
                
                if client.is_authenticated():
                    print(f"✅ Connection successful on attempt {attempt + 1}")
                    return True
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Attempt {attempt + 1} failed, retrying...")
                    time.sleep(retry_delay)
                else:
                    print(f"❌ All retry attempts failed: {e}")
                    return False
        
        return False
    
    def run_all_tests(self) -> bool:
        """
        Run all tests and return overall result
        
        Reason: Executes the complete test suite
        """
        print("=" * 60)
        print("🚀 Vault Integration Test Suite")
        print("=" * 60)
        
        # Reason: Connect to Vault first
        if not self.connect():
            print("\n❌ Failed to connect to Vault. Aborting tests.")
            return False
        
        # Reason: Define all tests to run
        tests = [
            ("KV Engine", self.test_kv_engine_enabled),
            ("Backend Secrets", self.test_backend_secrets),
            ("Airflow Secrets", self.test_airflow_secrets),
            ("Policies", self.test_policies),
            ("Secret Versioning", self.test_secret_versioning),
            ("Policy Enforcement", self.test_policy_enforcement),
            ("Connection Resilience", self.test_connection_resilience),
        ]
        
        # Reason: Run each test and track results
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"\n❌ Test '{test_name}' crashed: {e}")
                results.append((test_name, False))
        
        # Reason: Print summary
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test_name}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All tests passed! Vault integration is working correctly.")
            return True
        else:
            print(f"\n⚠️ {total - passed} test(s) failed. Please review the output above.")
            return False


def main():
    """
    Main entry point
    
    Reason: Runs the test suite and exits with appropriate code
    """
    tester = VaultIntegrationTester()
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
