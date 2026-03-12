# Contributing to Webhook Delivery Service

Thank you for your interest in contributing! This guide covers everything you need to get the project running locally, write tests, and submit a pull request.

---

## Table of Contents

1. [Development Setup](#1-development-setup)
2. [Pre-commit Hooks](#2-pre-commit-hooks)
3. [Running the Test Suite](#3-running-the-test-suite)
4. [Branching Strategy](#4-branching-strategy)
5. [PR Checklist](#5-pr-checklist)

---

## 1. Development Setup

### Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Python | 3.12 | [pyenv](https://github.com/pyenv/pyenv) or system package |
| Docker | 24.x | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Docker Compose V2 | 2.x | bundled with Docker Desktop |

### Clone and configure

```bash
git clone https://github.com/<your-org>/webhook-delivery.git
cd webhook-delivery

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Copy and edit environment config
cp .env.example .env
# At minimum, set a real JWT_SECRET:
python -c "import secrets; print(secrets.token_hex(32))"
```

### Start dev infrastructure

```bash
# PostgreSQL on port 5433, Redis on port 6379
docker compose -f docker/docker-compose.dev.yml up -d

# Apply migrations to both main and test databases
alembic upgrade head
```

### Verify your setup

```bash
# Run the unit tests (no live services required)
pytest tests/unit/ -q

# Run the API locally (optional)
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/health
```

---

## 2. Pre-commit Hooks

Pre-commit hooks enforce code quality before every commit. Install them once:

```bash
pre-commit install
```

The hooks run automatically on `git commit`. To run them manually:

```bash
pre-commit run --all-files
```

### What the hooks do

| Hook | Purpose |
|---|---|
| `ruff` | Lint for errors, style, and security issues |
| `ruff-format` | Auto-format code (replaces Black) |
| `mypy` | Static type checking (strict mode) |
| `trailing-whitespace` | Remove trailing whitespace |
| `end-of-file-fixer` | Ensure files end with a newline |
| `check-merge-conflict` | Reject commits with unresolved merge markers |

---

## 3. Running the Test Suite

### Test layout

```
tests/
├── unit/           # Fully mocked — no live services required
└── integration/    # Require dev containers (Postgres + Redis)
```

### Unit tests

```bash
pytest tests/unit/ -v
```

### Integration tests

Dev containers must be running first (see [Development Setup](#1-development-setup)).

```bash
pytest tests/integration/ -v -m integration
```

### Full suite with coverage report

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

Coverage must remain **≥ 85%**. The CI gate enforces `--cov-fail-under=85`.

### Lint and type checks

```bash
ruff check .       # check for issues
ruff format .      # auto-format
mypy app/          # strict type checking
```

All three must pass before a PR is merged.

### TDD discipline

This project follows strict TDD. Before writing any production code:

1. **Write a failing test first** (red).
2. **Make it pass with the minimum change** (green).
3. **Refactor under green** — only clean up when all tests pass.

See `docs/ROADMAP.md` for the full TDD discipline contract.

---

## 4. Branching Strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready code. All CI checks must pass. |
| `feature/<short-description>` | New features or enhancements |
| `fix/<short-description>` | Bug fixes |
| `docs/<short-description>` | Documentation-only changes |
| `chore/<short-description>` | Dependency bumps, config changes |

### Branch naming examples

```
feature/subscriber-bulk-import
fix/delivery-detached-instance-error
docs/adr-002-dual-drivers
chore/bump-fastapi-0-116
```

### Merge policy

- All PRs target `main`.
- Squash merge is preferred for feature branches to keep `main` history clean.
- Merge commits are used for release branches.

---

## 5. PR Checklist

Before requesting a review, confirm all items below:

### Code quality

- [ ] All new code has corresponding tests (red → green → refactor).
- [ ] `pytest tests/ --cov=app` passes with coverage ≥ 85%.
- [ ] `ruff check .` reports no errors.
- [ ] `ruff format .` reports nothing to reformat (or was run and committed).
- [ ] `mypy app/` reports no errors.
- [ ] Pre-commit hooks pass on all changed files.

### Documentation

- [ ] All new public functions and classes have Google-style docstrings.
- [ ] New environment variables are documented in `.env.example` and `README.md`.
- [ ] Significant architectural decisions are captured in a new ADR under `docs/adr/`.
- [ ] `CHANGELOG.md` `[Unreleased]` section is updated.

### Tests

- [ ] No `pytest.mark.skip` without a linked GitHub issue.
- [ ] Integration tests use the `@pytest.mark.integration` marker.
- [ ] Docker-dependent tests use the `@pytest.mark.docker` marker.
- [ ] New fixtures are documented with a docstring explaining their purpose.

### Review

- [ ] PR description explains *why* the change is needed, not just *what* it does.
- [ ] Breaking changes are called out explicitly in the PR description.
- [ ] The PR is scoped to a single concern (one feature or fix per PR).
