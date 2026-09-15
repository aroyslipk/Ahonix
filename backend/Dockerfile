# ==============================================================================
# AHONIX Backend — Production Dockerfile
# ==============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install minimal OS dependencies for health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency requirements
COPY requirements.txt .

# Install dependencies
# Handles public PyPI builds gracefully while supporting the full stack
RUN grep -v "emergentintegrations" requirements.txt | grep -v "customer-assets.emergentagent.com" > /tmp/reqs-pypi.txt && \
    pip install --no-cache-dir -r /tmp/reqs-pypi.txt || pip install --no-cache-dir -r requirements.txt


# Copy backend source code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck probe using curl against /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
