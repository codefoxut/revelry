.PHONY: run hub open mafia charades guess-the-personality pictionary heads-up emoji-charades name-that-tune spyfall codenames trivia-showdown

HUB_PORT ?= 4000
MAFIA_FRONTEND_PORT ?= 3000
MAFIA_BACKEND_PORT ?= 8000
CHARADES_PORT ?= 8080
GUESS_THE_PERSONALITY_PORT ?= 8081
PICTIONARY_PORT ?= 9090
HEADS_UP_PORT ?= 8082
EMOJI_CHARADES_PORT ?= 8083
NAME_THAT_TUNE_PORT ?= 8084
SPYFALL_FRONTEND_PORT ?= 3100
SPYFALL_BACKEND_PORT ?= 8100
CODENAMES_FRONTEND_PORT ?= 3200
CODENAMES_BACKEND_PORT ?= 8200
TRIVIA_SHOWDOWN_FRONTEND_PORT ?= 3300
TRIVIA_SHOWDOWN_BACKEND_PORT ?= 8300

URL := http://localhost:$(HUB_PORT)

# Games hub — a landing page linking to whichever games are currently running
# (and how to start the rest). Dependency-free (stdlib only). Starts the hub
# in the background, opens it in your browser, then waits on it in the
# foreground so Ctrl+C stops it.
run:
	@python3 hub.py --port $(HUB_PORT) --mafia-port $(MAFIA_FRONTEND_PORT) --charades-port $(CHARADES_PORT) --guess-the-personality-port $(GUESS_THE_PERSONALITY_PORT) --pictionary-port $(PICTIONARY_PORT) --heads-up-port $(HEADS_UP_PORT) --emoji-charades-port $(EMOJI_CHARADES_PORT) --name-that-tune-port $(NAME_THAT_TUNE_PORT) --spyfall-port $(SPYFALL_FRONTEND_PORT) --codenames-port $(CODENAMES_FRONTEND_PORT) --trivia-showdown-port $(TRIVIA_SHOWDOWN_FRONTEND_PORT) & \
	pid=$$!; \
	sleep 1; \
	command -v open >/dev/null 2>&1 && open "$(URL)" || xdg-open "$(URL)"; \
	wait $$pid

hub:
	python3 hub.py --port $(HUB_PORT) --mafia-port $(MAFIA_FRONTEND_PORT) --charades-port $(CHARADES_PORT) --guess-the-personality-port $(GUESS_THE_PERSONALITY_PORT) --pictionary-port $(PICTIONARY_PORT) --heads-up-port $(HEADS_UP_PORT) --emoji-charades-port $(EMOJI_CHARADES_PORT) --name-that-tune-port $(NAME_THAT_TUNE_PORT) --spyfall-port $(SPYFALL_FRONTEND_PORT) --codenames-port $(CODENAMES_FRONTEND_PORT) --trivia-showdown-port $(TRIVIA_SHOWDOWN_FRONTEND_PORT)

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

pictionary:
	$(MAKE) -C games/pictionary run PORT=$(PICTIONARY_PORT)

heads-up:
	$(MAKE) -C games/heads-up run PORT=$(HEADS_UP_PORT)

emoji-charades:
	$(MAKE) -C games/emoji-charades run PORT=$(EMOJI_CHARADES_PORT)

name-that-tune:
	$(MAKE) -C games/name-that-tune run PORT=$(NAME_THAT_TUNE_PORT)

spyfall:
	$(MAKE) -C games/spyfall install
	$(MAKE) -C games/spyfall dev FRONTEND_PORT=$(SPYFALL_FRONTEND_PORT) BACKEND_PORT=$(SPYFALL_BACKEND_PORT)

codenames:
	$(MAKE) -C games/codenames install
	$(MAKE) -C games/codenames dev FRONTEND_PORT=$(CODENAMES_FRONTEND_PORT) BACKEND_PORT=$(CODENAMES_BACKEND_PORT)

trivia-showdown:
	$(MAKE) -C games/trivia-showdown install
	$(MAKE) -C games/trivia-showdown dev FRONTEND_PORT=$(TRIVIA_SHOWDOWN_FRONTEND_PORT) BACKEND_PORT=$(TRIVIA_SHOWDOWN_BACKEND_PORT)
