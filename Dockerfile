# ==============================================================================
# ElasticBot Backend - Multi-Stage Production Dockerfile
# ==============================================================================
# Optimized for minimal image size and fast builds using layer caching.
# Final image: ~350MB (Python 3.11-slim base)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies and compile wheels
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Runtime - Production image with minimal footprint
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Django settings
    DJANGO_SETTINGS_MODULE=base.settings \
    # Default port
    PORT=8000

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    procps \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 elasticbot && \
    useradd --uid 1000 --gid elasticbot --shell /bin/bash --create-home elasticbot

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=elasticbot:elasticbot . .

# Create necessary directories
RUN mkdir -p /app/logs /app/staticfiles /app/media && \
    chown -R elasticbot:elasticbot /app

# Copy and setup entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Collect static files (if DEBUG=False) - as elasticbot user temporarily
USER elasticbot
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true
USER root

# Set default environment variables for supervisord
ENV PORT=8000 \
    GUNICORN_WORKERS=4 \
    GUNICORN_TIMEOUT=120 \
    CELERY_LOG_LEVEL=info \
    CELERY_CONCURRENCY=2

# Health check for container orchestrators
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/ || exit 1

# Expose port
EXPOSE ${PORT}

# Use entrypoint for setup, then start supervisord
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
