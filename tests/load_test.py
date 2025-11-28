#!/usr/bin/env python3
"""
Load Testing Script

Reason: Tests the system under high load to verify performance and stability
Simulates multiple concurrent users sending transactions
"""

import requests
import time
import threading
import statistics
from datetime import datetime
from typing import List, Dict
import random
import sys


class LoadTester:
    """
    Load testing tool for fraud detection system
    
    Reason: Validates system performance under stress
    """
    
    def __init__(self, base_url="http://localhost:8000", num_threads=10, transactions_per_thread=100):
        """
        Initialize the load tester
        
        Reason: Configures test parameters
        """
        self.base_url = base_url
        self.num_threads = num_threads
        self.transactions_per_thread = transactions_per_thread
        self.results = []
        self.errors = []
        self.lock = threading.Lock()
    
    def generate_transaction(self, index: int) -> Dict:
        """
        Generate a random test transaction
        
        Reason: Creates realistic transaction data for testing
        """
        merchant_categories = ["retail", "online", "food", "transport", "entertainment"]
        locations = ["New York, US", "London, UK", "Tokyo, JP", "Paris, FR", "Sydney, AU"]
        
        return {
            "transaction_id": f"load_test_{int(time.time())}_{index}_{random.randint(1000, 9999)}",
            "user_id": f"user_{random.randint(1000, 9999)}",
            "device_id": f"device_{random.randint(1000, 9999)}",
            "amount": round(random.uniform(10, 1000), 2),
            "merchant_category": random.choice(merchant_categories),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "location": random.choice(locations)
        }
    
    def send_transaction(self, transaction: Dict) -> Dict:
        """
        Send a transaction and measure response time
        
        Reason: Makes API request and tracks performance metrics
        """
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/transaction/validate",
                json=transaction,
                timeout=30
            )
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response_time,
                "transaction_id": transaction["transaction_id"]
            }
            
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            return {
                "success": False,
                "status_code": 0,
                "response_time": response_time,
                "transaction_id": transaction["transaction_id"],
                "error": str(e)
            }
    
    def worker(self, thread_id: int):
        """
        Worker thread that sends multiple transactions
        
        Reason: Simulates concurrent user activity
        """
        print(f"Thread {thread_id} started - sending {self.transactions_per_thread} transactions")
        
        for i in range(self.transactions_per_thread):
            # Reason: Generate and send transaction
            transaction = self.generate_transaction(i)
            result = self.send_transaction(transaction)
            
            # Reason: Store results in thread-safe manner
            with self.lock:
                if result["success"]:
                    self.results.append(result)
                else:
                    self.errors.append(result)
            
            # Reason: Small delay to prevent overwhelming the system instantly
            time.sleep(0.01)
        
        print(f"Thread {thread_id} completed")
    
    def run_load_test(self):
        """
        Execute the load test
        
        Reason: Spawns multiple threads to simulate concurrent load
        """
        print("=" * 60)
        print("LOAD TEST CONFIGURATION")
        print("=" * 60)
        print(f"Threads: {self.num_threads}")
        print(f"Transactions per thread: {self.transactions_per_thread}")
        print(f"Total transactions: {self.num_threads * self.transactions_per_thread}")
        print(f"Target URL: {self.base_url}")
        print("=" * 60)
        print()
        
        # Reason: Create and start worker threads
        threads = []
        start_time = time.time()
        
        print(f"Starting load test at {datetime.now().strftime('%H:%M:%S')}...\n")
        
        for i in range(self.num_threads):
            thread = threading.Thread(target=self.worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Reason: Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Reason: Analyze results
        self.print_results(total_duration)
    
    def print_results(self, total_duration: float):
        """
        Print test results and statistics
        
        Reason: Provides comprehensive performance analysis
        """
        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        
        total_requests = len(self.results) + len(self.errors)
        successful_requests = len(self.results)
        failed_requests = len(self.errors)
        
        print(f"\n📊 Overview:")
        print(f"  • Total requests: {total_requests}")
        print(f"  • Successful: {successful_requests} ({successful_requests/total_requests*100:.1f}%)")
        print(f"  • Failed: {failed_requests} ({failed_requests/total_requests*100:.1f}%)")
        print(f"  • Total duration: {total_duration:.2f} seconds")
        print(f"  • Throughput: {total_requests/total_duration:.2f} req/sec")
        
        if self.results:
            # Reason: Calculate response time statistics
            response_times = [r["response_time"] for r in self.results]
            
            print(f"\n⏱️ Response Time Statistics (ms):")
            print(f"  • Min: {min(response_times):.2f}")
            print(f"  • Max: {max(response_times):.2f}")
            print(f"  • Mean: {statistics.mean(response_times):.2f}")
            print(f"  • Median: {statistics.median(response_times):.2f}")
            
            if len(response_times) > 1:
                print(f"  • Std Dev: {statistics.stdev(response_times):.2f}")
            
            # Reason: Calculate percentiles
            sorted_times = sorted(response_times)
            p50 = sorted_times[int(len(sorted_times) * 0.50)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
            
            print(f"\n📈 Percentiles (ms):")
            print(f"  • P50: {p50:.2f}")
            print(f"  • P95: {p95:.2f}")
            print(f"  • P99: {p99:.2f}")
        
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)} total):")
            
            # Reason: Group errors by type
            error_types = {}
            for error in self.errors:
                error_key = error.get("error", f"HTTP {error['status_code']}")
                error_types[error_key] = error_types.get(error_key, 0) + 1
            
            for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                print(f"  • {error_type}: {count}")
        
        # Reason: Performance assessment
        print("\n" + "=" * 60)
        print("PERFORMANCE ASSESSMENT")
        print("=" * 60)
        
        avg_response_time = statistics.mean([r["response_time"] for r in self.results]) if self.results else 0
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        throughput = total_requests / total_duration if total_duration > 0 else 0
        
        # Reason: Define performance criteria
        criteria = {
            "Success Rate": (success_rate, ">= 95%", success_rate >= 95),
            "Average Response Time": (avg_response_time, "< 1000ms", avg_response_time < 1000),
            "Throughput": (throughput, "> 10 req/sec", throughput > 10)
        }
        
        all_passed = True
        for criterion, (value, target, passed) in criteria.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            
            if criterion == "Success Rate":
                print(f"{status} - {criterion}: {value:.1f}% (target: {target})")
            elif criterion == "Average Response Time":
                print(f"{status} - {criterion}: {value:.2f}ms (target: {target})")
            elif criterion == "Throughput":
                print(f"{status} - {criterion}: {value:.2f} req/sec (target: {target})")
            
            if not passed:
                all_passed = False
        
        print()
        if all_passed:
            print("🎉 System performance is EXCELLENT under load!")
        else:
            print("⚠️ System performance needs improvement.")
        
        print("=" * 60)


