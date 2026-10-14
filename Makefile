BACKEND_DIR := backend
VENV_DIR := $(BACKEND_DIR)/.venv

ifeq ($(OS),Windows_NT)
PYTHON ?= py -3
VENV_BIN := .venv/Scripts
else
PYTHON ?= python3
VENV_BIN := .venv/bin
endif

VENV_PYTHON := $(VENV_BIN)/python

.PHONY: install dev test lint format migrate seed graph diagrams eval dev-stack up down

install:
	$(PYTHON) -m venv $(VENV_DIR)
	cd $(BACKEND_DIR) && $(VENV_PYTHON) -m pip install --upgrade pip
	cd $(BACKEND_DIR) && $(VENV_PYTHON) -m pip install -r requirements-dev.txt

.dev-check:
	cd $(BACKEND_DIR) && $(VENV_PYTHON) --version

test: .dev-check
	cd $(BACKEND_DIR) && $(VENV_BIN)/pytest -q

lint: .dev-check
	cd $(BACKEND_DIR) && $(VENV_BIN)/ruff check app tests evals

format: .dev-check
	cd $(BACKEND_DIR) && $(VENV_BIN)/ruff format app tests

migrate: .dev-check
	cd $(BACKEND_DIR) && $(VENV_BIN)/alembic upgrade head

seed: .dev-check
	cd $(BACKEND_DIR) && $(VENV_PYTHON) ../scripts/seed.py

graph: .dev-check
	cd $(BACKEND_DIR) && $(VENV_PYTHON) -m app.agent.export_graph

eval: .dev-check
	cd $(BACKEND_DIR) && $(VENV_PYTHON) -m evals.run

diagrams:
	npx --yes @mermaid-js/mermaid-cli@11.4.2 -i docs/diagrams/system.mmd -o docs/images/architecture.png -b transparent -s 2

dev-stack:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

dev: .dev-check
	cd $(BACKEND_DIR) && $(VENV_BIN)/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

up:
	docker compose up --build

down:
	docker compose down
