VENV   := .venv
PYTHON := $(VENV)/bin/python
UV     := $(VENV)/bin/uvicorn
PORT   := 8082

.PHONY: setup install run test seed clean

setup: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	@echo "✅ Virtualenv created at $(VENV)"

install: setup
	$(PYTHON) -m pip install --upgrade pip -q
	$(PYTHON) -m pip install -r requirements.txt -q
	@echo "✅ Dependencies installed. Run: make run"

run: install
	@echo "🤳 Starting Heads Up! on http://localhost:$(PORT)"
	$(UV) main:app --host 0.0.0.0 --port $(PORT) --reload

seed: install
	$(PYTHON) tools/seed_categories.py

test: install
	$(PYTHON) -m pytest -q

clean:
	rm -rf $(VENV) __pycache__ static/__pycache__ tools/__pycache__ .pytest_cache
	@echo "🧹 Cleaned up"
