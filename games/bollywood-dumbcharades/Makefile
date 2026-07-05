VENV   := .venv
PYTHON := $(VENV)/bin/python
UV     := $(VENV)/bin/uvicorn
PORT   := 8080

.PHONY: setup install run scrape update-movies bulk-fill clean

setup: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	@echo "✅ Virtualenv created at $(VENV)"

install: setup
	$(PYTHON) -m pip install --upgrade pip -q
	$(PYTHON) -m pip install -r requirements.txt -q
	@echo "✅ Dependencies installed. Run: make run"

run: install
	@test -f .env || (echo "❌ .env file not found. Copy .env and add your ANTHROPIC_API_KEY."; exit 1)
	@echo "🎬 Starting Bollywood Dumb Charades on http://localhost:$(PORT)"
	$(UV) main:app --host 0.0.0.0 --port $(PORT) --reload

scrape: install
	@test -n "$(YEAR)" || (echo "❌ Usage: make scrape YEAR=2023 [ARGS=\"--limit 15 --dry-run\"]"; exit 1)
	$(PYTHON) tools/scrape_wiki_movies.py --year $(YEAR) $(ARGS)

update-movies: install
	$(PYTHON) tools/update_movies.py $(ARGS)

bulk-fill: install
	@test -n "$(START)" || (echo "❌ Usage: make bulk-fill START=1927 END=2026 [ARGS=\"--skip-existing 15 --dry-run\"]"; exit 1)
	@test -n "$(END)" || (echo "❌ Usage: make bulk-fill START=1927 END=2026 [ARGS=\"--skip-existing 15 --dry-run\"]"; exit 1)
	$(PYTHON) tools/bulk_fill_movies.py --start $(START) --end $(END) $(ARGS)

clean:
	rm -rf $(VENV) __pycache__ static/__pycache__ tools/__pycache__
	@echo "🧹 Cleaned up"
