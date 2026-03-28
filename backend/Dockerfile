# ============================================================
# Riverty Contract Review — Backend Dockerfile
# Multi-stage build: builder installs deps, runtime runs app
# ============================================================

# ── Stage 1: Builder ────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install Tesseract OCR and German language pack as system dependency
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-deu \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/uploads /app/chroma_db \
    && chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser app/ ./app/

# Switch to non-root user
USER appuser

EXPOSE 8000

# Health check using the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
