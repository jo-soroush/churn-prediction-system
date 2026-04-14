"""Tests for Phase 1 API key route protection."""

import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


SAMPLE_INPUT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "sample_input.json"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOP_LEVEL_KEYS = {"error"}
EXPECTED_ERROR_KEYS = {"type", "message", "details"}


def _load_payload() -> dict[str, object]:
    with SAMPLE_INPUT_PATH.open("r", encoding="utf-8-sig") as file_handle:
        return json.load(file_handle)


def _assert_unauthorized_response(payload: dict[str, object]) -> None:
    assert set(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert set(payload["error"].keys()) == EXPECTED_ERROR_KEYS
    assert payload["error"]["type"] == "unauthorized"
    assert payload["error"]["message"] == "Authentication required"
    assert payload["error"]["details"] is None


def test_public_health_does_not_require_api_key() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_public_health_v1_does_not_require_api_key() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_prediction_rejects_missing_api_key() -> None:
    with TestClient(app) as client:
        response = client.post("/predict/tree", json=_load_payload())

    assert response.status_code == 401
    _assert_unauthorized_response(response.json())


def test_protected_prediction_rejects_invalid_api_key() -> None:
    with TestClient(app) as client:
        response = client.post("/predict/tree", json=_load_payload(), headers={"X-API-Key": "wrong-key"})

    assert response.status_code == 401
    _assert_unauthorized_response(response.json())


def test_protected_prediction_allows_valid_api_key(auth_headers: dict[str, str]) -> None:
    with TestClient(app) as client:
        response = client.post("/predict/tree", json=_load_payload(), headers=auth_headers)

    assert response.status_code == 200


def test_protected_metadata_requires_valid_api_key(auth_headers: dict[str, str]) -> None:
    with TestClient(app) as client:
        missing_key_response = client.get("/metadata")
        valid_key_response = client.get("/metadata", headers=auth_headers)

    assert missing_key_response.status_code == 401
    _assert_unauthorized_response(missing_key_response.json())
    assert valid_key_response.status_code == 200


def test_protected_metrics_requires_valid_api_key(auth_headers: dict[str, str]) -> None:
    with TestClient(app) as client:
        missing_key_response = client.get("/metrics")
        valid_key_response = client.get("/metrics", headers=auth_headers)

    assert missing_key_response.status_code == 401
    _assert_unauthorized_response(missing_key_response.json())
    assert valid_key_response.status_code == 200


def test_auth_enabled_requires_configured_api_key() -> None:
    environment = os.environ.copy()
    environment["API_AUTH_ENABLED"] = "true"
    environment.pop("API_KEY", None)
    environment["PYTHONPATH"] = str(PROJECT_ROOT)

    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode != 0
    assert "API_KEY must be set when API_AUTH_ENABLED=true." in result.stderr
