# Dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Final stage
FROM python:3.13-slim

WORKDIR /app

# Copy only the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application
COPY main.py ./

# Run as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Use venv python directly
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "main.py"]