#!/bin/bash
# Setup script for Fabric CI/CD project

set -e

echo "🚀 Setting up Fabric CI/CD project..."

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Conda not found. Please install Anaconda or Miniconda first."
    echo "   https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Create conda environment
echo "📦 Creating conda environment..."
conda env create -f environment.yml

echo "✅ Conda environment 'fabric-cli-cicd' created successfully!"

# Activate environment and install pip dependencies
echo "📦 Installing additional dependencies..."
conda run -n fabric-cli-cicd pip install -r requirements.txt

# Create .env file from template
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.template .env
    echo "⚠️  Please edit .env file with your actual values:"
    echo "   - FABRIC_TOKEN: Your Fabric authentication token"
    echo "   - TENANT_ID: Your Azure tenant ID"
    echo "   - Other organization-specific settings"
fi

# Create audit logs directory
mkdir -p audit_logs

echo "🔍 Running Fabric CLI preflight checks..."
conda run -n fabric-cli-cicd python scripts/preflight_check.py --auto-install --skip-env-check

echo ""
echo "🎉 Setup complete! Next steps:"
echo ""
echo "1. Activate the environment:"
echo "   conda activate fabric-cli-cicd"
echo ""
echo "2. Edit .env file with your credentials:"
echo "   vim .env"
echo ""
echo "3. Install Fabric CLI if not already installed"
echo ""
echo "4. Validate your setup:"
echo "   python src/fabric_deploy.py diagnose"
echo ""
echo "5. Test with a configuration:"
echo "   python src/fabric_deploy.py validate config/templates/basic_etl.yaml"
echo ""
echo "6. Deploy to development:"
echo "   python src/fabric_deploy.py deploy config/templates/basic_etl.yaml --env dev"
echo ""
echo "Happy deploying! 🚀"