# syntax=docker/dockerfile:1.7
# Multi-stage build using uv for fast, reproducible images.
# Final image: python:3.11-slim + read-only app + non-root user.

# ── Builder ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Pin uv to a known version (matches the lockfile environment)
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app

# UV_COMPILE_BYTECODE  — precompile .pyc for faster cold-start
# UV_LINK_MODE=copy    — host filesystems often lack hardlink support inside Docker
# UV_PROJECT_ENVIRONMENT — explicit venv location for the copy-step in the runtime stage
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Install dependencies first (cached layer) without project source
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Install the project itself in a second cached layer
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── Runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Create a non-root user
RUN groupadd --system app && \
    useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Copy the prebuilt virtualenv + source from the builder
COPY --from=builder --chown=app:app /app /app

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CVE_LOG_FILE="" \
    CVE_LOG_JSON=true

USER app

EXPOSE 8000

# Liveness probe — hit the public /api/health endpoint via the venv's httpx
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import httpx, sys; r = httpx.get('http://127.0.0.1:8000/api/health', timeout=3); sys.exit(0 if r.status_code == 200 else 1)" || exit 1

CMD ["python", "-m", "src", "serve", "--host", "0.0.0.0", "--port", "8000"]
