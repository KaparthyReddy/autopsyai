# Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/)

## [Unreleased]

## [0.1.0] - 2024-01-01

### Added
- Structured span-based tracing engine with async-safe context propagation
- SQLite trace store with WAL mode and content-addressed span storage
- Native integrations: OpenAI, Anthropic, LangChain callback handler, raw decorator
- Four analyzers: failure pattern detection, token cost profiling, latency analysis, loop detection
- Rich terminal timeline reporter with collapsible spans
- Self-contained HTML trace visualiser
- JSON reporter for CI/CD and downstream tooling
- Typer CLI: `run`, `show`, `list`, `analyze`, `export`, `doctor`
- Full mypy strict + ruff clean codebase
