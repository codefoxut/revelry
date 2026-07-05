.PHONY: install install-backend install-frontend \
	dev dev-backend dev-frontend \
	test test-backend test-frontend \
	docker-up docker-down docker-build docker-logs \
	clean

BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV := $(BACKEND_DIR)/.venv
PYTHON := $(VENV)/bin/python

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3000

install: install-backend install-frontend

install-backend:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r $(BACKEND_DIR)/requirements.txt

install-frontend:
	cd $(FRONTEND_DIR) && npm install

dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd $(BACKEND_DIR) && .venv/bin/uvicorn app.main:app --reload --port $(BACKEND_PORT)

dev-frontend:
	cd $(FRONTEND_DIR) && npm run dev -- -p $(FRONTEND_PORT)

test: test-backend test-frontend

test-backend:
	cd $(BACKEND_DIR) && .venv/bin/pytest

test-frontend:
	cd $(FRONTEND_DIR) && npm run test

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

clean:
	rm -rf $(VENV) $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/.next
