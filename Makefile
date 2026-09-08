# Pulse -- common tasks.
.DEFAULT_GOAL := help
.PHONY: help up down restart logs ps build rebuild migrate revision shell-api shell-db \
        test lint format backend-dev frontend-dev clean deploy

COMPOSE := docker compose
DEV     := $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the full stack
	$(COMPOSE) up -d --build

down: ## Stop the stack (keeps volumes)
	$(COMPOSE) down

restart: ## Restart every service
	$(COMPOSE) restart

logs: ## Follow logs (make logs S=api for one service)
	$(COMPOSE) logs -f --tail=100 $(S)

ps: ## Show service status
	$(COMPOSE) ps

build: ## Build images
	$(COMPOSE) build

rebuild: ## Rebuild images from scratch
	$(COMPOSE) build --no-cache

migrate: ## Apply database migrations
	$(COMPOSE) run --rm migrate alembic upgrade head

revision: ## Autogenerate a migration: make revision M="add table"
	./backend/scripts/new-migration.sh "$(M)"

shell-api: ## Open a shell in the API container
	$(COMPOSE) exec api bash

shell-db: ## Open psql on the database
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-pulse} -d $${POSTGRES_DB:-pulse}

test: ## Run the backend test suite
	cd backend && ../.venv/bin/python -m pytest -q

lint: ## Lint backend and frontend
	cd backend && ../.venv/bin/ruff check . && ../.venv/bin/ruff format --check .
	cd frontend && npm run lint && npx tsc --noEmit

format: ## Auto-format the backend
	cd backend && ../.venv/bin/ruff check --fix . && ../.venv/bin/ruff format .

backend-dev: ## Run the API locally with reload
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8010

frontend-dev: ## Run the web app locally
	cd frontend && npm run dev

deploy: ## Deploy to the configured host
	./deploy/deploy.sh

clean: ## Stop the stack and delete its volumes (DESTROYS DATA)
	$(COMPOSE) down -v
