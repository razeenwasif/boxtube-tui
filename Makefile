# BoxTube developer tasks.
# Usage: make <target>   (run `make help` for a list)

VENV    := .venv
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

$(VENV): ## Create the virtualenv
	python3 -m venv $(VENV)

.PHONY: install
install: $(VENV) ## Install the app and runtime deps (editable)
	$(PIP) install -e .

.PHONY: dev
dev: $(VENV) ## Install with development/test extras
	$(PIP) install -e ".[dev]"

.PHONY: link
link: ## Symlink the `boxtube` command into ~/.local/bin
	mkdir -p $(HOME)/.local/bin
	ln -sf "$(CURDIR)/$(VENV)/bin/boxtube" $(HOME)/.local/bin/boxtube
	@echo "Linked boxtube -> $(HOME)/.local/bin/boxtube"

.PHONY: run
run: ## Launch BoxTube
	$(PYTHON) -m boxtube

.PHONY: test
test: ## Run the test suite
	$(PYTHON) -m pytest

.PHONY: update-ytdlp
update-ytdlp: ## Update the bundled yt-dlp (fixes most playback breakage)
	$(PIP) install -U yt-dlp

.PHONY: clean
clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -not -path './$(VENV)/*' -exec rm -rf {} +

.PHONY: distclean
distclean: clean ## clean + remove the virtualenv
	rm -rf $(VENV)
