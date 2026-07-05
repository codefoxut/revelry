VENV     := .venv
PYTHON   := $(VENV)/bin/python3
PORT     := 9090
APP      := server.py

.DEFAULT_GOAL := help

# ── Colours ────────────────────────────────────────────────────────────────
BOLD  := \033[1m
RESET := \033[0m
CYAN  := \033[36m
GREEN := \033[32m
GOLD  := \033[33m

# ── Targets ────────────────────────────────────────────────────────────────
.PHONY: help install run dev update-categories populate-categories migrate-db clean

help:
	@printf "\n"
	@printf "  $(BOLD)$(GOLD)🎨  PICTIONARY — Makefile$(RESET)\n"
	@printf "  $(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)\n"
	@printf "  $(GREEN)make install$(RESET)             create .venv and install dependencies\n"
	@printf "  $(GREEN)make run$(RESET)                 start the game server  (port $(PORT))\n"
	@printf "  $(GREEN)make dev$(RESET)                 start with auto-reload  (debug mode)\n"
	@printf "  $(GREEN)make update-categories$(RESET)   grow data/categories.db via Claude (ARGS=\"...\")\n"
	@printf "  $(GREEN)make populate-categories$(RESET) bulk-fill data/categories.db from static sources, no LLM (ARGS=\"...\")\n"
	@printf "  $(GREEN)make migrate-db$(RESET)          one-time: rebuild data/categories.db from a categories.json\n"
	@printf "  $(GREEN)make clean$(RESET)               remove compiled Python cache files\n"
	@printf "  $(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)\n"
	@printf "\n"

$(VENV)/bin/python3:
	@printf "$(CYAN)▶ Creating virtualenv at $(VENV)…$(RESET)\n"
	python3 -m venv $(VENV)

install: $(VENV)/bin/python3
	@printf "$(CYAN)▶ Installing dependencies…$(RESET)\n"
	$(PYTHON) -m pip install -r requirements.txt --quiet
	@printf "$(GREEN)✔ Done!$(RESET)\n"

run: install
	@printf "$(CYAN)▶ Starting Pictionary on http://localhost:$(PORT)$(RESET)\n"
	@set -a && [ -f .env ] && . ./.env; set +a; $(PYTHON) $(APP) --port=$(PORT)

dev: install
	@printf "$(CYAN)▶ Killing any process on port $(PORT)…$(RESET)\n"
	@lsof -ti :$(PORT) | xargs kill -9 2>/dev/null || true
	@printf "$(CYAN)▶ Dev mode (auto-reload) on http://localhost:$(PORT)$(RESET)\n"
	@set -a && [ -f .env ] && . ./.env; set +a; $(PYTHON) $(APP) --port=$(PORT) --debug

update-categories: install
	@printf "$(CYAN)▶ Growing data/categories.db via Claude…$(RESET)\n"
	@set -a && [ -f .env ] && . ./.env; set +a; $(PYTHON) tools/update_categories.py $(ARGS)

populate-categories: install
	@printf "$(CYAN)▶ Populating data/categories.db from static sources (no LLM calls)…$(RESET)\n"
	$(PYTHON) tools/populate_categories.py $(ARGS)

migrate-db: install
	@printf "$(CYAN)▶ Migrating data/categories.json -> data/categories.db…$(RESET)\n"
	$(PYTHON) tools/migrate_json_to_db.py

clean:
	@printf "$(CYAN)▶ Cleaning compiled Python files…$(RESET)\n"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@printf "$(GREEN)✔ Clean!$(RESET)\n"
