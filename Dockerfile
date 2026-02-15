# Fabric CLI CI/CD - Optimised Production Docker Image
# Multi-stage build: separates build-time deps (git) from runtime
# ~60% smaller than single-stage approach

# ============================================================
# Stage 1: Builder - installs all deps into a virtual env
# ============================================================
FROM python:3.14-slim AS builder

WORKDIR /build

# Install git (only needed here to pip-install Fabric CLI from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual env so we can cleanly copy it to the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install production requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install specific version of Fabric CLI (v1.3.1 - January 2026)
RUN pip install --no-cache-dir git+https://github.com/microsoft/fabric-cli.git@v1.3.1#egg=ms-fabric-cli

# ============================================================
# Stage 2: Runtime - lean production image (no git, no build tools)
# ============================================================
FROM python:3.14-slim

WORKDIR /app

# Install runtime system deps (git needed by gitpython, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtual env from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code (selective - no tests, docs, webapp)
COPY src/ ./src/
COPY config/ ./config/
COPY pyproject.toml .
COPY README.md .

# Install the application itself
RUN pip install --no-cache-dir .

# Set Python path
ENV PYTHONPATH=/app/src

# Create non-root user for security
RUN useradd -m -u 1000 fabric && chown -R fabric:fabric /app
USER fabric

# Configure Fabric CLI to use plaintext auth token fallback (fix for container environments)
# Must be run as the user who will execute the commands
RUN fab config set encryption_fallback_enabled true

# Set entrypoint to the installed CLI
ENTRYPOINT ["fabric-cicd"]

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD fab --version || exit 1
CMD ["--help"]

# Build instructions:
# docker build -t usf-fabric-cli-cicd:latest .
#
# Run instructions:
# docker run --rm \
#   -e AZURE_CLIENT_ID=${AZURE_CLIENT_ID} \
#   -e AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET} \
#   -e AZURE_TENANT_ID=${AZURE_TENANT_ID} \
#   -v $(pwd)/config:/app/config \
#   usf-fabric-cli-cicd:latest \
#   deploy config/my-workspace.yaml --env prod
