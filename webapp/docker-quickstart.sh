#!/bin/bash
# =============================================================================
# Quick Start Script - Build and Run Docker Containers Locally
# =============================================================================
# This script builds and runs the webapp in Docker for local testing
# before deploying to Azure or sharing with others.
#
# Usage:
#   ./docker-quickstart.sh [command]
#
# Commands:
#   build    Build Docker images
#   up       Start containers (detached)
#   down     Stop and remove containers
#   logs     View container logs
#   status   Show container status
#   clean    Remove images and volumes
#   help     Show this help
#
# Default (no command): build + up
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd "$(dirname "$0")"

case "${1:-default}" in
    build)
        echo -e "${GREEN}Building Docker images...${NC}"
        docker compose build
        echo -e "${GREEN}Build complete!${NC}"
        ;;
    
    up)
        echo -e "${GREEN}Starting containers...${NC}"
        docker compose up -d
        echo ""
        echo -e "${GREEN}Containers started!${NC}"
        echo -e "Frontend: ${BLUE}http://localhost:8080${NC}"
        echo -e "Backend:  ${BLUE}http://localhost:8001${NC}"
        echo ""
        echo "Run './docker-quickstart.sh logs' to view logs"
        ;;
    
    down)
        echo -e "${YELLOW}Stopping containers...${NC}"
        docker compose down
        echo -e "${GREEN}Containers stopped${NC}"
        ;;
    
    logs)
        docker compose logs -f
        ;;
    
    status)
        echo -e "${GREEN}Container Status:${NC}"
        docker compose ps
        ;;
    
    clean)
        echo -e "${YELLOW}Removing containers, images, and volumes...${NC}"
        docker compose down --rmi all --volumes --remove-orphans
        echo -e "${GREEN}Cleanup complete${NC}"
        ;;
    
    help|-h|--help)
        head -22 "$0" | tail -17
        ;;
    
    default)
        echo -e "${GREEN}"
        echo "╔═══════════════════════════════════════════════════════════════╗"
        echo "║    Fabric CLI CI/CD Interactive Guide - Docker Quick Start    ║"
        echo "╚═══════════════════════════════════════════════════════════════╝"
        echo -e "${NC}"
        echo -e "${GREEN}Building Docker images...${NC}"
        docker compose build
        echo ""
        echo -e "${GREEN}Starting containers...${NC}"
        docker compose up -d
        echo ""
        echo -e "${GREEN}✓ Webapp is running!${NC}"
        echo ""
        echo -e "Open in browser: ${BLUE}http://localhost:8080${NC}"
        echo ""
        echo "Commands:"
        echo "  ./docker-quickstart.sh logs    - View logs"
        echo "  ./docker-quickstart.sh down    - Stop containers"
        echo "  ./docker-quickstart.sh status  - Show status"
        ;;
    
    *)
        echo "Unknown command: $1"
        echo "Run './docker-quickstart.sh help' for usage"
        exit 1
        ;;
esac
