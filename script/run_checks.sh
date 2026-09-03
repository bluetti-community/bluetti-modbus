#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

cd "$ROOT_DIR"

echo "==> Installing project dependencies"
"$PYTHON_BIN" -m pip install --root-user-action=ignore -e ".[cli,cli-pymodbus]"

if ! "$PYTHON_BIN" -m ruff --version >/dev/null 2>&1; then
    echo "==> Installing Ruff"
    "$PYTHON_BIN" -m pip install --root-user-action=ignore ruff
fi

if ! "$PYTHON_BIN" -m mypy --version >/dev/null 2>&1; then
    echo "==> Installing mypy"
    "$PYTHON_BIN" -m pip install --root-user-action=ignore mypy
fi

if ! "$PYTHON_BIN" -c "import pytest, pytest_asyncio, pytest_cov" >/dev/null 2>&1; then
    echo "==> Installing test dependencies"
    "$PYTHON_BIN" -m pip install --root-user-action=ignore \
        "pytest>=8" "pytest-asyncio>=0.24" "pytest-cov>=5"
fi

echo "==> Checking formatting"
"$PYTHON_BIN" -m ruff format --check .

echo "==> Running Ruff"
"$PYTHON_BIN" -m ruff check .

echo "==> Running mypy --strict"
"$PYTHON_BIN" -m mypy

echo "==> Running tests (100% coverage required)"
# --cov-report=xml on top of term-missing, not instead of it: xml is for the
# editor's Coverage Gutters extension (see .devcontainer/devcontainer.json),
# term-missing is what a human reads in this script's own output.
"$PYTHON_BIN" -m pytest tests/ -v --cov=bluetti_modbus_lib --cov-report=term-missing --cov-report=xml --cov-fail-under=100

echo "==> All checks passed"