def main():
    """
    Main entry point
    
    Reason: Runs the load test with configurable parameters
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Load test the fraud detection system")
    parser.add_argument("--threads", type=int, default=10, help="Number of concurrent threads (default: 10)")
    parser.add_argument("--transactions", type=int, default=100, help="Transactions per thread (default: 100)")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="Base URL (default: http://localhost:8000)")
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("KYDA Fraud Detection - Load Testing Tool")
    print("=" * 60 + "\n")
    
    # Reason: Check if backend is accessible
    print("Checking if backend is accessible...")
    try:
        response = requests.get(args.url, timeout=5)
        print("✅ Backend is accessible\n")
    except Exception as e:
        print(f"❌ Backend is not accessible: {e}")
        print("Please ensure docker-compose is running: docker-compose up -d")
        sys.exit(1)
    
    # Reason: Warning for high load
    if args.threads * args.transactions > 5000:
        print("⚠️ WARNING: You are about to send a very high number of requests!")
        print(f"Total: {args.threads * args.transactions} requests")
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(0)
        print()
    
    # Reason: Run load test
    tester = LoadTester(
        base_url=args.url,
        num_threads=args.threads,
        transactions_per_thread=args.transactions
    )
    
    tester.run_load_test()


if __name__ == "__main__":
    main()
