# Multi-stage Dockerfile for buildx cross-compilation
# Stage 1: Build the Rust binary
# Start from Ubuntu 22.04 with controlled Python version, then install Rust
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /build

# Install Python 3.12 and build dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
    python3.12 \
    python3.12-dev \
    pkg-config \
    libssl-dev \
    protobuf-compiler \
    curl \
    build-essential \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy the entire source (Cargo.toml defines svc binary at svc/svc_main.rs)
COPY Cargo.toml ./
COPY inferxlib/ ./inferxlib/
COPY ixshare/ ./ixshare/
COPY svc/ ./svc/
COPY ixctl/ ./ixctl/

# Build the svc binary in release mode
RUN cargo build --release --bin svc

# Stage 2: Runtime image
FROM ubuntu:22.04

WORKDIR /

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libnuma-dev \
    fuse3 \
    libkeyutils-dev \
    libaio-dev \
    libssl-dev \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    iptables \
    uidmap \
    xz-utils \
    pigz \
    gnupg2 \
    socat \
    wget \
    vim \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Etc/UTC
ENV DEBIAN_FRONTEND=noninteractive

# Install Docker CLI (for docker-in-docker scenarios if needed)
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu jammy stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /opt/inferx/config /opt/inferx/log /opt/inferx/bin

# Copy the compiled binary from builder
COPY --from=builder /build/target/release/svc /svc

# Copy config files
COPY nodeconfig/node*.json /opt/inferx/config/
COPY onenode_logging_config.yaml /opt/inferx/config/

# Copy entrypoint
COPY deployment/svc-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/svc-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/svc-entrypoint.sh"]
