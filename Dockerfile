# Best practice: Define uv version as an argument for flexibility and reproducibility
ARG UV_VERSION=0.7.18

# Stage 1: builder - for installing dependencies and the project
FROM python:3.13-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy only the dependency definition files first for better caching
COPY pyproject.toml uv.lock ./

# Install project dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable --compile-bytecode

# Copy the entire backend source code into the builder stage
# We copy 'backend' specifically, not everything with '.'
COPY ./backend /app

# Sync the project itself into the environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --compile-bytecode

# Stage 2: final - a minimal image
FROM python:3.13-slim-bookworm

# Set working directory
WORKDIR /app

# Copy only the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy the source code from the builder stage
COPY --from=builder /app/app /app/app

# Ensure the installed binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port
EXPOSE 8000

# Start the FastAPI server
# Your main.py is inside the 'app' directory, so the import path is 'app.main'
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]