#!/usr/bin/env python3
"""
Security Audit Script

Reason: Comprehensive security testing including SQL injection, XSS, JWT validation, and more
Tests for common vulnerabilities in the fraud detection system
"""

import requests
import jwt
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


class SecurityAuditor:
    """
    Security audit tool for the fraud detection system
    
    Reason: Identifies security vulnerabilities before production deployment
    """
    
    def __init__(self, base_url="http://localhost:8000"):
        """
        Initialize the security auditor
        
        Reason: Sets up testing parameters
        """
        self.base_url = base_url
        self.vulnerabilities = []
        self.warnings = []
        self.secure = []
    
    def log(self, message: str, level: str = "INFO"):
        """
        Log a security test message
        
        Reason: Provides visibility into security testing
        """
        prefix = {
            "SECURE": "✅",
            "VULNERABLE": "❌",
            "WARNING": "⚠️",
            "INFO": "ℹ️"
        }.get(level, "•")
        print(f"{prefix} {message}")
    
    def test_sql_injection(self) -> bool:
        """
        Test 1: SQL Injection Vulnerabilities
        
        Reason: Verify the system is protected against SQL injection attacks
        """
        self.log("\n--- Testing SQL Injection Protection ---", "INFO")
        
        # Reason: Common SQL injection payloads
        sql_payloads = [
            "' OR '1'='1",
            "admin'--",
            "' OR '1'='1' --",
            "1' UNION SELECT NULL--",
            "'; DROP TABLE users--"
        ]
        
        vulnerable = False
        
        for payload in sql_payloads:
            try:
                # Reason: Test login endpoint with SQL injection
                response = requests.post(
                    f"{self.base_url}/auth/login",
                    json={"username": payload, "password": payload},
                    timeout=10
                )
                
                # Reason: Should return 401 (Unauthorized), not 200
                if response.status_code == 200:
                    self.log(f"CRITICAL: SQL injection possible with payload: {payload}", "VULNERABLE")
                    self.vulnerabilities.append(f"SQL Injection in login: payload '{payload}' succeeded")
                    vulnerable = True
                
            except Exception as e:
                pass  # Errors are expected
        
        if not vulnerable:
            self.log("SQL injection protection: SECURE", "SECURE")
            self.secure.append("SQL Injection protection working")
            return True
        
        return False
    
    def test_xss_protection(self) -> bool:
        """
        Test 2: Cross-Site Scripting (XSS) Protection
        
        Reason: Verify user input is properly sanitized
        """
        self.log("\n--- Testing XSS Protection ---", "INFO")
        
        # Reason: Common XSS payloads
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>"
        ]
        
        vulnerable = False
        
        for payload in xss_payloads:
            try:
                # Reason: Test transaction validation with XSS payload
                response = requests.post(
                    f"{self.base_url}/api/v1/transaction/validate",
                    json={
                        "transaction_id": payload,
                        "user_id": "user_123",
                        "device_id": "device_456",
                        "amount": 100,
                        "merchant_category": "retail",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "location": payload
                    },
                    timeout=10
                )
                
                # Reason: Check if payload is reflected in response
                if response.status_code == 200 and payload in response.text:
                    self.log(f"WARNING: Possible XSS with payload: {payload}", "WARNING")
                    self.warnings.append(f"XSS: payload '{payload}' reflected in response")
                    vulnerable = True
                
            except Exception as e:
                pass
        
        if not vulnerable:
            self.log("XSS protection: SECURE", "SECURE")
            self.secure.append("XSS protection working")
            return True
        else:
            self.log("XSS protection: Needs review", "WARNING")
            return False
    
    def test_jwt_validation(self) -> bool:
        """
        Test 3: JWT Token Validation
        
        Reason: Verify JWT tokens are properly validated
        """
        self.log("\n--- Testing JWT Validation ---", "INFO")
        
        vulnerable = False
        
        # Reason: Test 1 - Invalid JWT format
        try:
            headers = {"Authorization": "Bearer invalid_token_format"}
            response = requests.get(
                f"{self.base_url}/transactions/",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 403 or response.status_code == 401:
                self.log("Invalid JWT format correctly rejected", "SECURE")
            else:
                self.log(f"Invalid JWT accepted (status: {response.status_code})", "VULNERABLE")
                self.vulnerabilities.append("Invalid JWT format not rejected")
                vulnerable = True
        except Exception as e:
            pass
        
        # Reason: Test 2 - Expired token
        try:
            # Create an expired token
            expired_payload = {
                "sub": "admin",
                "exp": datetime.utcnow() - timedelta(hours=1),
                "type": "access"
            }
            expired_token = jwt.encode(expired_payload, "secret", algorithm="HS256")
            
            headers = {"Authorization": f"Bearer {expired_token}"}
            response = requests.get(
                f"{self.base_url}/transactions/",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 403 or response.status_code == 401:
                self.log("Expired JWT correctly rejected", "SECURE")
            else:
                self.log("WARNING: Expired JWT might be accepted", "WARNING")
                self.warnings.append("Expired JWT validation unclear")
        except Exception as e:
            self.log("Expired token test inconclusive", "WARNING")
        
        # Reason: Test 3 - No token provided
        try:
            response = requests.get(
                f"{self.base_url}/transactions/",
                timeout=10
            )
            
            if response.status_code == 403:
                self.log("Missing JWT correctly rejected", "SECURE")
            else:
                self.log(f"Missing JWT not rejected (status: {response.status_code})", "VULNERABLE")
                self.vulnerabilities.append("Missing JWT not properly handled")
                vulnerable = True
        except Exception as e:
            pass
        
        if not vulnerable:
            self.secure.append("JWT validation working correctly")
            return True
        
        return False
    
    def test_rate_limiting(self) -> bool:
        """
        Test 4: Rate Limiting
        
        Reason: Verify rate limiting is configured to prevent abuse
        """
        self.log("\n--- Testing Rate Limiting ---", "INFO")
        
        # Reason: Send multiple rapid requests
        rapid_requests = 200
        rate_limited = False
        
        self.log(f"Sending {rapid_requests} rapid requests...", "INFO")
        
        for i in range(rapid_requests):
            try:
                response = requests.get(f"{self.base_url}/", timeout=5)
                
                if response.status_code == 429:  # Too Many Requests
                    self.log(f"Rate limiting triggered after {i+1} requests", "SECURE")
                    rate_limited = True
                    break
                    
            except Exception as e:
                pass
        
        if not rate_limited:
            self.log("WARNING: No rate limiting detected", "WARNING")
            self.warnings.append("Rate limiting not detected (Traefik configuration needed)")
            return False
        else:
            self.secure.append("Rate limiting working")
            return True
    
    def test_authentication_bypass(self) -> bool:
        """
        Test 5: Authentication Bypass Attempts
        
        Reason: Verify there are no ways to bypass authentication
        """
        self.log("\n--- Testing Authentication Bypass ---", "INFO")
        
        vulnerable = False
        
        # Reason: Test various bypass techniques
        bypass_attempts = [
            {"username": "admin", "password": ""},
            {"username": "", "password": "admin"},
            {"username": None, "password": None},
        ]
        
        for attempt in bypass_attempts:
            try:
                response = requests.post(
                    f"{self.base_url}/auth/login",
                    json=attempt,
                    timeout=10
                )
                
                if response.status_code == 200:
                    self.log(f"CRITICAL: Authentication bypassed with {attempt}", "VULNERABLE")
                    self.vulnerabilities.append(f"Authentication bypass possible: {attempt}")
                    vulnerable = True
                    
            except Exception as e:
                pass
        
        if not vulnerable:
            self.log("No authentication bypass found", "SECURE")
            self.secure.append("Authentication bypass protection working")
            return True
        
        return False
    
    def test_https_configuration(self) -> bool:
        """
        Test 6: HTTPS Configuration
        
        Reason: Verify TLS/SSL is properly configured
        """
        self.log("\n--- Testing HTTPS Configuration ---", "INFO")
        
        if self.base_url.startswith("https://"):
            try:
                response = requests.get(self.base_url, timeout=10, verify=True)
                self.log("HTTPS properly configured", "SECURE")
                self.secure.append("HTTPS enabled")
                return True
            except requests.exceptions.SSLError:
                self.log("WARNING: SSL certificate issues detected", "WARNING")
                self.warnings.append("SSL certificate validation failed")
                return False
        else:
            self.log("WARNING: Running on HTTP (not HTTPS)", "WARNING")
            self.warnings.append("HTTPS not enabled (development mode)")
            return False
    
    def test_sensitive_data_exposure(self) -> bool:
        """
        Test 7: Sensitive Data Exposure
        
        Reason: Verify no sensitive data is leaked in responses
        """
        self.log("\n--- Testing Sensitive Data Exposure ---", "INFO")
        
        exposed = False
        
        # Reason: Check root endpoint for sensitive info
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)
            data = response.json()
            
            # Reason: Check for exposed sensitive data
            sensitive_keywords = ["password", "secret", "token", "key", "credential"]
            response_text = str(data).lower()
            
            for keyword in sensitive_keywords:
                if keyword in response_text:
                    self.log(f"WARNING: Possible sensitive data exposure: '{keyword}' in response", "WARNING")
                    self.warnings.append(f"Sensitive keyword '{keyword}' in API response")
                    exposed = True
                    
        except Exception as e:
            pass
        
        if not exposed:
            self.log("No sensitive data exposure detected", "SECURE")
            self.secure.append("Sensitive data properly protected")
            return True
        
        return False
    
    def test_input_validation(self) -> bool:
        """
        Test 8: Input Validation
        
        Reason: Verify proper input validation on all endpoints
        """
        self.log("\n--- Testing Input Validation ---", "INFO")
        
        # Reason: Test with malformed data
        invalid_inputs = [
            {"amount": -1000},  # Negative amount
            {"amount": "not_a_number"},  # Wrong type
            {"timestamp": "invalid_date"},  # Invalid date format
        ]
        
        properly_validated = True
        
        for invalid_input in invalid_inputs:
            try:
                # Merge with valid transaction data
                transaction = {
                    "transaction_id": "test_validation",
                    "user_id": "user_123",
                    "device_id": "device_456",
                    "amount": 100,
                    "merchant_category": "retail",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "location": "Test"
                }
                transaction.update(invalid_input)
                
                response = requests.post(
                    f"{self.base_url}/api/v1/transaction/validate",
                    json=transaction,
                    timeout=10
                )
                
                # Reason: Should return 422 (Validation Error)
                if response.status_code == 200:
                    self.log(f"WARNING: Invalid input accepted: {invalid_input}", "WARNING")
                    self.warnings.append(f"Input validation weak for: {invalid_input}")
                    properly_validated = False
                elif response.status_code == 422:
                    pass  # Expected
                    
            except Exception as e:
                pass
        
        if properly_validated:
            self.log("Input validation working correctly", "SECURE")
            self.secure.append("Input validation properly implemented")
            return True
        
        return False
    
    def run_security_audit(self) -> bool:
        """
        Run all security tests
        
        Reason: Executes the complete security audit
        """
        self.log("=" * 60, "INFO")
        self.log("SECURITY AUDIT - KYDA Fraud Detection System", "INFO")
        self.log("=" * 60, "INFO")
        
        # Reason: Run all security tests
        tests = [
            ("SQL Injection Protection", self.test_sql_injection),
            ("XSS Protection", self.test_xss_protection),
            ("JWT Validation", self.test_jwt_validation),
            ("Rate Limiting", self.test_rate_limiting),
            ("Authentication Bypass", self.test_authentication_bypass),
            ("HTTPS Configuration", self.test_https_configuration),
            ("Sensitive Data Exposure", self.test_sensitive_data_exposure),
            ("Input Validation", self.test_input_validation),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                self.log(f"Test '{test_name}' failed: {e}", "WARNING")
                results.append((test_name, False))
        
        # Reason: Print summary
        self.print_summary(results)
        
        # Reason: Return True if no critical vulnerabilities found
        return len(self.vulnerabilities) == 0
    
    def print_summary(self, results: List[Tuple[str, bool]]):
        """
        Print security audit summary
        
        Reason: Provides comprehensive security assessment
        """
        print("\n" + "=" * 60)
        print("SECURITY AUDIT SUMMARY")
        print("=" * 60)
        
        print(f"\n✅ Secure ({len(self.secure)}):")
        for item in self.secure:
            print(f"  • {item}")
        
        if self.warnings:
            print(f"\n⚠️ Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if self.vulnerabilities:
            print(f"\n❌ CRITICAL Vulnerabilities ({len(self.vulnerabilities)}):")
            for vuln in self.vulnerabilities:
                print(f"  • {vuln}")
        
        print("\n" + "=" * 60)
        print("OVERALL SECURITY ASSESSMENT")
        print("=" * 60)
        
        if len(self.vulnerabilities) == 0:
            if len(self.warnings) == 0:
                print("🎉 EXCELLENT: No vulnerabilities or warnings found!")
                print("   System is secure for production deployment.")
            else:
                print("✅ GOOD: No critical vulnerabilities found.")
                print(f"   {len(self.warnings)} warning(s) should be reviewed.")
        else:
            print("❌ CRITICAL: Security vulnerabilities detected!")
            print("   DO NOT deploy to production until fixed.")
        
        print("=" * 60)


def main():
    """
    Main entry point
    
    Reason: Runs the security audit
    """
    print("\n" + "=" * 60)
    print("KYDA Fraud Detection - Security Audit Tool")
    print("=" * 60 + "\n")
    
    # Reason: Check if backend is accessible
    print("Checking if backend is accessible...")
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        print("✅ Backend is accessible\n")
    except Exception as e:
        print(f"❌ Backend is not accessible: {e}")
        print("Please ensure docker-compose is running: docker-compose up -d")
        sys.exit(1)
    
    # Reason: Run security audit
    auditor = SecurityAuditor()
    success = auditor.run_security_audit()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
