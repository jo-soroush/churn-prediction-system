"""Tests for artifact loading behavior."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
REQUIRED_ARTIFACT_PATHS = [
    ARTIFACTS_DIR / "feature_schema.json",
    ARTIFACTS_DIR / "model_metadata.json",
    ARTIFACTS_DIR / "tree_preprocessor.pkl",
    ARTIFACTS_DIR / "xgb_model.json",
    ARTIFACTS_DIR / "mlp_model.pt",
    ARTIFACTS_DIR / "mlp_preprocessor.pkl",
    ARTIFACTS_DIR / "category_maps.json",
]


def test_required_artifact_files_exist() -> None:
    for artifact_path in REQUIRED_ARTIFACT_PATHS:
        assert artifact_path.exists()


def test_health_reports_all_artifact_resources_loaded() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200

    response_payload = response.json()
    assert response_payload["tree_model_loaded"] is True
    assert response_payload["tree_preprocessor_loaded"] is True
    assert response_payload["tree_feature_schema_loaded"] is True
    assert response_payload["mlp_model_loaded"] is True
    assert response_payload["mlp_preprocessor_loaded"] is True
    assert response_payload["mlp_category_maps_loaded"] is True
