# Reason: Multi-stage build for FastAPI backend
# Uses Python 3.11 slim image for smaller size

FROM python:3.11-slim

# Reason: Set working directory for application
WORKDIR /app

# Reason: Copy requirements first for better Docker layer caching
# Dependencies only rebuild if requirements.txt changes
COPY requirements.txt .

# Reason: Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Reason: Copy application code
COPY . .

# Reason: Create directory for RSA keys
# Keys will be generated on first run
RUN mkdir -p keys

# Reason: Expose port 8000 for FastAPI/Uvicorn
EXPOSE 8000

# Reason: Run FastAPI with Uvicorn ASGI server
# --host 0.0.0.0 allows external connections
# --reload disabled for production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
