.PHONY: run hub open mafia charades guess-the-personality pictionary heads-up emoji-charades name-that-tune spyfall codenames trivia-showdown two-truths-and-a-lie fill-in-the-blank family-feud wavelength would-you-rather rapid-fire scattergories-sprint

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
WOULD_YOU_RATHER_FRONTEND_PORT ?= 3400
WOULD_YOU_RATHER_BACKEND_PORT ?= 8400
RAPID_FIRE_FRONTEND_PORT ?= 3500
RAPID_FIRE_BACKEND_PORT ?= 8500
FAMILY_FEUD_FRONTEND_PORT ?= 3600
FAMILY_FEUD_BACKEND_PORT ?= 8600
FILL_IN_THE_BLANK_FRONTEND_PORT ?= 3700
FILL_IN_THE_BLANK_BACKEND_PORT ?= 8700
WAVELENGTH_FRONTEND_PORT ?= 3800
WAVELENGTH_BACKEND_PORT ?= 8800
SCATTERGORIES_SPRINT_FRONTEND_PORT ?= 3900
SCATTERGORIES_SPRINT_BACKEND_PORT ?= 8900
TWO_TRUTHS_FRONTEND_PORT ?= 4100
TWO_TRUTHS_BACKEND_PORT ?= 9000

URL := http://localhost:$(HUB_PORT)

# Games hub — a landing page linking to whichever games are currently running
# (and how to start the rest). Dependency-free (stdlib only). Starts the hub
# in the background, opens it in your browser, then waits on it in the
# foreground so Ctrl+C stops it.
run:
	@python3 hub.py --port $(HUB_PORT) --mafia-port $(MAFIA_FRONTEND_PORT) --charades-port $(CHARADES_PORT) --guess-the-personality-port $(GUESS_THE_PERSONALITY_PORT) --pictionary-port $(PICTIONARY_PORT) --heads-up-port $(HEADS_UP_PORT) --emoji-charades-port $(EMOJI_CHARADES_PORT) --name-that-tune-port $(NAME_THAT_TUNE_PORT) --spyfall-port $(SPYFALL_FRONTEND_PORT) --codenames-port $(CODENAMES_FRONTEND_PORT) --trivia-showdown-port $(TRIVIA_SHOWDOWN_FRONTEND_PORT) --would-you-rather-port $(WOULD_YOU_RATHER_FRONTEND_PORT) --rapid-fire-port $(RAPID_FIRE_FRONTEND_PORT) --family-feud-port $(FAMILY_FEUD_FRONTEND_PORT) --fill-in-the-blank-port $(FILL_IN_THE_BLANK_FRONTEND_PORT) --wavelength-port $(WAVELENGTH_FRONTEND_PORT) --scattergories-sprint-port $(SCATTERGORIES_SPRINT_FRONTEND_PORT) --two-truths-and-a-lie-port $(TWO_TRUTHS_FRONTEND_PORT) & \
	pid=$$!; \
	sleep 1; \
	command -v open >/dev/null 2>&1 && open "$(URL)" || xdg-open "$(URL)"; \
	wait $$pid

hub:
	python3 hub.py --port $(HUB_PORT) --mafia-port $(MAFIA_FRONTEND_PORT) --charades-port $(CHARADES_PORT) --guess-the-personality-port $(GUESS_THE_PERSONALITY_PORT) --pictionary-port $(PICTIONARY_PORT) --heads-up-port $(HEADS_UP_PORT) --emoji-charades-port $(EMOJI_CHARADES_PORT) --name-that-tune-port $(NAME_THAT_TUNE_PORT) --spyfall-port $(SPYFALL_FRONTEND_PORT) --codenames-port $(CODENAMES_FRONTEND_PORT) --trivia-showdown-port $(TRIVIA_SHOWDOWN_FRONTEND_PORT) --would-you-rather-port $(WOULD_YOU_RATHER_FRONTEND_PORT) --rapid-fire-port $(RAPID_FIRE_FRONTEND_PORT) --family-feud-port $(FAMILY_FEUD_FRONTEND_PORT) --fill-in-the-blank-port $(FILL_IN_THE_BLANK_FRONTEND_PORT) --wavelength-port $(WAVELENGTH_FRONTEND_PORT) --scattergories-sprint-port $(SCATTERGORIES_SPRINT_FRONTEND_PORT) --two-truths-and-a-lie-port $(TWO_TRUTHS_FRONTEND_PORT)

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

two-truths-and-a-lie:
	$(MAKE) -C games/two-truths-and-a-lie install
	$(MAKE) -C games/two-truths-and-a-lie dev FRONTEND_PORT=$(TWO_TRUTHS_FRONTEND_PORT) BACKEND_PORT=$(TWO_TRUTHS_BACKEND_PORT)

fill-in-the-blank:
	$(MAKE) -C games/fill-in-the-blank install
	$(MAKE) -C games/fill-in-the-blank dev FRONTEND_PORT=$(FILL_IN_THE_BLANK_FRONTEND_PORT) BACKEND_PORT=$(FILL_IN_THE_BLANK_BACKEND_PORT)

family-feud:
	$(MAKE) -C games/family-feud install
	$(MAKE) -C games/family-feud dev FRONTEND_PORT=$(FAMILY_FEUD_FRONTEND_PORT) BACKEND_PORT=$(FAMILY_FEUD_BACKEND_PORT)

wavelength:
	$(MAKE) -C games/wavelength install
	$(MAKE) -C games/wavelength dev FRONTEND_PORT=$(WAVELENGTH_FRONTEND_PORT) BACKEND_PORT=$(WAVELENGTH_BACKEND_PORT)

would-you-rather:
	$(MAKE) -C games/would-you-rather install
	$(MAKE) -C games/would-you-rather dev FRONTEND_PORT=$(WOULD_YOU_RATHER_FRONTEND_PORT) BACKEND_PORT=$(WOULD_YOU_RATHER_BACKEND_PORT)

rapid-fire:
	$(MAKE) -C games/rapid-fire install
	$(MAKE) -C games/rapid-fire dev FRONTEND_PORT=$(RAPID_FIRE_FRONTEND_PORT) BACKEND_PORT=$(RAPID_FIRE_BACKEND_PORT)

scattergories-sprint:
	$(MAKE) -C games/scattergories-sprint install
	$(MAKE) -C games/scattergories-sprint dev FRONTEND_PORT=$(SCATTERGORIES_SPRINT_FRONTEND_PORT) BACKEND_PORT=$(SCATTERGORIES_SPRINT_BACKEND_PORT)
