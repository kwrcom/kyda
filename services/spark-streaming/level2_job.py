"""
Second Spark job to consume transactions.level2, perform heavy ML/graph/session processing,
and emit verdicts into level2.verdicts.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, to_json, struct, when
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, MapType
import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_LEVEL2 = os.getenv("KAFKA_TOPIC_LEVEL2", "transactions.level2")
KAFKA_TOPIC_VERDICTS = os.getenv("KAFKA_TOPIC_VERDICTS", "level2.verdicts")
CHECKPOINT_DIR = os.getenv("SPARK_CHECKPOINT_DIR", "/opt/spark/checkpoints/level2")


def create_spark_session():
    return SparkSession.builder \
        .appName("TransactionLevel2") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
        .getOrCreate()


# Schema for heavy payload
heavy_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("user_id", StringType(), True),
    StructField("device_id", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("timestamp", StringType(), True),
    StructField("session_features", MapType(StringType(), StringType()), True),
    StructField("graph_features", MapType(StringType(), StringType()), True)
])


def main():
    print("Starting Level 2 Spark Job -> reading transactions.level2")
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    raw = spark.readStream.format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC_LEVEL2) \
        .option("startingOffsets", "earliest") \
        .load()

    parsed = raw.select(from_json(col("value").cast("string"), heavy_schema).alias("data")).select("data.*")

    # Very simple heavy-scoring logic implemented in SQL expressions
    # Convert placeholder features into numeric values if present
    scored = parsed.withColumn("neighbor_count", when(col("graph_features").isNotNull(), col("graph_features")["neighbor_count"]).otherwise(0).cast(DoubleType())) \
        .withColumn("graph_score", when(col("graph_features").isNotNull(), col("graph_features")["graph_score"]).otherwise(0).cast(DoubleType()))

    # implement a heuristic heavy score (0-1)
    scored = scored.withColumn(
        "heavy_score",
        (col("neighbor_count") / 10.0) + (col("graph_score")) + when(col("amount") > 0, (col("amount") / 10000.0)).otherwise(0.0)
    )

    # clamp to [0,1]
    scored = scored.withColumn(
        "heavy_score_clamped",
        when(col("heavy_score") < 0, 0.0).when(col("heavy_score") > 1, 1.0).otherwise(col("heavy_score"))
    )

    # verdict based on the same thresholds
    scored = scored.withColumn(
        "verdict",
        when(col("heavy_score_clamped") < 0.2, "Allow").when(col("heavy_score_clamped") < 0.6, "Challenge").otherwise("Quarantine")
    )

    output = scored.select(to_json(struct("transaction_id", "user_id", "device_id", "amount", "timestamp", "heavy_score_clamped", "verdict")).alias("value"))

    query = output.writeStream.format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("topic", KAFKA_TOPIC_VERDICTS) \
        .option("checkpointLocation", CHECKPOINT_DIR) \
        .outputMode("append") \
        .start()

    query.awaitTermination()


if __name__ == "__main__":
    main()
