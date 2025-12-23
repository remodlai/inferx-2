# Dockerfile for InferX StateSvc
# Runs Temporal worker + gRPC server in single container

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy inferx-common (shared library)
COPY inferx-common /app/inferx-common

# Copy project files
COPY statesvc/pyproject.toml ./
COPY statesvc/README.md ./
COPY statesvc/src ./src
COPY statesvc/proto ./proto
COPY statesvc/.env .env

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Install inferx-common first
RUN uv pip install --system /app/inferx-common

# Install statesvc as proper package (not editable)
RUN uv pip install --system .

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Add /app to Python path so imports work
ENV PYTHONPATH=/app

# Expose gRPC port
EXPOSE 1237

# Run the combined worker + gRPC server as module
CMD ["python", "-m", "src.main"]
