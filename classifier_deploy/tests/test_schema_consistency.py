"""Tests for schema and category map consistency."""

import json
from pathlib import Path


ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
FEATURE_SCHEMA_PATH = ARTIFACTS_DIR / "feature_schema.json"
CATEGORY_MAPS_PATH = ARTIFACTS_DIR / "category_maps.json"
MODEL_METADATA_PATH = ARTIFACTS_DIR / "model_metadata.json"


def _load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def test_feature_schema_partitions_match_feature_columns() -> None:
    feature_schema = _load_json(FEATURE_SCHEMA_PATH)

    feature_columns = feature_schema["feature_columns"]
    numeric_features = feature_schema["numeric_features"]
    categorical_features = feature_schema["categorical_features"]

    assert isinstance(feature_columns, list)
    assert isinstance(numeric_features, list)
    assert isinstance(categorical_features, list)
    assert set(numeric_features).issubset(set(feature_columns))
    assert set(categorical_features).issubset(set(feature_columns))
    assert set(numeric_features).isdisjoint(set(categorical_features))
    assert set(feature_columns) == set(numeric_features) | set(categorical_features)


def test_tree_feature_names_follow_numeric_then_categorical_order() -> None:
    feature_schema = _load_json(FEATURE_SCHEMA_PATH)

    feature_columns = feature_schema["feature_columns"]
    numeric_features = feature_schema["numeric_features"]
    categorical_features = feature_schema["categorical_features"]
    tree_feature_names = feature_schema["tree_feature_names"]

    assert isinstance(tree_feature_names, list)
    assert set(tree_feature_names) == set(feature_columns)
    assert tree_feature_names == numeric_features + categorical_features


def test_category_maps_match_categorical_features() -> None:
    feature_schema = _load_json(FEATURE_SCHEMA_PATH)
    category_maps = _load_json(CATEGORY_MAPS_PATH)

    categorical_features = feature_schema["categorical_features"]
    category_map_feature_names = [key for key in category_maps if key != "category_mapping_version"]

    assert set(category_map_feature_names) == set(categorical_features)


def test_category_maps_include_unknown_token() -> None:
    feature_schema = _load_json(FEATURE_SCHEMA_PATH)
    category_maps = _load_json(CATEGORY_MAPS_PATH)

    categorical_features = feature_schema["categorical_features"]

    for feature_name in categorical_features:
        mapping = category_maps[feature_name]
        assert "__UNK__" in mapping
        assert mapping["__UNK__"] == 0


def test_model_metadata_versions_match_schema_artifacts() -> None:
    feature_schema = _load_json(FEATURE_SCHEMA_PATH)
    category_maps = _load_json(CATEGORY_MAPS_PATH)
    model_metadata = _load_json(MODEL_METADATA_PATH)

    assert model_metadata["schema_version"] == feature_schema["schema_version"]
    assert model_metadata["feature_order_version"] == feature_schema["feature_order_version"]
    assert model_metadata["category_mapping_version"] == category_maps["category_mapping_version"]
