# =============================================================================
# RetailFlow AI — Backend Dockerfile
# =============================================================================
# Multi-stage build:
#   1. base        → Python base with system deps
#   2. development → Hot reload with all dev dependencies
#   3. production  → Minimal production image with gunicorn
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Base — Python with system dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# ---------------------------------------------------------------------------
# Stage 2: Development — Hot reload
# ---------------------------------------------------------------------------
FROM base AS development

# Install dev dependencies
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy source code (mounted as volume in docker-compose for hot reload)
COPY . .

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Hot reload with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]

# ---------------------------------------------------------------------------
# Stage 3: Production — Optimized runtime
# ---------------------------------------------------------------------------
FROM base AS production

# Install only production dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid 1001 --no-create-home appuser

# Copy application source
COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Gunicorn with uvicorn workers for production
# Workers = (2 × CPU cores) + 1 (standard formula)
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
