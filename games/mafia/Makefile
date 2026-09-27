.PHONY: install install-backend install-frontend \
	dev dev-backend dev-frontend \
	dev-lan dev-lan-backend dev-lan-frontend \
	test test-backend test-frontend \
	docker-up docker-down docker-build docker-logs \
	clean

BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV := $(BACKEND_DIR)/.venv
PYTHON := $(VENV)/bin/python

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3000
LAN_HOST ?= 192.168.1.108

install: install-backend install-frontend

install-backend:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r $(BACKEND_DIR)/requirements.txt

install-frontend:
	cd $(FRONTEND_DIR) && npm install

dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-lan:
	$(MAKE) -j2 dev-lan-backend dev-lan-frontend

dev-backend:
	cd $(BACKEND_DIR) && .venv/bin/uvicorn app.main:app --reload --port $(BACKEND_PORT)

dev-frontend:
	cd $(FRONTEND_DIR) && npm run dev -- -p $(FRONTEND_PORT)

dev-lan-backend:
	cd $(BACKEND_DIR) && REVELRY_CORS_ORIGINS='["http://localhost:$(FRONTEND_PORT)","http://127.0.0.1:$(FRONTEND_PORT)","http://$(LAN_HOST):$(FRONTEND_PORT)"]' REVELRY_FRONTEND_BASE_URL='http://$(LAN_HOST):$(FRONTEND_PORT)' .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port $(BACKEND_PORT)

dev-lan-frontend:
	cd $(FRONTEND_DIR) && NEXT_PUBLIC_API_BASE_URL='http://$(LAN_HOST):$(BACKEND_PORT)' NEXT_PUBLIC_WS_BASE_URL='ws://$(LAN_HOST):$(BACKEND_PORT)' npm run dev -- -H 0.0.0.0 -p $(FRONTEND_PORT)

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
