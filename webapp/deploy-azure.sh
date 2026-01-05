#!/bin/bash
# =============================================================================
# Fabric CLI CI/CD Interactive Guide - Azure Deployment Script
# =============================================================================
# This script deploys the webapp to Azure Container Apps
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Docker installed and running
#   - Sufficient Azure permissions (Contributor on subscription/resource group)
#
# Usage:
#   ./deploy-azure.sh [options]
#
# Options:
#   -n, --name NAME          Resource name prefix (default: fabric-cli-guide)
#   -l, --location LOCATION  Azure region (default: eastus)
#   -g, --resource-group RG  Resource group name (default: {name}-rg)
#   -t, --tag TAG            Image tag (default: latest)
#   --skip-build             Skip Docker build (use existing images)
#   --dry-run                Show what would be done without executing
#   -h, --help               Show this help message
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
NAME_PREFIX="fabric-cli-guide"
LOCATION="eastus"
TAG="latest"
SKIP_BUILD=false
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            NAME_PREFIX="$2"
            shift 2
            ;;
        -l|--location)
            LOCATION="$2"
            shift 2
            ;;
        -g|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            head -30 "$0" | tail -25
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Derived names
RESOURCE_GROUP="${RESOURCE_GROUP:-${NAME_PREFIX}-rg}"
ACR_NAME=$(echo "${NAME_PREFIX}acr" | tr -d '-' | tr '[:upper:]' '[:lower:]')
BACKEND_IMAGE="${ACR_NAME}.azurecr.io/fabric-cli-guide-backend:${TAG}"
FRONTEND_IMAGE="${ACR_NAME}.azurecr.io/fabric-cli-guide-frontend:${TAG}"
CONTAINER_ENV="${NAME_PREFIX}-env"
BACKEND_APP="${NAME_PREFIX}-backend"
FRONTEND_APP="${NAME_PREFIX}-frontend"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $*"
    else
        "$@"
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Please install: https://docs.microsoft.com/cli/azure/install-azure-cli"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker."
        exit 1
    fi
    
    # Check Azure login
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Please run 'az login' first."
        exit 1
    fi
    
    log_success "All prerequisites met"
}

# Print deployment summary
print_summary() {
    echo ""
    echo -e "${GREEN}=== Deployment Configuration ===${NC}"
    echo "Resource Group:     $RESOURCE_GROUP"
    echo "Location:           $LOCATION"
    echo "ACR Name:           $ACR_NAME"
    echo "Container Env:      $CONTAINER_ENV"
    echo "Backend App:        $BACKEND_APP"
    echo "Frontend App:       $FRONTEND_APP"
    echo "Image Tag:          $TAG"
    echo ""
}

# Create resource group
create_resource_group() {
    log_info "Creating resource group '$RESOURCE_GROUP' in '$LOCATION'..."
    run_cmd az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none
    log_success "Resource group created"
}

# Create Azure Container Registry
create_acr() {
    log_info "Creating Azure Container Registry '$ACR_NAME'..."
    run_cmd az acr create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --sku Basic \
        --admin-enabled true \
        --output none
    log_success "ACR created"
}

# Build and push images
build_and_push_images() {
    if [ "$SKIP_BUILD" = true ]; then
        log_warning "Skipping image build (--skip-build specified)"
        return
    fi
    
    log_info "Building and pushing Docker images..."
    
    # Get ACR credentials
    ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query "username" -o tsv)
    ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)
    
    # Login to ACR
    echo "$ACR_PASSWORD" | docker login "${ACR_NAME}.azurecr.io" -u "$ACR_USERNAME" --password-stdin
    
    # Build backend
    log_info "Building backend image..."
    run_cmd docker build -t "$BACKEND_IMAGE" ./backend
    run_cmd docker push "$BACKEND_IMAGE"
    log_success "Backend image pushed"
    
    # Build frontend
    log_info "Building frontend image..."
    run_cmd docker build -t "$FRONTEND_IMAGE" ./frontend
    run_cmd docker push "$FRONTEND_IMAGE"
    log_success "Frontend image pushed"
}

# Create Container Apps Environment
create_container_env() {
    log_info "Creating Container Apps Environment '$CONTAINER_ENV'..."
    run_cmd az containerapp env create \
        --name "$CONTAINER_ENV" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none
    log_success "Container Apps Environment created"
}

# Deploy backend container app
deploy_backend() {
    log_info "Deploying backend container app..."
    
    ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query "username" -o tsv)
    ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)
    
    run_cmd az containerapp create \
        --name "$BACKEND_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --environment "$CONTAINER_ENV" \
        --image "$BACKEND_IMAGE" \
        --registry-server "${ACR_NAME}.azurecr.io" \
        --registry-username "$ACR_USERNAME" \
        --registry-password "$ACR_PASSWORD" \
        --target-port 8001 \
        --ingress internal \
        --min-replicas 1 \
        --max-replicas 3 \
        --cpu 0.5 \
        --memory 1.0Gi \
        --env-vars "CORS_ORIGINS=*" \
        --output none
    
    # Get backend FQDN
    BACKEND_FQDN=$(az containerapp show \
        --name "$BACKEND_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" -o tsv)
    
    log_success "Backend deployed at: $BACKEND_FQDN"
}

# Deploy frontend container app
deploy_frontend() {
    log_info "Deploying frontend container app..."
    
    ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query "username" -o tsv)
    ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)
    
    run_cmd az containerapp create \
        --name "$FRONTEND_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --environment "$CONTAINER_ENV" \
        --image "$FRONTEND_IMAGE" \
        --registry-server "${ACR_NAME}.azurecr.io" \
        --registry-username "$ACR_USERNAME" \
        --registry-password "$ACR_PASSWORD" \
        --target-port 80 \
        --ingress external \
        --min-replicas 1 \
        --max-replicas 5 \
        --cpu 0.25 \
        --memory 0.5Gi \
        --output none
    
    # Get frontend URL
    FRONTEND_URL=$(az containerapp show \
        --name "$FRONTEND_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" -o tsv)
    
    log_success "Frontend deployed at: https://$FRONTEND_URL"
}

# Main execution
main() {
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║    Fabric CLI CI/CD Interactive Guide - Azure Deployment      ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_prerequisites
    print_summary
    
    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN MODE - No changes will be made"
    fi
    
    read -p "Proceed with deployment? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deployment cancelled"
        exit 0
    fi
    
    create_resource_group
    create_acr
    build_and_push_images
    create_container_env
    deploy_backend
    deploy_frontend
    
    echo ""
    echo -e "${GREEN}=== Deployment Complete ===${NC}"
    echo ""
    echo "Your application is available at:"
    FRONTEND_URL=$(az containerapp show \
        --name "$FRONTEND_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null || echo "pending...")
    echo -e "  ${BLUE}https://$FRONTEND_URL${NC}"
    echo ""
    echo "To tear down resources:"
    echo "  az group delete --name $RESOURCE_GROUP --yes --no-wait"
    echo ""
}

# Run main
cd "$(dirname "$0")"
main
