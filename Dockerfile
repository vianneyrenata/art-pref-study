# Dockerfile for Railway deployment
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p /app/data_exports

# Railway will set PORT env var
CMD gunicorn --bind 0.0.0.0:$PORT app:app
