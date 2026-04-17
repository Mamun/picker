# Contributing to StockIQ

Thank you for your interest in contributing! StockIQ is a community-driven project and every improvement — big or small — is appreciated.

## Table of Contents

- [Getting started](#getting-started)
- [Development setup](#development-setup)
- [Running tests](#running-tests)
- [Code style](#code-style)
- [Submitting a PR](#submitting-a-pr)
- [Reporting bugs](#reporting-bugs)
- [Suggesting features](#suggesting-features)

---

## Getting started

1. **Fork** the repository on GitHub.
2. **Clone** your fork:
   ```bash
   git clone https://github.com/<your-username>/stockiq.git
   cd stockiq
   ```
3. Create a feature branch:
   ```bash
   git checkout -b feat/your-feature-name
   ```

---

## Development setup

**Requirements:** Python 3.10+

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .               # installs stockiq package + all dependencies
pip install pytest pytest-cov ruff
```

Copy the Streamlit secrets template and add your API key:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml and set ANTHROPIC_API_KEY
```

Run the app locally:

```bash
streamlit run app.py
```

---

## Running tests

```bash
# All tests
pytest

# With coverage
pytest --cov=. --cov-report=term-missing

# A single file
pytest tests/test_indicators.py -v
```

Tests live in `tests/`. Pure-logic tests mock all network calls — no live market data or API keys required.

---

## Code style

We use [Ruff](https://github.com/astral-sh/ruff) for linting:

```bash
ruff check .
```

Key conventions used in this codebase:

- **Functions over classes** for stateless transformations
- **pandas-native operations** — avoid row-by-row Python loops where possible
- **`st.cache_data`** with explicit TTL on every function that hits the network
- Keep `views/` modules as thin Streamlit wrappers; business logic belongs in `indicators.py`, `signals.py`, or `data/`

---

## Submitting a PR

1. Make sure tests pass: `pytest`
2. Make sure the linter is happy: `ruff check .`
3. Push your branch and open a Pull Request against `main`
4. Fill in the PR template — link the relevant issue(s)
5. A maintainer will review within a few days

For large changes (new pages, new screeners, data-source changes), open a **Feature Request** issue first to discuss the approach before writing code.

---

## Reporting bugs

Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.yml) template on GitHub Issues. Include:

- Exact steps to reproduce
- The error message / traceback
- Your Python and Streamlit versions

---

## Suggesting features

Use the [Feature Request](.github/ISSUE_TEMPLATE/feature_request.yml) template. Describe:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you considered

---

## Code of Conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). All contributors are expected to follow it.
