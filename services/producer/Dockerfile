# Reason: Dockerfile for transaction producer
# Lightweight Python container for continuous data generation

FROM python:3.11-slim

# Reason: Set working directory
WORKDIR /app

# Reason: Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Reason: Copy producer script
COPY producer.py .

# Reason: Run producer continuously
CMD ["python", "-u", "producer.py"]
