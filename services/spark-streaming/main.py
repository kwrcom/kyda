"""
Spark Structured Streaming Application for Real-Time Feature Engineering

Reason: Processes transaction data from Kafka, calculates features, and writes enriched data back to Kafka
Uses windowed aggregations for user-level statistics and checkpointing for fault tolerance
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, to_json, struct, window, avg, stddev, count,
    hour, dayofweek, when, lit, expr
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, TimestampType
)
import os
import json
import redis
from kafka import KafkaProducer

# Reason: Kafka configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_RAW = os.getenv("KAFKA_TOPIC_RAW", "transactions.raw")
KAFKA_TOPIC_PREPROCESSED = os.getenv("KAFKA_TOPIC_PREPROCESSED", "transactions.preprocessed")
KAFKA_TOPIC_LEVEL2 = os.getenv("KAFKA_TOPIC_LEVEL2", "transactions.level2")
CHECKPOINT_DIR = os.getenv("SPARK_CHECKPOINT_DIR", "/opt/spark/checkpoints")

# Reason: Define schema for incoming JSON transactions
# Must match the schema from producer service
transaction_schema = StructType([
    StructField("transaction_id", StringType(), False),
    StructField("user_id", StringType(), False),
    StructField("amount", DoubleType(), False),
    StructField("merchant_category", StringType(), False),
    StructField("timestamp", StringType(), False),  # Will convert to TimestampType
    StructField("location", StringType(), False),
    StructField("device_id", StringType(), False),
    StructField("is_fraud", BooleanType(), False)
])


def create_spark_session():
    """
    Create Spark session with Kafka integration
    
    Reason: Initializes Spark with necessary packages for Kafka streaming
    """
    return SparkSession.builder \
        .appName("TransactionFeatureEngineering") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()


def read_from_kafka(spark):
    """
    Read streaming data from Kafka topic
    
    Reason: Creates streaming DataFrame from Kafka source
    Returns raw Kafka messages that need to be parsed
    """
    return spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC_RAW) \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
        .load()


def parse_transactions(kafka_df):
    """
    Parse JSON from Kafka value field
    
    Reason: Extracts and parses JSON transaction data from Kafka messages
    Converts timestamp string to TimestampType for time-based operations
    """
    # Reason: Parse JSON from Kafka value field
    parsed_df = kafka_df.select(
        from_json(col("value").cast("string"), transaction_schema).alias("data")
    ).select("data.*")
    
    # Reason: Convert timestamp string to TimestampType
    # This is required for time-based feature extraction
    parsed_df = parsed_df.withColumn(
        "timestamp",
        col("timestamp").cast(TimestampType())
    )
    
    return parsed_df


def calculate_time_features(df):
    """
    Calculate time-based features
    
    Reason: Extracts hour_of_day and day_of_week from timestamp
    These are simple features that don't require windowing
    """
    # Reason: Extract hour (0-23) from timestamp
    df = df.withColumn("hour_of_day", hour(col("timestamp")))
    
    # Reason: Extract day of week (1=Sunday, 7=Saturday in Spark)
    # Convert to 0-6 where 0=Monday for consistency
    df = df.withColumn(
        "day_of_week",
        (dayofweek(col("timestamp")) + 5) % 7
    )
    
    return df


def calculate_windowed_features(df):
    """
    Calculate windowed aggregation features per user
    
    Reason: Computes user-level statistics over time windows
    - amount_zscore: Detects anomalous transaction amounts
    - transactions_last_hour: Detects rapid-fire patterns
    """
    # Reason: Add watermark for handling late data
    # 10 minute watermark allows late-arriving events
    df_with_watermark = df.withWatermark("timestamp", "10 minutes")
    
    # Reason: Calculate user-level statistics over 24-hour window
    # This provides context for z-score calculation
    user_stats = df_with_watermark.groupBy(
        col("user_id"),
        window(col("timestamp"), "24 hours", "1 hour")
    ).agg(
        avg("amount").alias("mean_amount"),
        stddev("amount").alias("stddev_amount")
    )
    
    # Reason: Join statistics back to original transactions
    # Use window join to match transactions with their statistics
    # Explicitly select columns to avoid duplicate user_id from join
    # Avoid ambiguous column references by explicitly qualifying every selected column
    # Use the original df's column names and fully qualify them with alias "t"
    df_with_stats = df.alias("t").join(
        user_stats.alias("s"),
        (col("t.user_id") == col("s.user_id")) &
        (col("t.timestamp") >= col("s.window.start")) &
        (col("t.timestamp") < col("s.window.end")),
        "left"
    ).select(*[col(f"t.{c}") for c in df.columns], col("s.mean_amount"), col("s.stddev_amount"))
    
    # Reason: Calculate z-score: (amount - mean) / stddev
    # Handle cases where stddev is 0 or null (single transaction)
    df_with_stats = df_with_stats.withColumn(
        "amount_zscore",
        when(
            (col("stddev_amount").isNull()) | (col("stddev_amount") == 0),
            lit(0.0)
        ).otherwise(
            (col("amount") - col("mean_amount")) / col("stddev_amount")
        )
    )
    
    # Reason: Calculate transaction count in last hour per user
    # Uses sliding window: 1 hour window, 5 minute slide
    hourly_counts = df_with_watermark.groupBy(
        col("user_id"),
        window(col("timestamp"), "1 hour", "5 minutes")
    ).agg(
        count("*").alias("tx_count")
    )
    
    # Reason: Join hourly counts back to transactions
    # Explicitly select columns to avoid duplicate user_id
    # When joining counts back, explicitly qualify t2 columns and only include h.tx_count
    df_enriched = df_with_stats.alias("t2").join(
        hourly_counts.alias("h"),
        (col("t2.user_id") == col("h.user_id")) &
        (col("t2.timestamp") >= col("h.window.start")) &
        (col("t2.timestamp") < col("h.window.end")),
        "left"
    ).select(*[col(f"t2.{c}") for c in df_with_stats.columns], col("h.tx_count"))
    
    # Reason: Rename and select final columns
    df_enriched = df_enriched.withColumn(
        "transactions_last_hour",
        when(col("tx_count").isNull(), lit(1)).otherwise(col("tx_count"))
    )
    
    # Reason: Select only the original columns plus new features
    # Drop intermediate columns from joins
    final_columns = [
        "transaction_id",
        "user_id",
        "amount",
        "merchant_category",
        "timestamp",
        "location",
        "device_id",
        "is_fraud",
        "hour_of_day",
        "day_of_week",
        "amount_zscore",
        "transactions_last_hour"
    ]
    
    # Also calculate 1-minute transaction count (hot feature) using windowed counts
    minute_counts = df_with_watermark.groupBy(
        col("user_id"),
        window(col("timestamp"), "1 minute", "10 seconds")
    ).agg(
        count("*").alias("tx_count_1min")
    )

    df_final = df_enriched.alias("t3").join(
        minute_counts.alias("m"),
        (col("t3.user_id") == col("m.user_id")) &
        (col("t3.timestamp") >= col("m.window.start")) &
        (col("t3.timestamp") < col("m.window.end")),
        "left"
    ).select(*[col(f"t3.{c}") for c in df_enriched.columns], col("m.tx_count_1min"))

    # Default tx_count_1min -> 1
    df_final = df_final.withColumn(
        "tx_count_1min",
        when(col("tx_count_1min").isNull(), lit(1)).otherwise(col("tx_count_1min"))
    )

    return df_final.select(*final_columns, "tx_count_1min")


def write_to_kafka(df):
    """
    Write enriched data to Kafka topic
    
    Reason: Serializes enriched transactions to JSON and writes to output topic
    Uses checkpointing for exactly-once semantics
    """
    # For operational needs we want to:
    # 1) Write the enriched/lightweight message to transactions.preprocessed (existing)
    # 2) Persist hot features (tx_count_1min) to Redis for the online feature store
    # 3) Emit heavy-feature enriched messages to transactions.level2 for Level 2 processing

    # Configure external clients (these will run inside the driver for foreachBatch)
    redis_url = os.getenv("REDIS_URL", "redis://airflow-redis:6379/0")
    redis_client = redis.from_url(redis_url)
    kafka_producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","), linger_ms=5)

    def foreach_batch(batch_df, epoch_id):
        # Convert this micro-batch to JSON records in the driver and side-effect
        # - write hot features into Redis
        # - push heavy-feature messages into transactions.level2
        if batch_df.rdd.isEmpty():
            return

        # Collect a small batch of rows (careful with large batches)
        rows = batch_df.toJSON().collect()

        for r in rows:
            try:
                obj = json.loads(r)
            except Exception:
                continue

            user = obj.get("user_id")
            tx_id = obj.get("transaction_id")
            # write hot feature to redis (keyed per user)
            try:
                key = f"features:user:{user}:tx_count_1min"
                redis_client.set(key, int(obj.get("tx_count_1min", 0)))
                redis_client.expire(key, 120)  # short TTL for hot features
            except Exception:
                pass

            # Build heavy-feature payload (session/graph placeholders)
            heavy_payload = {
                "transaction_id": tx_id,
                "user_id": user,
                "device_id": obj.get("device_id"),
                "amount": obj.get("amount"),
                "timestamp": obj.get("timestamp"),
                # Add heavier features to be consumed by Level 2 jobs
                "session_features": {
                    "session_length": obj.get("transactions_last_hour", 0),
                    "recent_amounts": []
                },
                "graph_features": {
                    "neighbor_count": 0,
                    "graph_score": 0.0
                }
            }

            try:
                kafka_producer.send(KAFKA_TOPIC_LEVEL2, json.dumps(heavy_payload).encode("utf-8"))
            except Exception:
                pass

        # Flush
        try:
            kafka_producer.flush()
        except Exception:
            pass

    query = df.select(to_json(struct(*[col(c) for c in df.columns])).alias("value")) \
        .writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("topic", KAFKA_TOPIC_PREPROCESSED) \
        .option("checkpointLocation", CHECKPOINT_DIR) \
        .outputMode("append") \
        .start()

    # Also kick off a foreachBatch on the enriched dataframe itself to handle redis/kafka level2 side-effects
    df.writeStream \ 
        .foreachBatch(foreach_batch) \
        .option("checkpointLocation", CHECKPOINT_DIR + "/side-effects") \
        .outputMode("append") \
        .start()

    return query


def main():
    """
    Main entry point for Spark Streaming application
    
    Reason: Orchestrates the entire streaming pipeline
    """
    print("=" * 80)
    print("Starting Spark Structured Streaming - Transaction Feature Engineering")
    print("=" * 80)
    print(f"Kafka Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Input Topic: {KAFKA_TOPIC_RAW}")
    print(f"Output Topic: {KAFKA_TOPIC_PREPROCESSED}")
    print(f"Checkpoint Directory: {CHECKPOINT_DIR}")
    print("=" * 80)
    
    # Reason: Create Spark session
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    
    try:
        # Reason: Build streaming pipeline
        # 1. Read from Kafka
        kafka_df = read_from_kafka(spark)
        print("✓ Connected to Kafka source")
        
        # 2. Parse JSON transactions
        transactions_df = parse_transactions(kafka_df)
        print("✓ Configured JSON parsing")
        
        # 3. Calculate time-based features
        transactions_with_time = calculate_time_features(transactions_df)
        print("✓ Configured time-based features")
        
        # 4. Calculate windowed features
        enriched_df = calculate_windowed_features(transactions_with_time)
        print("✓ Configured windowed aggregations")
        
        # 5. Write to Kafka
        query = write_to_kafka(enriched_df)
        print("✓ Started streaming query")
        print("=" * 80)
        print("Streaming query is running. Press Ctrl+C to stop.")
        print("=" * 80)
        
        # Reason: Wait for termination
        query.awaitTermination()
        
    except KeyboardInterrupt:
        print("\nStopping streaming query...")
    except Exception as e:
        print(f"Error in streaming application: {e}")
        raise
    finally:
        spark.stop()
        print("Spark session stopped")


if __name__ == "__main__":
    main()
