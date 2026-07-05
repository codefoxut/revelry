VENV   := .venv
PYTHON := $(VENV)/bin/python
UV     := $(VENV)/bin/uvicorn
PORT   := 8081

.PHONY: setup install run clean

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
	@echo "🕵️  Starting Guess the Personality on http://localhost:$(PORT)"
	$(UV) main:app --host 0.0.0.0 --port $(PORT) --reload

clean:
	rm -rf $(VENV) __pycache__ static/__pycache__
	@echo "🧹 Cleaned up"
