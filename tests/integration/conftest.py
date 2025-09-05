"""Shared fixtures for integration tests."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def llm_fixtures_dir():
    """Get the LLM fixtures directory path."""
    return Path(__file__).parent.parent / "fixtures" / "llm_data"


@pytest.fixture
def fncall_raw_logs(llm_fixtures_dir):
    """Load function calling raw logs from real data."""
    logs = []
    log_dir = llm_fixtures_dir / "llm-logs"
    if log_dir.exists():
        for log_file in log_dir.glob("*.json"):
            with open(log_file) as f:
                logs.append(json.load(f))
    return logs


@pytest.fixture
def nonfncall_raw_logs(llm_fixtures_dir):
    """Load non-function calling raw logs from real data."""
    logs = []
    log_dir = llm_fixtures_dir / "nonfncall-llm-logs"
    if log_dir.exists():
        for log_file in log_dir.glob("*.json"):
            with open(log_file) as f:
                logs.append(json.load(f))
    return logs


# Removed cleaning function - working with raw data to understand real issues
