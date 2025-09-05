# OpenHands V1 Makefile
# Minimal Makefile for OpenHands V1 using uv

# Colors for output
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
CYAN := \033[36m
RESET := \033[0m

# Required uv version
REQUIRED_UV_VERSION := 0.8.13

.PHONY: build format lint clean help check-uv-version

# Default target
.DEFAULT_GOAL := help

# Check uv version
check-uv-version:
	@echo "$(YELLOW)Checking uv version...$(RESET)"
	@UV_VERSION=$$(uv --version | cut -d' ' -f2); \
	REQUIRED_VERSION=$(REQUIRED_UV_VERSION); \
	if [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$UV_VERSION" | sort -V | head -n1)" != "$$REQUIRED_VERSION" ]; then \
		echo "$(RED)Error: uv version $$UV_VERSION is less than required $$REQUIRED_VERSION$(RESET)"; \
		echo "$(YELLOW)Please update uv with: uv self update$(RESET)"; \
		exit 1; \
	fi; \
	echo "$(GREEN)uv version $$UV_VERSION meets requirements$(RESET)"

# Main build target - setup everything
build: check-uv-version
	@echo "$(CYAN)Setting up OpenHands V1 development environment...$(RESET)"
	@echo "$(YELLOW)Installing dependencies with uv sync --dev...$(RESET)"
	@uv sync --dev
	@echo "$(GREEN)Dependencies installed successfully.$(RESET)"
	@echo "$(YELLOW)Setting up pre-commit hooks...$(RESET)"
	@uv run pre-commit install
	@echo "$(GREEN)Pre-commit hooks installed successfully.$(RESET)"
	@echo "$(GREEN)Build complete! Development environment is ready.$(RESET)"

# Format code using uv format
format:
	@echo "$(YELLOW)Formatting code with uv format...$(RESET)"
	@uv run ruff format
	@echo "$(GREEN)Code formatted successfully.$(RESET)"

# Lint code
lint:
	@echo "$(YELLOW)Linting code with ruff...$(RESET)"
	@uv run ruff check --fix
	@echo "$(GREEN)Linting completed.$(RESET)"

# Clean up cache files
clean:
	@echo "$(YELLOW)Cleaning up cache files...$(RESET)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache .ruff_cache .mypy_cache 2>/dev/null || true
	@echo "$(GREEN)Cache files cleaned.$(RESET)"

# Show help
help:
	@echo "$(CYAN)OpenHands V1 Makefile$(RESET)"
	@echo "Available targets:"
	@echo "  $(GREEN)build$(RESET)        - Setup development environment (install deps + hooks)"
	@echo "  $(GREEN)format$(RESET)       - Format code with uv format"
	@echo "  $(GREEN)lint$(RESET)         - Lint code with ruff"
	@echo "  $(GREEN)clean$(RESET)        - Clean up cache files"
	@echo "  $(GREEN)help$(RESET)         - Show this help message"
