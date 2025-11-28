"""
Local smoke test for the Spark Structured Streaming feature engineering pipeline.

Run this locally to verify the pipeline runs in batch/local-mode (no Kafka required):

    pip install -r requirements.txt
    python services/spark-streaming/smoke_test.py

This will create a small in-memory DataFrame, parse transactions, compute features,
and print out the final dataframe schema and a few rows to verify the fix.
"""
import json
import sys
from datetime import datetime, timedelta

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit

# Import functions from main.py in the same directory
from main import parse_transactions, calculate_time_features, calculate_windowed_features


def create_local_session():
    return SparkSession.builder.master("local[*]").appName("smoke-test").getOrCreate()


def make_json_value(transaction_id, user_id, amount, ts):
    obj = {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "amount": amount,
        "merchant_category": "groceries",
        "timestamp": ts.isoformat(),
        "location": "US",
        "device_id": "device-1",
        "is_fraud": False
    }
    return json.dumps(obj)


def run_smoke_test():
    spark = create_local_session()
    spark.sparkContext.setLogLevel("WARN")

    # Build a series of sample transactions across two users and timestamps
    now = datetime.utcnow()
    rows = [
        {"value": make_json_value("t1", "u1", 10.0, now - timedelta(hours=2))},
        {"value": make_json_value("t2", "u1", 200.0, now - timedelta(hours=1, minutes=30))},
        {"value": make_json_value("t3", "u1", 20.0, now - timedelta(minutes=20))},
        {"value": make_json_value("t4", "u2", 5.0, now - timedelta(minutes=40))},
        {"value": make_json_value("t5", "u2", 7.0, now - timedelta(minutes=10))},
    ]

    kafka_df = spark.createDataFrame(rows)

    try:
        parsed = parse_transactions(kafka_df)
        timed = calculate_time_features(parsed)

        # This step uses windowed aggregations and joins — the area where ambiguous
        # column references previously caused runtime errors. It should run in batch
        # mode for testing as well.
        enriched = calculate_windowed_features(timed)

        print("=== Enriched schema ===")
        enriched.printSchema()
        print("=== Example rows ===")
        for r in enriched.limit(10).collect():
            print(r)

    except Exception as exc:  # pragma: no cover - smoke test only
        print("Smoke test failed with exception:", exc)
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    try:
        run_smoke_test()
        print("Smoke test finished successfully — no ambiguous column errors detected.")
        sys.exit(0)
    except Exception:
        sys.exit(2)
