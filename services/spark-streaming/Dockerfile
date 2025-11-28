# Reason: Custom Dockerfile for Spark Streaming
# Based on Python slim image with Java installed manually
# This avoids issues with finding specific Bitnami Spark tags

FROM python:3.11-slim-bookworm

# Reason: Install Java (required for Spark) and procps (for ps command used by Spark)
# Using default-jre-headless for better compatibility
RUN apt-get update && \
    apt-get install -y default-jre-headless procps && \
    rm -rf /var/lib/apt/lists/*

# Reason: Set JAVA_HOME environment variable
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Reason: Install PySpark
# This includes the Spark runtime and spark-submit binary
RUN pip install --no-cache-dir pyspark==3.5.0

# Reason: Create checkpoint directory
RUN mkdir -p /opt/spark/checkpoints

# Reason: Set working directory
WORKDIR /app

# Reason: Copy application code
COPY . .

# Reason: Run Spark application
# --packages downloads the Kafka connector jar at runtime
CMD ["spark-submit", "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0", "--master", "local[*]", "main.py"]
