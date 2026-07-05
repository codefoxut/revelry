.PHONY: run hub open mafia charades guess-the-personality

HUB_PORT ?= 4000
MAFIA_FRONTEND_PORT ?= 3000
MAFIA_BACKEND_PORT ?= 8000
CHARADES_PORT ?= 8080
GUESS_THE_PERSONALITY_PORT ?= 8081

URL := http://localhost:$(HUB_PORT)

# Games hub — a landing page linking to whichever games are currently running
# (and how to start the rest). Dependency-free (stdlib only). Starts the hub
# in the background, opens it in your browser, then waits on it in the
# foreground so Ctrl+C stops it.
run:
	@python3 hub.py --port $(HUB_PORT) --mafia-port $(MAFIA_FRONTEND_PORT) --charades-port $(CHARADES_PORT) --guess-the-personality-port $(GUESS_THE_PERSONALITY_PORT) & \
	pid=$$!; \
	sleep 1; \
	command -v open >/dev/null 2>&1 && open "$(URL)" || xdg-open "$(URL)"; \
	wait $$pid

hub:
	python3 hub.py --port $(HUB_PORT) --mafia-port $(MAFIA_FRONTEND_PORT) --charades-port $(CHARADES_PORT) --guess-the-personality-port $(GUESS_THE_PERSONALITY_PORT)

# Opens the hub page in your default browser. Run this from a second
# terminal (or after backgrounding `make run`) once the hub is up.
open:
	@command -v open >/dev/null 2>&1 && open "$(URL)" || xdg-open "$(URL)"

# Convenience shortcuts to start an individual game directly, delegating to
# that game's own Makefile.
mafia:
	$(MAKE) -C games/mafia install
	$(MAKE) -C games/mafia dev FRONTEND_PORT=$(MAFIA_FRONTEND_PORT) BACKEND_PORT=$(MAFIA_BACKEND_PORT)

charades:
	$(MAKE) -C games/bollywood-dumbcharades run PORT=$(CHARADES_PORT)

guess-the-personality:
	$(MAKE) -C games/guess-the-personality run PORT=$(GUESS_THE_PERSONALITY_PORT)
