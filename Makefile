# =============================================================================
# RetailFlow AI — Makefile
# =============================================================================
# Developer convenience commands for local development.
# Usage: make <target>
# =============================================================================

.PHONY: help up down logs build migrate seed test test-backend test-frontend
.PHONY: lint lint-backend lint-frontend format shell-backend shell-db clean

# Default target — show help
.DEFAULT_GOAL := help

# Colors for output
GREEN  := \033[0;32m
YELLOW := \033[0;33m
CYAN   := \033[0;36m
RESET  := \033[0m

## ============================================================================
## Help
## ============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(CYAN)RetailFlow AI — Developer Commands$(RESET)"
	@echo "$(CYAN)====================================$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

## ============================================================================
## Docker — Local Development
## ============================================================================

up: ## Start all services (detached)
	@echo "$(CYAN)Starting RetailFlow AI services...$(RESET)"
	docker compose up -d
	@echo "$(GREEN)✓ Services started$(RESET)"
	@echo ""
	@echo "  Frontend:     http://localhost:3000"
	@echo "  Backend API:  http://localhost:8000"
	@echo "  Swagger UI:   http://localhost:8000/docs"
	@echo "  AI Service:   http://localhost:8001"
	@echo ""

down: ## Stop all services
	@echo "$(YELLOW)Stopping RetailFlow AI services...$(RESET)"
	docker compose down
	@echo "$(GREEN)✓ Services stopped$(RESET)"

down-volumes: ## Stop all services AND delete volumes (WARNING: deletes DB data)
	@echo "$(YELLOW)WARNING: This will delete all local database data!$(RESET)"
	@read -p "Are you sure? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose down -v
	@echo "$(GREEN)✓ Services and volumes removed$(RESET)"

build: ## Rebuild all Docker images (use after dependency changes)
	@echo "$(CYAN)Rebuilding Docker images...$(RESET)"
	docker compose build --no-cache
	@echo "$(GREEN)✓ Images rebuilt$(RESET)"

build-backend: ## Rebuild backend Docker image only
	docker compose build --no-cache backend

build-frontend: ## Rebuild frontend Docker image only
	docker compose build --no-cache frontend

build-ai: ## Rebuild AI service Docker image only
	docker compose build --no-cache ai-service

logs: ## Tail logs for all services (Ctrl+C to exit)
	docker compose logs -f

logs-backend: ## Tail backend logs only
	docker compose logs -f backend

logs-frontend: ## Tail frontend logs only
	docker compose logs -f frontend

logs-ai: ## Tail AI service logs only
	docker compose logs -f ai-service

ps: ## Show running service status
	docker compose ps

## ============================================================================
## Database
## ============================================================================

migrate: ## Run all pending database migrations
	@echo "$(CYAN)Running database migrations...$(RESET)"
	docker compose exec backend alembic upgrade head
	@echo "$(GREEN)✓ Migrations complete$(RESET)"

migrate-down: ## Roll back the last database migration
	@echo "$(YELLOW)Rolling back last migration...$(RESET)"
	docker compose exec backend alembic downgrade -1
	@echo "$(GREEN)✓ Rollback complete$(RESET)"

migrate-status: ## Show migration status
	docker compose exec backend alembic current

migration: ## Create a new migration file (usage: make migration name="add_user_table")
	@if [ -z "$(name)" ]; then echo "Usage: make migration name='description'"; exit 1; fi
	docker compose exec backend alembic revision --autogenerate -m "$(name)"
	@echo "$(GREEN)✓ Migration file created in backend/alembic/versions/$(RESET)"

seed: ## Seed the database with sample data
	@echo "$(CYAN)Seeding database with sample data...$(RESET)"
	docker compose exec backend python -m app.scripts.seed
	@echo "$(GREEN)✓ Database seeded$(RESET)"

reset-db: ## Drop and recreate the database (WARNING: deletes all data)
	@echo "$(YELLOW)WARNING: This will delete all database data!$(RESET)"
	@read -p "Are you sure? [y/N]: " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose exec backend alembic downgrade base
	docker compose exec backend alembic upgrade head
	@echo "$(GREEN)✓ Database reset$(RESET)"

## ============================================================================
## Testing
## ============================================================================

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests with coverage
	@echo "$(CYAN)Running backend tests...$(RESET)"
	docker compose exec backend pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html:coverage/backend
	@echo "$(GREEN)✓ Backend tests complete. Coverage: coverage/backend/index.html$(RESET)"

test-backend-unit: ## Run backend unit tests only (fast)
	docker compose exec backend pytest tests/unit/ -v

test-backend-integration: ## Run backend integration tests
	docker compose exec backend pytest tests/integration/ -v

test-frontend: ## Run frontend tests
	@echo "$(CYAN)Running frontend tests...$(RESET)"
	docker compose exec frontend npm run test -- --coverage --watchAll=false
	@echo "$(GREEN)✓ Frontend tests complete$(RESET)"

test-ai: ## Run AI service tests
	@echo "$(CYAN)Running AI service tests...$(RESET)"
	docker compose exec ai-service pytest tests/ -v
	@echo "$(GREEN)✓ AI service tests complete$(RESET)"

## ============================================================================
## Linting & Formatting
## ============================================================================

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint backend (ruff + mypy)
	@echo "$(CYAN)Linting backend...$(RESET)"
	docker compose exec backend ruff check app/ tests/
	docker compose exec backend mypy app/
	@echo "$(GREEN)✓ Backend lint passed$(RESET)"

lint-frontend: ## Lint frontend (ESLint + TypeScript)
	@echo "$(CYAN)Linting frontend...$(RESET)"
	docker compose exec frontend npm run lint
	docker compose exec frontend npm run type-check
	@echo "$(GREEN)✓ Frontend lint passed$(RESET)"

format: ## Auto-format all code (ruff + prettier)
	@echo "$(CYAN)Formatting code...$(RESET)"
	docker compose exec backend ruff format app/ tests/
	docker compose exec frontend npm run format
	@echo "$(GREEN)✓ Formatting complete$(RESET)"

## ============================================================================
## Shell Access
## ============================================================================

shell-backend: ## Open a shell in the backend container
	docker compose exec backend bash

shell-frontend: ## Open a shell in the frontend container
	docker compose exec frontend sh

shell-ai: ## Open a shell in the AI service container
	docker compose exec ai-service bash

shell-db: ## Open a PostgreSQL shell
	docker compose exec postgres psql -U ${POSTGRES_USER:-retailflow} -d ${POSTGRES_DB:-retailflow_db}

shell-redis: ## Open a Redis CLI shell
	docker compose exec redis redis-cli

## ============================================================================
## Deployment
## ============================================================================

deploy-frontend: ## Deploy frontend to Vercel
	@echo "$(CYAN)Deploying frontend to Vercel...$(RESET)"
	cd frontend && npx vercel --prod
	@echo "$(GREEN)✓ Frontend deployed$(RESET)"

deploy-backend: ## Trigger Render backend deployment via webhook
	@if [ -z "$(RENDER_BACKEND_DEPLOY_HOOK)" ]; then echo "Set RENDER_BACKEND_DEPLOY_HOOK env variable"; exit 1; fi
	curl -X POST "$(RENDER_BACKEND_DEPLOY_HOOK)"
	@echo "$(GREEN)✓ Backend deployment triggered$(RESET)"

## ============================================================================
## Utilities
## ============================================================================

clean: ## Remove all generated files, caches, and build artifacts
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name coverage -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(RESET)"

check-env: ## Verify .env file exists and has required variables
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)⚠️  .env file not found. Copy .env.example to .env and configure it.$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ .env file found$(RESET)"
