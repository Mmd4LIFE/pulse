# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libpq is needed by psycopg (which Alembic runs its migrations over).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies are their own layer so code edits do not trigger a reinstall.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# The API writes uploads here; the volume is mounted over it at run time.
RUN mkdir -p /data/media \
    && useradd --create-home --uid 10001 pulse \
    && chown -R pulse:pulse /app /data
USER pulse

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Two workers fits the box; uvicorn workers are async so this is not the
# concurrency limit, just the number of event loops.
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", \
     "--graceful-timeout", "20", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
