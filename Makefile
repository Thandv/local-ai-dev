# Makefile — build local-ai-setup binaries with PyInstaller
# Run `make` to see available targets.

PYTHON     := python3
PYINSTALLER := pyinstaller
ENTRY      := scripts/setup_installer.py
DIST       := dist
SPEC_FLAGS := --onefile --clean --name local-ai-setup \
              --add-data "src/local_ai/repos.json:." \
              --add-data "src:package"

.PHONY: help install binary binary-mac binary-linux binary-win clean

help:
	@echo ""
	@echo "  Local AI Dev Suite — Build Targets"
	@echo "  ─────────────────────────────────"
	@echo "  make install      Install Python package locally (dev mode)"
	@echo "  make binary       Build installer binary for this platform"
	@echo "  make clean        Remove build artefacts"
	@echo ""

install:
	$(PYTHON) -m pip install -e ".[dev]"

deps:
	$(PYTHON) -m pip install pyinstaller

binary: deps
	$(PYINSTALLER) $(SPEC_FLAGS) $(ENTRY)
	@echo ""
	@echo "  Binary built: $(DIST)/local-ai-setup"
	@echo "  Run it with:  ./$(DIST)/local-ai-setup"

clean:
	rm -rf $(DIST) build __pycache__ *.spec
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
