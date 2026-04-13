"""Pre-runtime integrity checks for shipped model artifacts."""

import json
from pathlib import Path

import joblib
import torch
import torch.nn as nn
from xgboost import XGBClassifier

from app.predict import build_mlp_model_from_checkpoint


ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
FEATURE_SCHEMA_PATH = ARTIFACTS_DIR / "feature_schema.json"
CATEGORY_MAPS_PATH = ARTIFACTS_DIR / "category_maps.json"
SAMPLE_INPUT_PATH = ARTIFACTS_DIR / "sample_input.json"
TREE_PREPROCESSOR_PATH = ARTIFACTS_DIR / "tree_preprocessor.pkl"
XGB_MODEL_PATH = ARTIFACTS_DIR / "xgb_model.json"
MLP_MODEL_PATH = ARTIFACTS_DIR / "mlp_model.pt"
MLP_PREPROCESSOR_PATH = ARTIFACTS_DIR / "mlp_preprocessor.pkl"


def _load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8-sig") as file_handle:
        payload = json.load(file_handle)

    assert isinstance(payload, dict)
    assert payload
    return payload


def test_sample_input_matches_feature_schema() -> None:
    feature_schema = _load_json(FEATURE_SCHEMA_PATH)
    sample_input = _load_json(SAMPLE_INPUT_PATH)

    assert set(sample_input.keys()) == set(feature_schema["feature_columns"])


def test_preprocessor_artifacts_load_with_expected_contract() -> None:
    feature_schema = _load_json(FEATURE_SCHEMA_PATH)

    tree_preprocessor = joblib.load(TREE_PREPROCESSOR_PATH)
    assert hasattr(tree_preprocessor, "transform")
    assert hasattr(tree_preprocessor, "get_feature_names_out")
    assert list(tree_preprocessor.get_feature_names_out()) == feature_schema["tree_feature_names"]

    mlp_preprocessor = joblib.load(MLP_PREPROCESSOR_PATH)
    assert set(mlp_preprocessor.keys()) == {
        "categorical_features",
        "numeric_features",
        "numeric_imputer",
        "numeric_scaler",
    }
    assert mlp_preprocessor["categorical_features"] == feature_schema["categorical_features"]
    assert mlp_preprocessor["numeric_features"] == feature_schema["numeric_features"]
    assert hasattr(mlp_preprocessor["numeric_imputer"], "transform")
    assert hasattr(mlp_preprocessor["numeric_scaler"], "transform")


def test_tree_model_artifact_loads_with_expected_feature_count() -> None:
    feature_schema = _load_json(FEATURE_SCHEMA_PATH)

    model = XGBClassifier()
    model.load_model(XGB_MODEL_PATH)

    assert list(model.classes_) == [0, 1]
    assert model.n_features_in_ == len(feature_schema["tree_feature_names"])


def test_mlp_checkpoint_loads_and_matches_feature_contract() -> None:
    feature_schema = _load_json(FEATURE_SCHEMA_PATH)
    category_maps = _load_json(CATEGORY_MAPS_PATH)

    checkpoint = torch.load(MLP_MODEL_PATH, map_location="cpu")

    expected_keys = {
        "cardinalities",
        "categorical_features",
        "dropout",
        "feature_order",
        "hidden_dims",
        "model_state_dict",
        "numeric_feature_count",
        "numeric_features",
    }
    assert set(checkpoint.keys()) == expected_keys
    assert checkpoint["feature_order"] == feature_schema["feature_columns"]
    assert checkpoint["categorical_features"] == feature_schema["categorical_features"]
    assert checkpoint["numeric_features"] == feature_schema["numeric_features"]
    assert checkpoint["numeric_feature_count"] == len(feature_schema["numeric_features"])
    assert len(checkpoint["cardinalities"]) == len(feature_schema["categorical_features"])
    assert checkpoint["model_state_dict"]

    category_cardinalities = [
        len(category_maps[feature_name]) for feature_name in feature_schema["categorical_features"]
    ]
    assert checkpoint["cardinalities"] == category_cardinalities

    model = build_mlp_model_from_checkpoint(checkpoint)
    assert isinstance(model, nn.Module)
