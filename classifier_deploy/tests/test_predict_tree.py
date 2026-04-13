"""Tests for the tree prediction endpoints."""

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import app.predict as predict_module
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
EXPECTED_TOP_FEATURE_KEYS = {"feature", "display_name", "shap_value", "direction"}
EXPECTED_DIRECTIONS = {"increases_churn_score", "decreases_churn_score"}


def _load_payload() -> dict[str, object]:
    with SAMPLE_INPUT_PATH.open("r", encoding="utf-8-sig") as file_handle:
        return json.load(file_handle)


@pytest.mark.parametrize("path", ["/predict/tree", "/api/v1/predict/tree"])
def test_predict_tree_returns_transitional_contract(path: str) -> None:
    payload = _load_payload()

    with TestClient(app) as client:
        response = client.post(path, json=payload)

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
        "model_key": "tree",
        "model_name": "XGBoost",
        "model_family": "xgboost",
        "artifact_set": "active",
    }

    assert set(response_payload["prediction_result"].keys()) == EXPECTED_PREDICTION_RESULT_KEYS
    assert response_payload["prediction_result"]["label"] in {"positive", "negative"}
    assert isinstance(response_payload["prediction_result"]["probability"], float)
    assert response_payload["prediction_result"]["threshold"] == 0.5
    assert response_payload["prediction_result"]["threshold_rule"] == "probability >= threshold => positive"

    assert set(response_payload["interpretation_basis"].keys()) == EXPECTED_INTERPRETATION_KEYS
    assert response_payload["interpretation_basis"]["label_source"] == "thresholded_probability"
    assert isinstance(response_payload["interpretation_basis"]["notes"], list)

    assert set(response_payload["explanation"].keys()) == EXPECTED_EXPLANATION_KEYS
    assert isinstance(response_payload["explanation"]["available"], bool)
    assert response_payload["explanation"]["method"] == "shap_tree"
    assert isinstance(response_payload["explanation"]["notes"], list)
    assert len(response_payload["explanation"]["notes"]) >= 1
    assert isinstance(response_payload["explanation"]["top_features"], list)

    if response_payload["explanation"]["available"] is True:
        assert response_payload["interpretation_basis"]["feature_level_explanation_available"] is True
        assert len(response_payload["interpretation_basis"]["notes"]) >= 2
        assert 1 <= len(response_payload["explanation"]["top_features"]) <= 5

        for feature in response_payload["explanation"]["top_features"]:
            assert set(feature.keys()) == EXPECTED_TOP_FEATURE_KEYS
            assert isinstance(feature["feature"], str)
            assert feature["feature"]
            assert isinstance(feature["display_name"], str)
            assert feature["display_name"]
            assert isinstance(feature["shap_value"], float)
            assert feature["direction"] in EXPECTED_DIRECTIONS
            if feature["shap_value"] > 0:
                assert feature["direction"] == "increases_churn_score"
            else:
                assert feature["direction"] == "decreases_churn_score"
    else:
        assert response_payload["interpretation_basis"]["feature_level_explanation_available"] is False
        assert response_payload["explanation"]["top_features"] == []
        assert len(response_payload["interpretation_basis"]["notes"]) >= 2

    if response_payload["prediction_result"]["probability"] >= response_payload["prediction_result"]["threshold"]:
        assert response_payload["prediction_result"]["label"] == "positive"
    else:
        assert response_payload["prediction_result"]["label"] == "negative"


class _FakeExplanation:
    def __init__(self, values: np.ndarray):
        self.values = values


def test_predict_tree_explanation_uses_top_k_and_direction_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _load_payload()

    with TestClient(app) as client:
        feature_count = len(predict_module.tree_feature_schema["tree_feature_names"])
        fake_values = np.zeros((1, feature_count), dtype=float)
        fake_values[0, :6] = np.array([0.40, -0.35, 0.30, -0.25, 0.20, -0.15])

        class _FakeExplainer:
            def __call__(self, transformed_frame):
                return _FakeExplanation(fake_values)

        monkeypatch.setattr(predict_module, "tree_shap_explainer", _FakeExplainer())
        monkeypatch.setattr(predict_module, "tree_shap_status_message", None)

        response = client.post("/predict/tree", json=payload)

    assert response.status_code == 200
    explanation = response.json()["explanation"]

    assert explanation["available"] is True
    assert explanation["method"] == "shap_tree"
    assert len(explanation["top_features"]) == 5
    assert [feature["shap_value"] for feature in explanation["top_features"]] == [0.4, -0.35, 0.3, -0.25, 0.2]
    assert [feature["direction"] for feature in explanation["top_features"]] == [
        "increases_churn_score",
        "decreases_churn_score",
        "increases_churn_score",
        "decreases_churn_score",
        "increases_churn_score",
    ]


def test_predict_tree_returns_honest_unavailable_explanation_when_explainer_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _load_payload()

    with TestClient(app) as client:
        monkeypatch.setattr(predict_module, "tree_shap_explainer", None)
        monkeypatch.setattr(
            predict_module,
            "tree_shap_status_message",
            "Tree SHAP explainability is unavailable because the runtime explainer is not initialized.",
        )

        response = client.post("/predict/tree", json=payload)

    assert response.status_code == 200
    explanation = response.json()["explanation"]
    interpretation_basis = response.json()["interpretation_basis"]

    assert explanation["available"] is False
    assert explanation["method"] == "shap_tree"
    assert explanation["top_features"] == []
    assert explanation["notes"] == [
        "Tree SHAP explainability is unavailable because the runtime explainer is not initialized."
    ]
    assert interpretation_basis["feature_level_explanation_available"] is False
