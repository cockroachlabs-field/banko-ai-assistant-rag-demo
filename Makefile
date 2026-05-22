.PHONY: test test-local lint types fmt clean help

help:
	@echo "Targets:"
	@echo "  make test            - run full pytest suite"
	@echo "  make test-local      - lint + types + test (the gate before any push)"
	@echo "  make lint            - ruff check"
	@echo "  make types           - mypy"
	@echo "  make fmt             - ruff format"
	@echo "  make clean           - remove caches"

test:
	uv run pytest tests/ -v

test-local: lint types test
	@echo ""
	@echo "✓ Local test suite passed."
	@echo "  REMINDER: multi-provider smoke is still required before push."
	@echo "  See docs/coach-smoke-checklist.md once it exists, or run the app"
	@echo "  against each of watsonx, openai, aws, gemini, ollama manually."

lint:
	uv run ruff check banko_ai/ tests/

types:
	uv run mypy banko_ai/

fmt:
	uv run ruff format banko_ai/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache
