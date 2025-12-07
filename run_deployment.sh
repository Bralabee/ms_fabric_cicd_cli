#!/bin/bash

# Simple wrapper script for Fabric CI/CD Deployment
# Usage: ./run_deployment.sh <config_file> [env]

CONFIG_FILE=$1
ENV=${2:-dev}

if [ -z "$CONFIG_FILE" ]; then
    echo "Usage: ./run_deployment.sh <config_file> [env]"
    echo "Example: ./run_deployment.sh config/my_project.yaml dev"
    exit 1
fi

# Check if fabric-cicd is installed
if ! command -v fabric-cicd &> /dev/null; then
    echo "Installing fabric-cicd package..."
    pip install .
fi

# Run deployment
echo "Deploying $CONFIG_FILE to $ENV environment..."
fabric-cicd deploy "$CONFIG_FILE" --env "$ENV"
