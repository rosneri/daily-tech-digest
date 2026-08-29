# Daily Tech Digest
SHELL := /bin/bash
.DEFAULT_GOAL := help

DATE ?= $(shell date +%F)

CONFIG := config.env
HAVE_CONFIG := $(wildcard $(CONFIG))
ifneq ($(HAVE_CONFIG),)
include $(CONFIG)
export
endif

DIGEST_HOME ?= $(HOME)/Automation/daily-tech-digest
SUMMARY     := $(DIGEST_HOME)/horizon/data/summaries/horizon-$(DATE)-en.md

.PHONY: help install install-podcast install-schedule uninstall-schedule \
        config run-horizon podcast transcript status logs summary clean check \
        skill test

help: ## Show this help
	@echo "Daily Tech Digest"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Override the date on any target:  make podcast DATE=2026-08-28"

config: ## Create config.env from the example
	@test -f $(CONFIG) && echo "config.env already exists" \
	  || (cp config.env.example $(CONFIG) && echo "created config.env — edit it before installing")

install: ## Full install (horizon + podcast + schedule)
	@./install.sh

install-podcast: ## Install podcastfy into its own venv
	@scripts/install-podcast.sh

install-schedule: ## Install/reload the daily launchd job
	@scripts/install-launchd.sh

uninstall-schedule: ## Remove the launchd job
	@launchctl unload "$(HOME)/Library/LaunchAgents/$(LAUNCHD_LABEL).plist" 2>/dev/null || true
	@rm -f "$(HOME)/Library/LaunchAgents/$(LAUNCHD_LABEL).plist"
	@echo "removed $(LAUNCHD_LABEL)"

test: ## Run the test suite
	@python3 tests/test_transcript.py

check: ## Verify config, dependencies and syntax
	@echo "== shell syntax"
	@for f in install.sh scripts/*.sh; do bash -n "$$f" && echo "  ok $$f"; done
	@echo "== python syntax"
	@python3 -c "import ast;ast.parse(open('scripts/generate_podcast.py').read());print('  ok scripts/generate_podcast.py')"
	@echo "== json"
	@for f in config/*.json; do python3 -m json.tool "$$f" >/dev/null && echo "  ok $$f"; done
	@echo "== tools"
	@for t in git python3 uv claude ffmpeg; do \
	  command -v $$t >/dev/null && echo "  ok $$t" || echo "  -- $$t (missing)"; done
	@test -f $(CONFIG) && echo "  ok config.env" || echo "  -- config.env (run: make config)"
	@echo "== tests"
	@python3 tests/test_transcript.py >/dev/null && echo "  ok tests pass"

skill: ## Print the Claude routine definition with your config filled in
	@scripts/render-skill.sh

run-horizon: ## Fetch, score and summarise today's news
	@scripts/run-horizon.sh

podcast: ## Generate the podcast episode for DATE
	@scripts/generate-podcast.sh $(DATE)

transcript: ## Write the podcast script for DATE without synthesising audio
	@scripts/generate-podcast.sh $(DATE) --transcript-only

summary: ## Print today's Horizon summary headlines
	@test -f "$(SUMMARY)" || { echo "no summary for $(DATE)"; exit 1; }
	@sed -n '1,/^---$$/p' "$(SUMMARY)"

status: ## Show what exists for DATE
	@echo "date        $(DATE)"
	@echo "state       $(DIGEST_HOME)"
	@printf "summary     "; test -f "$(SUMMARY)" \
	  && echo "$$(wc -c < "$(SUMMARY)" | tr -d ' ') bytes" || echo "missing"
	@printf "digest      "; test -f "$(DIGEST_HOME)/digests/$(DATE)/digest.json" \
	  && python3 -c "import json;d=json.load(open('$(DIGEST_HOME)/digests/$(DATE)/digest.json'));print(d['story_count'],'stories, source=',d.get('source'))" \
	  || echo "missing"
	@printf "podcast     "; test -f "$(DIGEST_HOME)/podcasts/digest-$(DATE).mp3" \
	  && echo "$$(du -h "$(DIGEST_HOME)/podcasts/digest-$(DATE).mp3" | cut -f1)" || echo "missing"
	@printf "schedule    "; launchctl list 2>/dev/null | grep -q "$(LAUNCHD_LABEL)" \
	  && echo "$(LAUNCHD_LABEL) loaded" || echo "not loaded"

logs: ## Tail the Horizon log
	@tail -40 "$(DIGEST_HOME)/horizon.log" 2>/dev/null || echo "no log yet"

clean: ## Remove generated podcast artefacts (keeps digests and summaries)
	@rm -rf "$(DIGEST_HOME)/podcasts"/*.mp3 "$(DIGEST_HOME)/podcasts/transcripts"
	@echo "cleaned podcast artefacts"
