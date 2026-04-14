"""Shared pytest fixtures for the classifier deployment test layer."""

import os
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_API_KEY = "test-phase-1-api-key"

os.environ.setdefault("API_AUTH_ENABLED", "true")
os.environ.setdefault("API_KEY", TEST_API_KEY)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": TEST_API_KEY}
