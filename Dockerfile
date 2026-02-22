# =============================================================================
# InsureFlow AI — Backend Dockerfile
# Multi-stage build for GCP Cloud Run
# =============================================================================

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# System build deps (compile wheels for opencv, PyMuPDF, cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    libmupdf-dev \
    mupdf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .

# Install into an isolated prefix so we can copy cleanly later
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Runtime system libraries required by packages:
#   tesseract-ocr  → pytesseract
#   libzbar0       → pyzbar (QR/barcode)
#   poppler-utils  → pdf2image
#   libgl1         → opencv-python (headless would avoid this, but keeping for ELA)
#   libglib2.0-0   → opencv dependency
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libzbar0 \
    poppler-utils \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Non-root user for security (Cloud Run runs as root by default but best practice)
RUN groupadd --gid 1001 appgroup \
 && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy application source
COPY . .

# Create writable directories for logs and storage
RUN mkdir -p /app/logs /app/storage/uploads /app/storage/encrypted \
 && chown -R appuser:appgroup /app

# Copy and make entrypoint executable
RUN chmod +x /app/scripts/entrypoint.sh

USER appuser

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
