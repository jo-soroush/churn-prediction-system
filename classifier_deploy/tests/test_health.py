"""Tests for health endpoints."""

from fastapi.testclient import TestClient

from app.main import app


EXPECTED_HEALTH_KEYS = {
    "status",
    "tree_model_loaded",
    "tree_preprocessor_loaded",
    "tree_feature_schema_loaded",
    "mlp_model_loaded",
    "mlp_preprocessor_loaded",
    "mlp_category_maps_loaded",
}

READINESS_KEYS = EXPECTED_HEALTH_KEYS - {"status"}


def test_health_returns_expected_shape_and_status() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()
    assert set(payload.keys()) == EXPECTED_HEALTH_KEYS
    assert payload["status"] == "ok"
    for key in READINESS_KEYS:
        assert isinstance(payload[key], bool)


def test_health_v1_returns_expected_shape_and_status() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200

    payload = response.json()
    assert set(payload.keys()) == EXPECTED_HEALTH_KEYS
    assert payload["status"] == "ok"
    for key in READINESS_KEYS:
        assert isinstance(payload[key], bool)
