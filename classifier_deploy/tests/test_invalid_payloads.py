"""Tests for invalid request payload handling."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


SAMPLE_INPUT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "sample_input.json"
EXPECTED_TOP_LEVEL_KEYS = {"error"}
EXPECTED_ERROR_KEYS = {"type", "message", "details"}


def _load_invalid_payload() -> dict[str, object]:
    with SAMPLE_INPUT_PATH.open("r", encoding="utf-8-sig") as file_handle:
        payload = json.load(file_handle)

    payload.pop("gender")
    return payload


@pytest.mark.parametrize("path", ["/predict/tree", "/api/v1/predict/tree"])
def test_predict_tree_invalid_payload_returns_validation_error(path: str, auth_headers: dict[str, str]) -> None:
    invalid_payload = _load_invalid_payload()

    with TestClient(app) as client:
        response = client.post(path, json=invalid_payload, headers=auth_headers)

    assert response.status_code == 422

    response_payload = response.json()
    assert set(response_payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert set(response_payload["error"].keys()) == EXPECTED_ERROR_KEYS
    assert response_payload["error"]["type"] == "validation_error"
    assert response_payload["error"]["message"] == "Request validation failed"
    assert isinstance(response_payload["error"]["details"], list)
    assert any(error.get("loc") == ["body", "gender"] for error in response_payload["error"]["details"])


@pytest.mark.parametrize("path", ["/predict/mlp", "/api/v1/predict/mlp"])
def test_predict_mlp_invalid_payload_returns_validation_error(path: str, auth_headers: dict[str, str]) -> None:
    invalid_payload = _load_invalid_payload()

    with TestClient(app) as client:
        response = client.post(path, json=invalid_payload, headers=auth_headers)

    assert response.status_code == 422

    response_payload = response.json()
    assert set(response_payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert set(response_payload["error"].keys()) == EXPECTED_ERROR_KEYS
    assert response_payload["error"]["type"] == "validation_error"
    assert response_payload["error"]["message"] == "Request validation failed"
    assert isinstance(response_payload["error"]["details"], list)
    assert any(error.get("loc") == ["body", "gender"] for error in response_payload["error"]["details"])
