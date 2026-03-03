SHELL := /bin/bash

VENV_BIN := .venv/bin
PYTHON := $(if $(wildcard $(VENV_BIN)/python),$(VENV_BIN)/python,python3)
PIP := $(if $(wildcard $(VENV_BIN)/pip),$(VENV_BIN)/pip,pip3)
PYTEST := $(if $(wildcard $(VENV_BIN)/pytest),$(VENV_BIN)/pytest,pytest)
RUFF := $(if $(wildcard $(VENV_BIN)/ruff),$(VENV_BIN)/ruff,ruff)
CELERY := $(if $(wildcard $(VENV_BIN)/celery),$(VENV_BIN)/celery,celery)
MANAGE := $(PYTHON) manage.py
DOCKER_COMPOSE := docker compose

.PHONY: help setup install infra infra-full infra-down redis-up redis-down db-up db-down migrate makemigrations-check check api worker beat test lint ci

help: ## Show available commands
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv and install dev dependencies
	@test -d .venv || python3 -m venv .venv
	@$(VENV_BIN)/pip install --upgrade pip
	@$(VENV_BIN)/pip install -r requirements/dev.txt

install: setup ## Alias for setup

infra: ## Start Redis only (recommended when local Postgres is already running)
	@$(DOCKER_COMPOSE) up -d redis

infra-full: ## Start Postgres + Redis via docker-compose
	@$(DOCKER_COMPOSE) up -d db redis

infra-down: ## Stop Postgres + Redis services
	@$(DOCKER_COMPOSE) stop db redis

redis-up: ## Start Redis
	@$(DOCKER_COMPOSE) up -d redis

redis-down: ## Stop Redis
	@$(DOCKER_COMPOSE) stop redis

db-up: ## Start Postgres
	@$(DOCKER_COMPOSE) up -d db

db-down: ## Stop Postgres
	@$(DOCKER_COMPOSE) stop db

migrate: ## Apply Django migrations
	@$(MANAGE) migrate

makemigrations-check: ## Fail if model changes need migrations
	@$(MANAGE) makemigrations --check --dry-run

check: ## Run Django system checks
	@$(MANAGE) check

api: ## Run Django API server on :8000
	@$(MANAGE) runserver 0.0.0.0:8000

worker: ## Run Celery worker (critical/default/bulk queues)
	@$(CELERY) -A config worker -Q critical,default,bulk -l info

beat: ## Run Celery beat scheduler
	@$(CELERY) -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

test: ## Run full pytest suite
	@$(PYTEST) -q

lint: ## Run ruff checks
	@$(RUFF) check apps config services

ci: makemigrations-check check lint test ## Run local CI-style checks
