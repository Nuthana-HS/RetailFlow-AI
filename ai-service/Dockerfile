# =============================================================================
# RetailFlow AI — AI Service Dockerfile
# =============================================================================
# Multi-stage build with CPU-only PyTorch (lighter image)
# For GPU support, change base image to pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Base — Python with system deps
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

# Install system dependencies for OpenCV and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip

# ---------------------------------------------------------------------------
# Stage 2: Development
# ---------------------------------------------------------------------------
FROM base AS development

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download YOLOv8 nano model weights
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" || true

COPY . .

EXPOSE 8001

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]

# ---------------------------------------------------------------------------
# Stage 3: Production
# ---------------------------------------------------------------------------
FROM base AS production

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download YOLOv8 nano model weights into the image
# This avoids downloading on every container start
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" || true

# Create non-root user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid 1001 --no-create-home appuser

COPY --chown=appuser:appgroup . .

# Create models directory for storing trained XGBoost models
RUN mkdir -p models && chown appuser:appgroup models

USER appuser

EXPOSE 8001

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "2", \
     "--log-level", "info"]
