# Multi-stage lightweight Dockerfile for Self-Healing Cloud Deployment Pipelines Orchestrator
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    APP_CORPUS_DIR=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and configurations
COPY config/ ./config/
COPY src/ ./src/
COPY run_server.py .
COPY README.md .

# Expose FastAPI and WebSocket dashboard port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/status || exit 1

# Run self-healing orchestrator server
CMD ["python", "run_server.py"]
