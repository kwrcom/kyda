"""
Transaction Data Producer for Kafka

Reason: Generates realistic transaction data with fraud patterns
Sends JSON messages to Kafka topic for fraud detection pipeline
"""

import json
import time
import random
import os
from datetime import datetime, timedelta
from typing import Dict
from kafka import KafkaProducer
from faker import Faker

# Reason: Initialize Faker for generating realistic data
fake = Faker()

# Reason: Kafka configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "transactions.raw")
TRANSACTIONS_PER_SECOND = int(os.getenv("TRANSACTIONS_PER_SECOND", "10"))

# Reason: Merchant categories for realistic transactions
MERCHANT_CATEGORIES = [
    "grocery", "restaurant", "gas_station", "online_shopping",
    "electronics", "pharmacy", "clothing", "entertainment",
    "travel", "utilities", "healthcare", "education"
]

# Reason: Simulate user base with consistent behavior patterns
USER_POOL_SIZE = 100
user_profiles = {}


def initialize_user_profiles():
    """
    Initialize user profiles with consistent patterns
    
    Reason: Creates realistic user behavior patterns
    Each user has typical spending habits and locations
    """
    global user_profiles
    
    for i in range(USER_POOL_SIZE):
        user_id = f"user_{i:04d}"
        user_profiles[user_id] = {
            "home_location": fake.city(),
            "typical_amount_range": (10, 500),
            "preferred_categories": random.sample(MERCHANT_CATEGORIES, 3),
            "device_id": fake.uuid4(),
            "transaction_count": 0,
            "last_transaction_time": None,
            "is_fraudster": random.random() < 0.05  # 5% are potential fraudsters
        }


def generate_normal_transaction(user_id: str) -> Dict:
    """
    Generate a normal (non-fraudulent) transaction
    
    Reason: Creates realistic transaction with typical patterns
    95% of transactions should be normal
    """
    profile = user_profiles[user_id]
    
    # Reason: Amount within typical range for this user
    amount = round(random.uniform(*profile["typical_amount_range"]), 2)
    
    # Reason: Prefer user's typical merchant categories
    if random.random() < 0.7:
        category = random.choice(profile["preferred_categories"])
    else:
        category = random.choice(MERCHANT_CATEGORIES)
    
    # Reason: Use consistent location (home city)
    location = profile["home_location"]
    
    # Reason: Use user's registered device
    device_id = profile["device_id"]
    
    return {
        "transaction_id": fake.uuid4(),
        "user_id": user_id,
        "amount": amount,
        "merchant_category": category,
        "timestamp": datetime.utcnow().isoformat(),
        "location": location,
        "device_id": device_id,
        "is_fraud": False
    }


def generate_fraudulent_transaction(user_id: str) -> Dict:
    """
    Generate a fraudulent transaction with anomalies
    
    Reason: Creates suspicious patterns for fraud detection testing
    5% of transactions should be fraudulent
    """
    profile = user_profiles[user_id]
    
    # Reason: Choose fraud pattern type
    fraud_type = random.choice([
        "high_amount",      # Unusually high amount
        "rapid_fire",       # Multiple transactions in short time
        "location_jump",    # Transaction from different location
        "new_device",       # Transaction from unknown device
        "unusual_category"  # Unusual merchant category
    ])
    
    # Reason: Base transaction on normal pattern
    transaction = generate_normal_transaction(user_id)
    transaction["is_fraud"] = True
    
    # Reason: Apply fraud pattern
    if fraud_type == "high_amount":
        # Anomalously high amount
        transaction["amount"] = round(random.uniform(1000, 5000), 2)
    
    elif fraud_type == "rapid_fire":
        # Multiple transactions in short period (simulated by timestamp)
        # In real scenario, this would be detected by frequency analysis
        transaction["amount"] = round(random.uniform(50, 300), 2)
    
    elif fraud_type == "location_jump":
        # Transaction from different country/city (impossible travel)
        transaction["location"] = fake.city()
    
    elif fraud_type == "new_device":
        # Transaction from unknown device
        transaction["device_id"] = fake.uuid4()
    
    elif fraud_type == "unusual_category":
        # Unusual merchant category for this user
        unusual_categories = [c for c in MERCHANT_CATEGORIES 
                            if c not in profile["preferred_categories"]]
        transaction["merchant_category"] = random.choice(unusual_categories)
        transaction["amount"] = round(random.uniform(800, 2000), 2)
    
    return transaction


def generate_transaction() -> Dict:
    """
    Generate a transaction (95% normal, 5% fraud)
    
    Reason: Main transaction generator with proper fraud distribution
    """
    # Reason: Select random user from pool
    user_id = random.choice(list(user_profiles.keys()))
    profile = user_profiles[user_id]
    
    # Reason: Update user's transaction history
    profile["transaction_count"] += 1
    profile["last_transaction_time"] = datetime.utcnow()
    
    # Reason: Determine if transaction should be fraudulent
    # 95% normal, 5% fraud distribution
    if random.random() < 0.95:
        return generate_normal_transaction(user_id)
    else:
        return generate_fraudulent_transaction(user_id)


def create_kafka_producer() -> KafkaProducer:
    """
    Create Kafka producer with JSON serialization
    
    Reason: Initializes Kafka producer with proper configuration
    """
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        # Reason: Retry configuration for reliability
        retries=5,
        # Reason: Compression for better network efficiency
        compression_type='gzip'
    )


def main():
    """
    Main producer loop
    
    Reason: Continuously generates and sends transactions to Kafka
    """
    print(f"Starting transaction producer...")
    print(f"Kafka servers: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic: {KAFKA_TOPIC}")
    print(f"Rate: {TRANSACTIONS_PER_SECOND} transactions/second")
    
    # Reason: Initialize user profiles for consistent behavior
    initialize_user_profiles()
    print(f"Initialized {USER_POOL_SIZE} user profiles")
    
    # Reason: Wait for Kafka to be ready
    time.sleep(10)
    
    # Reason: Create Kafka producer
    producer = create_kafka_producer()
    print("Connected to Kafka")
    
    # Reason: Calculate sleep time between transactions
    sleep_time = 1.0 / TRANSACTIONS_PER_SECOND
    
    transaction_count = 0
    fraud_count = 0
    
    import requests
    FAST_SCORER_URL = os.getenv("FAST_SCORER_URL", "http://fast-scorer:8001/score")

    try:
        while True:
            # Reason: Generate transaction
            transaction = generate_transaction()
            
            # Reason: Send to Kafka (Async Path)
            producer.send(KAFKA_TOPIC, value=transaction)

            # Reason: Send to Fast Scorer (Sync/L1 Path)
            try:
                requests.post(FAST_SCORER_URL, json=transaction, timeout=0.5)
            except Exception as e:
                # print(f"Failed to call fast-scorer: {e}")
                pass
            
            # Reason: Track statistics
            transaction_count += 1
            if transaction["is_fraud"]:
                fraud_count += 1
            
            # Reason: Log progress every 100 transactions
            if transaction_count % 100 == 0:
                fraud_rate = (fraud_count / transaction_count) * 100
                print(f"Sent {transaction_count} transactions "
                      f"({fraud_count} fraudulent, {fraud_rate:.1f}%)")
            
            # Reason: Rate limiting
            time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        print("\nShutting down producer...")
    finally:
        # Reason: Flush and close producer
        producer.flush()
        producer.close()
        print(f"Producer stopped. Total transactions: {transaction_count}")


if __name__ == "__main__":
    main()
