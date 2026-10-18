PACKAGE := aburra_air

.PHONY: help install lint typecheck test coverage contract extract load transform quality dbt-docs elt app docs clean

help:  ## Show this help
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install:  ## Install all dependencies and the pre-commit hooks
	uv sync
	uv run pre-commit install

lint:  ## Lint, check formatting and run the security scan
	uv run ruff check .
	uv run ruff format --check .
	uv run bandit -c pyproject.toml -r src -q

typecheck:  ## Static type checking
	uv run mypy

test:  ## Run the test suite
	uv run pytest

coverage:  ## Run tests with a coverage report (terminal + htmlcov/)
	uv run pytest --cov --cov-report=term --cov-report=html

contract:  ## Check the live SIATA API still has the fields the pipeline relies on
	uv run pytest -m live

extract:  ## Run the extract pipeline (APIs -> 01_raw)
	uv run python -m $(PACKAGE).pipelines.extract_pipeline

load:  ## Run the load pipeline (01_raw -> DuckDB)
	uv run python -m $(PACKAGE).pipelines.load_pipeline

transform:  ## Run the transform pipeline (dbt)
	uv run python -m $(PACKAGE).pipelines.transform_pipeline

quality:  ## Fail if the loaded data is stale, incomplete or duplicated
	uv run python -m $(PACKAGE).pipelines.quality_pipeline

dbt-docs:  ## Generate the dbt docs site (dbt/target/index.html)
	uv run python -m $(PACKAGE).pipelines.transform_pipeline docs generate

elt: extract load transform quality  ## Run the full ELT

app:  ## Launch the Streamlit app
	uv run streamlit run src/$(PACKAGE)/app/main.py

docs:  ## Serve the documentation locally
	uv run mkdocs serve

clean:  ## Remove caches and build artifacts
	rm -rf .mypy_cache .pytest_cache .ruff_cache htmlcov .coverage coverage.xml site dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
