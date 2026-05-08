.DEFAULT_GOAL := help
PKG := autopsyai

help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?##"}{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

install:             ## Install runtime deps
	pip install -e .

install-dev:         ## Install all deps including dev
	pip install -e ".[all,dev]"
	pre-commit install

lint:                ## Run ruff linter
	ruff check $(PKG) tests

fmt:                 ## Auto-format with ruff
	ruff format $(PKG) tests
	ruff check --fix $(PKG) tests

typecheck:           ## Run mypy strict
	mypy $(PKG) --strict

test:                ## Run full test suite
	pytest tests/ -x

test-unit:           ## Run unit tests only
	pytest tests/unit/ -x

test-integration:    ## Run integration tests
	pytest tests/integration/ -x -m integration

coverage:            ## HTML coverage report
	pytest tests/ --cov=$(PKG) --cov-report=html
	open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html

clean:               ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info .coverage htmlcov/ .mypy_cache/ .ruff_cache/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true

build: clean         ## Build wheel + sdist
	python3 -m hatchling build

publish: build       ## Publish to PyPI
	python3 -m twine upload dist/* --username __token__ --password $$PYPI_TOKEN
