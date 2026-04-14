"""Tests for deployment metadata endpoints."""

from fastapi.testclient import TestClient

from app.main import app


EXPECTED_METADATA_KEYS = {
    "artifact_bundle_version",
    "schema_version",
    "feature_order_version",
    "selection_protocol",
    "dependency_compatibility",
    "input_schema",
    "technical_models",
}

EXPECTED_SELECTION_PROTOCOL_KEYS = {
    "training_split",
    "selection_split",
    "final_reporting_split",
}

EXPECTED_RUNTIME_COMPATIBILITY_KEYS = {
    "python_version",
    "pytorch_version",
    "xgboost_version",
    "scikit_learn_version",
    "joblib_version",
    "pandas_version",
    "numpy_version",
    "notes",
}

EXPECTED_INPUT_SCHEMA_KEYS = {
    "feature_columns",
    "numeric_features",
    "categorical_features",
}

EXPECTED_TECHNICAL_MODEL_KEYS = {
    "tree_model_family",
    "tree_model_parameters",
    "neural_model_family",
    "neural_model_configuration",
}


def _assert_metadata_payload(payload: dict[str, object]) -> None:
    assert set(payload.keys()) == EXPECTED_METADATA_KEYS
    assert set(payload["selection_protocol"].keys()) == EXPECTED_SELECTION_PROTOCOL_KEYS
    assert set(payload["dependency_compatibility"].keys()) == EXPECTED_RUNTIME_COMPATIBILITY_KEYS
    assert set(payload["input_schema"].keys()) == EXPECTED_INPUT_SCHEMA_KEYS
    assert set(payload["technical_models"].keys()) == EXPECTED_TECHNICAL_MODEL_KEYS

    assert isinstance(payload["artifact_bundle_version"], str)
    assert isinstance(payload["schema_version"], str)
    assert isinstance(payload["feature_order_version"], str)
    assert isinstance(payload["input_schema"]["feature_columns"], list)
    assert isinstance(payload["input_schema"]["numeric_features"], list)
    assert isinstance(payload["input_schema"]["categorical_features"], list)

    metadata_text = str(payload)
    assert "validation_metrics" not in metadata_text
    assert "test_metrics" not in metadata_text


def test_metadata_returns_expected_shape(auth_headers: dict[str, str]) -> None:
    with TestClient(app) as client:
        response = client.get("/metadata", headers=auth_headers)

    assert response.status_code == 200
    _assert_metadata_payload(response.json())


def test_metadata_v1_returns_expected_shape(auth_headers: dict[str, str]) -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/metadata", headers=auth_headers)

    assert response.status_code == 200
    _assert_metadata_payload(response.json())
