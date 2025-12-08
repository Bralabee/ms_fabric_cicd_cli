# Fabric CLI CI/CD - Production Docker Image
# Addresses Gap A: Dependency on External CLI by pinning specific versions

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with pinned versions
# This ensures reproducible builds across environments
RUN pip install --no-cache-dir -r requirements.txt

# Install specific version of Fabric CLI
# TODO: Update this to pin a specific version once Fabric CLI has releases
# For now, install from main but document the commit hash
RUN pip install --no-cache-dir git+https://github.com/microsoft/fabric-cli.git@main#egg=ms-fabric-cli

# Verify Fabric CLI installation
RUN fab --version

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY templates/ ./templates/
COPY scripts/ ./scripts/

# Set Python path
ENV PYTHONPATH=/app

# Create non-root user for security
RUN useradd -m -u 1000 fabric && chown -R fabric:fabric /app
USER fabric

# Configure Fabric CLI to use plaintext auth token fallback (fix for container environments)
# Must be run as the user who will execute the commands
RUN fab config set encryption_fallback_enabled true

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD fab --version || exit 1

# Default command
ENTRYPOINT ["python", "src/fabric_deploy.py"]
CMD ["--help"]

# Build instructions:
# docker build -t usf-fabric-cli-cicd:latest .
#
# Run instructions:
# docker run --rm \
#   -e AZURE_CLIENT_ID=${AZURE_CLIENT_ID} \
#   -e AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET} \
#   -e TENANT_ID=${TENANT_ID} \
#   -v $(pwd)/config:/app/config \
#   usf-fabric-cli-cicd:latest \
#   deploy config/my-workspace.yaml --env prod
