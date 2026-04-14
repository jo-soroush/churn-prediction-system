"""Tests for the MLP prediction endpoints."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


SAMPLE_INPUT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "sample_input.json"
EXPECTED_RESPONSE_KEYS = {
    "request",
    "contract",
    "model",
    "prediction_result",
    "interpretation_basis",
    "explanation",
}
EXPECTED_REQUEST_KEYS = {"request_id", "timestamp_utc"}
EXPECTED_CONTRACT_KEYS = {"contract_version", "schema_version"}
EXPECTED_MODEL_KEYS = {"model_key", "model_name", "model_family", "artifact_set"}
EXPECTED_PREDICTION_RESULT_KEYS = {"label", "probability", "threshold", "threshold_rule"}
EXPECTED_INTERPRETATION_KEYS = {"label_source", "feature_level_explanation_available", "notes"}
EXPECTED_EXPLANATION_KEYS = {"available", "method", "top_features", "notes"}


def _load_payload() -> dict[str, object]:
    with SAMPLE_INPUT_PATH.open("r", encoding="utf-8-sig") as file_handle:
        return json.load(file_handle)


@pytest.mark.parametrize("path", ["/predict/mlp", "/api/v1/predict/mlp"])
def test_predict_mlp_returns_transitional_contract(path: str, auth_headers: dict[str, str]) -> None:
    payload = _load_payload()

    with TestClient(app) as client:
        response = client.post(path, json=payload, headers=auth_headers)

    assert response.status_code == 200

    response_payload = response.json()
    assert set(response_payload.keys()) == EXPECTED_RESPONSE_KEYS

    assert set(response_payload["request"].keys()) == EXPECTED_REQUEST_KEYS
    assert isinstance(response_payload["request"]["request_id"], str)
    assert response_payload["request"]["request_id"]
    assert isinstance(response_payload["request"]["timestamp_utc"], str)
    assert response_payload["request"]["timestamp_utc"].endswith("Z")

    assert set(response_payload["contract"].keys()) == EXPECTED_CONTRACT_KEYS
    assert response_payload["contract"]["contract_version"] == "v2"
    assert isinstance(response_payload["contract"]["schema_version"], str)
    assert response_payload["contract"]["schema_version"]

    assert set(response_payload["model"].keys()) == EXPECTED_MODEL_KEYS
    assert response_payload["model"] == {
        "model_key": "mlp",
        "model_name": "PyTorch MLP with embeddings",
        "model_family": "pytorch_mlp",
        "artifact_set": "active",
    }

    assert set(response_payload["prediction_result"].keys()) == EXPECTED_PREDICTION_RESULT_KEYS
    assert response_payload["prediction_result"]["label"] in {"positive", "negative"}
    assert isinstance(response_payload["prediction_result"]["probability"], float)
    assert response_payload["prediction_result"]["threshold"] == 0.5
    assert response_payload["prediction_result"]["threshold_rule"] == "probability >= threshold => positive"

    assert set(response_payload["interpretation_basis"].keys()) == EXPECTED_INTERPRETATION_KEYS
    assert response_payload["interpretation_basis"]["label_source"] == "thresholded_probability"
    assert response_payload["interpretation_basis"]["feature_level_explanation_available"] is False
    assert isinstance(response_payload["interpretation_basis"]["notes"], list)
    assert len(response_payload["interpretation_basis"]["notes"]) >= 2

    assert set(response_payload["explanation"].keys()) == EXPECTED_EXPLANATION_KEYS
    assert response_payload["explanation"]["available"] is False
    assert response_payload["explanation"]["method"] is None
    assert response_payload["explanation"]["top_features"] == []
    assert isinstance(response_payload["explanation"]["notes"], list)
    assert len(response_payload["explanation"]["notes"]) >= 1

    if response_payload["prediction_result"]["probability"] >= response_payload["prediction_result"]["threshold"]:
        assert response_payload["prediction_result"]["label"] == "positive"
    else:
        assert response_payload["prediction_result"]["label"] == "negative"
