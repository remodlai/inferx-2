# Dockerfile for InferX StateSvc
# Runs Temporal worker + gRPC server in single container

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src ./src
COPY proto ./proto
COPY .env .env

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Install dependencies
RUN uv pip install --system -e .

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Expose gRPC port
EXPOSE 1237

# Run the combined worker + gRPC server
CMD ["python", "-m", "src.main"]
