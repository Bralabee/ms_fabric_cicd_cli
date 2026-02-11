# Webapp Makefile for Fabric CLI CI/CD Interactive Guide

.PHONY: help dev stop backend frontend install test clean docker-build docker-up docker-down docker-logs

# Colors
GREEN = \033[0;32m
YELLOW = \033[1;33m
NC = \033[0m

help:
	@echo "$(GREEN)Fabric CLI CI/CD - Interactive Guide$(NC)"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make dev       - Start both backend and frontend in development mode"
	@echo "  make backend   - Start backend only (port 8001)"
	@echo "  make frontend  - Start frontend only (port 5173)"
	@echo "  make stop      - Stop any running development servers"
	@echo "  make install   - Install all dependencies"
	@echo ""
	@echo "$(YELLOW)Docker (Local):$(NC)"
	@echo "  make docker-build   - Build Docker images"
	@echo "  make docker-up      - Start containers (http://localhost:8080)"
	@echo "  make docker-down    - Stop and remove containers"
	@echo "  make docker-logs    - View container logs"
	@echo "  make docker-status  - Show container status"
	@echo "  make docker-clean   - Remove images and volumes"
	@echo ""
	@echo "$(YELLOW)Azure Deployment:$(NC)"
	@echo "  make deploy-azure        - Deploy to Azure Container Apps"
	@echo "  make deploy-azure-dryrun - Preview Azure deployment"
	@echo ""
	@echo "$(YELLOW)Testing:$(NC)"
	@echo "  make test          - Run all tests"
	@echo "  make test-backend  - Run backend tests only"
	@echo "  make test-frontend - Run frontend type checking"
	@echo ""
	@echo "$(YELLOW)Build:$(NC)"
	@echo "  make build     - Build frontend for production"
	@echo "  make clean     - Clean build artifacts"

install:
	@echo "$(GREEN)Installing backend dependencies...$(NC)"
	cd backend && pip install -r requirements-dev.txt
	@echo "$(GREEN)Installing frontend dependencies...$(NC)"
	cd frontend && npm install

backend:
	@echo "$(GREEN)Starting backend on port 8001...$(NC)"
	cd backend && uvicorn app.main:app --reload --port 8001

frontend:
	@echo "$(GREEN)Starting frontend on port 5173...$(NC)"
	cd frontend && npm run dev

dev:
	@echo "$(GREEN)Starting development servers...$(NC)"
	@echo "Backend: http://localhost:8001"
	@echo "Frontend: http://localhost:5173"
	@echo ""
	@echo "$(YELLOW)Press Ctrl+C to stop both servers$(NC)"
	@echo ""
	@trap 'kill 0' INT; \
	(cd backend && uvicorn app.main:app --reload --port 8001) & \
	(cd frontend && npm run dev) & \
	wait

stop:
	@echo "$(GREEN)Stopping any running servers...$(NC)"
	-@pkill -f "uvicorn app.main" 2>/dev/null || true
	-@pkill -f "vite" 2>/dev/null || true
	@echo "Servers stopped"

test: test-backend test-frontend

test-backend:
	@echo "$(GREEN)Running backend tests...$(NC)"
	cd backend && PYTHONPATH=. pytest tests/ -v

test-frontend:
	@echo "$(GREEN)Running frontend type check...$(NC)"
	cd frontend && npm run build

build:
	@echo "$(GREEN)Building frontend for production...$(NC)"
	cd frontend && npm run build

clean:
	@echo "$(GREEN)Cleaning build artifacts...$(NC)"
	rm -rf frontend/dist
	rm -rf backend/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true

# Docker commands
docker-build:
	@echo "$(GREEN)Building Docker images...$(NC)"
	docker compose build

docker-up:
	@echo "$(GREEN)Starting Docker containers...$(NC)"
	@echo "Application will be available at http://localhost:8080"
	docker compose up -d
	@echo ""
	@echo "$(YELLOW)Waiting for services to be healthy...$(NC)"
	@sleep 5
	@docker compose ps

docker-down:
	@echo "$(GREEN)Stopping Docker containers...$(NC)"
	docker compose down

docker-logs:
	@echo "$(GREEN)Showing container logs...$(NC)"
	docker compose logs -f

docker-restart:
	@echo "$(GREEN)Restarting containers...$(NC)"
	docker compose restart

docker-clean:
	@echo "$(GREEN)Removing Docker images and volumes...$(NC)"
	docker compose down --rmi all --volumes --remove-orphans

docker-status:
	@docker compose ps

# Azure Deployment
deploy-azure:
	@echo "$(GREEN)Deploying to Azure Container Apps...$(NC)"
	@chmod +x deploy-azure.sh
	./deploy-azure.sh

deploy-azure-dryrun:
	@echo "$(GREEN)Azure deployment dry run...$(NC)"
	@chmod +x deploy-azure.sh
	./deploy-azure.sh --dry-run
