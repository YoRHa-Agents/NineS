.PHONY: test lint format typecheck coverage clean

test:
	uv run pytest tests/

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

typecheck:
	uv run mypy src/nines/

coverage:
	uv run pytest --cov=nines --cov-report=term-missing --cov-report=html:reports/htmlcov tests/

clean:
	rm -rf .mypy_cache .pytest_cache .ruff_cache reports/ dist/ build/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
