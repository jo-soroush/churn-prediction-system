from typing import Any
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from time import perf_counter

from fastapi import APIRouter, HTTPException, Request

from app.logging_config import get_logger
from app.metrics import (
    record_model_inference_error,
    record_model_inference_finished,
    record_model_inference_started,
)
from app.schemas import (
    InterpretationBasis,
    PredictionContractMetadata,
    PredictionExplanationBody,
    PredictionExplanationFeature,
    PredictionModelMetadata,
    PredictionRequestMetadata,
    PredictionResultBody,
    TreePredictionRequest,
    TreePredictionResponse,
)

try:
    import shap
except Exception:  # pragma: no cover - exercised through runtime status handling
    shap = None


router = APIRouter()
logger = get_logger("assignment2.api")
CONTRACT_VERSION = "v2"
PREDICTION_THRESHOLD = 0.5
PREDICTION_THRESHOLD_RULE = "probability >= threshold => positive"
TREE_EXPLANATION_METHOD = "shap_tree"
TREE_EXPLANATION_TOP_K = 5
BASE_INTERPRETATION_NOTES = [
    "The returned label is derived from the model probability using the current threshold rule.",
]
TREE_EXPLANATION_NOTES = [
    "SHAP values describe how transformed feature values influenced the tree model output relative to the model baseline.",
    "Positive SHAP values increased the tree model's churn score and negative SHAP values decreased it.",
    "SHAP values are model-specific contribution values, not causal effects.",
]
MLP_EXPLANATION_UNAVAILABLE_NOTES = [
    "Feature-level explanation is not available for the deployed MLP endpoint.",
    "The current API exposes per-request SHAP explanations only for the deployed tree model.",
]
FEATURE_DISPLAY_NAMES = {
    "gender": "Gender",
    "seniorcitizen": "Senior Citizen",
    "partner": "Partner",
    "dependents": "Dependents",
    "tenure": "Tenure (Months)",
    "phoneservice": "Phone Service",
    "multiplelines": "Multiple Lines",
    "internetservice": "Internet Service",
    "onlinesecurity": "Online Security",
    "onlinebackup": "Online Backup",
    "deviceprotection": "Device Protection",
    "techsupport": "Tech Support",
    "streamingtv": "Streaming TV",
    "streamingmovies": "Streaming Movies",
    "contract": "Contract",
    "paperlessbilling": "Paperless Billing",
    "paymentmethod": "Payment Method",
    "monthlycharges": "Monthly Charges",
    "totalcharges": "Total Charges",
}

# These are initialized by app.main at startup.
tree_feature_schema: dict[str, Any] | None = None
tree_preprocessor = None
tree_model = None
tree_shap_explainer = None
tree_shap_status_message: str | None = None
mlp_preprocessor: dict[str, Any] | None = None
mlp_category_maps: dict[str, dict[str, int]] | None = None
mlp_checkpoint: dict[str, Any] | None = None
mlp_model: nn.Module | None = None
mlp_device: torch.device | None = None


def _elapsed_ms(start_time: float) -> float:
    return (perf_counter() - start_time) * 1000


def _log_prediction_timing(
    request: Request,
    *,
    model_name: str,
    preprocessing_ms: float,
    inference_ms: float,
    response_ms: float,
    explanation_ms: float | None = None,
) -> None:
    request_id = getattr(request.state, "request_id", "unknown")
    total_components_ms = preprocessing_ms + inference_ms + response_ms
    if explanation_ms is not None:
        total_components_ms += explanation_ms

    logger.info(
        "Prediction timing: method=%s path=%s request_id=%s model=%s preprocessing_ms=%.2f inference_ms=%.2f explanation_ms=%s response_ms=%.2f handler_total_ms=%.2f",
        request.method,
        request.url.path,
        request_id,
        model_name,
        preprocessing_ms,
        inference_ms,
        f"{explanation_ms:.2f}" if explanation_ms is not None else "n/a",
        response_ms,
        total_components_ms,
    )


class MLPWithEmbeddings(nn.Module):
    def __init__(
        self,
        cardinalities: list[int],
        embedding_dims: list[int],
        numeric_feature_count: int,
        hidden_dims: list[int],
        dropout: float,
    ):
        super().__init__()
        self.embedding_layers = nn.ModuleList(
            [nn.Embedding(cardinality, embedding_dim) for cardinality, embedding_dim in zip(cardinalities, embedding_dims)]
        )
        embedded_dim = sum(embedding_dims)
        input_dim = embedded_dim + numeric_feature_count

        layers: list[nn.Module] = []
        previous_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend([nn.Linear(previous_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout)])
            previous_dim = hidden_dim
        layers.append(nn.Linear(previous_dim, 1))
        self.network = nn.Sequential(*layers)

    def forward(self, categorical_inputs: torch.Tensor, numeric_inputs: torch.Tensor) -> torch.Tensor:
        if len(self.embedding_layers) > 0:
            embedded = [embedding(categorical_inputs[:, index]) for index, embedding in enumerate(self.embedding_layers)]
            embedded = torch.cat(embedded, dim=1)
            combined = torch.cat([embedded, numeric_inputs], dim=1)
        else:
            combined = numeric_inputs
        return self.network(combined).squeeze(1)


def _log_inference_error(request: Request, model_name: str, exc: Exception) -> None:
    duration_ms = None
    start_time = getattr(request.state, "request_start_time", None)
    if start_time is not None:
        duration_ms = (perf_counter() - start_time) * 1000

    if duration_ms is None:
        logger.error(
            "Inference error: method=%s path=%s model=%s status=500 error=%s exception_type=%s",
            request.method,
            request.url.path,
            model_name,
            "Prediction failed",
            type(exc).__name__,
        )
    else:
        logger.error(
            "Inference error: method=%s path=%s model=%s status=500 error=%s exception_type=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            model_name,
            "Prediction failed",
            type(exc).__name__,
            duration_ms,
        )


def build_mlp_model_from_checkpoint(checkpoint: dict[str, Any]) -> MLPWithEmbeddings:
    state_dict = checkpoint["model_state_dict"]
    cardinalities = [int(value) for value in checkpoint["cardinalities"]]
    embedding_dims = [state_dict[f"embedding_layers.{index}.weight"].shape[1] for index in range(len(cardinalities))]

    model = MLPWithEmbeddings(
        cardinalities=cardinalities,
        embedding_dims=embedding_dims,
        numeric_feature_count=int(checkpoint["numeric_feature_count"]),
        hidden_dims=[int(value) for value in checkpoint["hidden_dims"]],
        dropout=float(checkpoint["dropout"]),
    )
    model.load_state_dict(state_dict)
    return model


def _require_tree_feature_schema() -> dict[str, Any]:
    if tree_feature_schema is None:
        raise RuntimeError("Tree feature schema is not loaded.")
    return tree_feature_schema


def _require_tree_preprocessor() -> Any:
    if tree_preprocessor is None:
        raise RuntimeError("Tree preprocessor is not loaded.")
    return tree_preprocessor


def _require_mlp_preprocessor() -> dict[str, Any]:
    if mlp_preprocessor is None:
        raise RuntimeError("MLP preprocessor is not loaded.")
    return mlp_preprocessor


def _require_mlp_category_maps() -> dict[str, dict[str, int]]:
    if mlp_category_maps is None:
        raise RuntimeError("MLP category maps are not loaded.")
    return mlp_category_maps


def _require_mlp_model() -> nn.Module:
    if mlp_model is None:
        raise RuntimeError("MLP model is not loaded.")
    return mlp_model


def _require_mlp_device() -> torch.device:
    if mlp_device is None:
        raise RuntimeError("MLP device is not configured.")
    return mlp_device


def _build_prediction_response(
    request: Request,
    *,
    model_key: str,
    model_name: str,
    model_family: str,
    prediction: str,
    probability: float,
    interpretation_notes: list[str],
    feature_level_explanation_available: bool,
    explanation: PredictionExplanationBody,
) -> TreePredictionResponse:
    feature_schema = _require_tree_feature_schema()

    request_id = getattr(request.state, "request_id", "unknown")
    timestamp_utc = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rounded_probability = round(probability, 6)

    return TreePredictionResponse(
        request=PredictionRequestMetadata(
            request_id=request_id,
            timestamp_utc=timestamp_utc,
        ),
        contract=PredictionContractMetadata(
            contract_version=CONTRACT_VERSION,
            schema_version=str(feature_schema.get("schema_version", "unknown")),
        ),
        model=PredictionModelMetadata(
            model_key=model_key,
            model_name=model_name,
            model_family=model_family,
            artifact_set="active",
        ),
        prediction_result=PredictionResultBody(
            label=prediction,
            probability=rounded_probability,
            threshold=PREDICTION_THRESHOLD,
            threshold_rule=PREDICTION_THRESHOLD_RULE,
        ),
        interpretation_basis=InterpretationBasis(
            label_source="thresholded_probability",
            feature_level_explanation_available=feature_level_explanation_available,
            notes=interpretation_notes,
        ),
        explanation=explanation,
    )


def _build_tree_explainability_validation_frame() -> pd.DataFrame:
    feature_schema = _require_tree_feature_schema()

    row: dict[str, object] = {}
    numeric_features = set(feature_schema["numeric_features"])
    categorical_features = set(feature_schema["categorical_features"])
    for feature in feature_schema["feature_columns"]:
        if feature in numeric_features:
            row[feature] = 0.0
        elif feature in categorical_features:
            row[feature] = "missing"
        else:
            row[feature] = None
    return pd.DataFrame([row], columns=feature_schema["feature_columns"])


def validate_tree_explainability_setup() -> list[str]:
    if tree_feature_schema is None or tree_preprocessor is None:
        return ["Tree explainability validation could not run because tree artifacts are not loaded."]

    tree_feature_names = tree_feature_schema.get("tree_feature_names")
    if not isinstance(tree_feature_names, list) or not tree_feature_names:
        return ["Feature schema is missing a non-empty tree_feature_names list."]

    validation_errors: list[str] = []

    if hasattr(tree_preprocessor, "get_feature_names_out"):
        runtime_feature_names = list(tree_preprocessor.get_feature_names_out())
        if runtime_feature_names != tree_feature_names:
            validation_errors.append("Tree feature schema names do not match the runtime preprocessor output names.")

    try:
        validation_frame = _build_tree_explainability_validation_frame()
        transformed_features = tree_preprocessor.transform(validation_frame)
    except Exception as exc:
        validation_errors.append(
            f"Tree explainability validation row could not be transformed: {type(exc).__name__}: {exc}"
        )
        return validation_errors

    transformed_array = np.asarray(transformed_features)
    if transformed_array.ndim != 2:
        validation_errors.append(
            f"Tree explainability validation transform returned ndim={transformed_array.ndim}, expected 2."
        )
    elif transformed_array.shape[1] != len(tree_feature_names):
        validation_errors.append(
            "Tree explainability validation transform width does not match feature_schema.tree_feature_names."
        )

    return validation_errors


def initialize_tree_shap_explainer() -> None:
    global tree_shap_explainer
    global tree_shap_status_message

    tree_shap_explainer = None

    validation_errors = validate_tree_explainability_setup()
    if validation_errors:
        tree_shap_status_message = " ".join(validation_errors)
        logger.warning("Tree SHAP explainability disabled: %s", tree_shap_status_message)
        return

    if shap is None:
        tree_shap_status_message = "Tree SHAP explainability is unavailable because the SHAP runtime dependency is not installed."
        logger.warning("Tree SHAP explainability disabled: %s", tree_shap_status_message)
        return

    try:
        tree_shap_explainer = shap.TreeExplainer(tree_model)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        tree_shap_status_message = (
            f"Tree SHAP explainability is unavailable because explainer initialization failed: {type(exc).__name__}: {exc}"
        )
        logger.warning("Tree SHAP explainability disabled: %s", tree_shap_status_message)
        return

    tree_shap_status_message = None
    logger.info("Tree SHAP explainability initialized successfully")


def _build_tree_transformed_frame(input_frame: pd.DataFrame) -> pd.DataFrame:
    preprocessor = _require_tree_preprocessor()
    feature_schema = _require_tree_feature_schema()

    tree_feature_names = feature_schema["tree_feature_names"]
    transformed_features = preprocessor.transform(input_frame)
    transformed_array = np.asarray(transformed_features)
    return pd.DataFrame(transformed_array, columns=tree_feature_names)


def _normalize_tree_shap_values(shap_output: object) -> np.ndarray:
    shap_values = shap_output.values if hasattr(shap_output, "values") else shap_output
    if isinstance(shap_values, list):
        shap_values = shap_values[-1]

    shap_array = np.asarray(shap_values, dtype=float)
    if shap_array.ndim == 3:
        shap_array = shap_array[:, :, -1]
    elif shap_array.ndim == 1:
        shap_array = shap_array.reshape(1, -1)

    if shap_array.ndim != 2:
        raise ValueError(f"Unexpected SHAP output ndim={shap_array.ndim}; expected a 2D array.")

    return shap_array


def _build_unavailable_explanation(*, method: str | None, notes: list[str]) -> PredictionExplanationBody:
    return PredictionExplanationBody(available=False, method=method, top_features=[], notes=notes)


def _build_tree_explanation(transformed_frame: pd.DataFrame) -> PredictionExplanationBody:
    feature_schema = _require_tree_feature_schema()

    if tree_shap_explainer is None:
        explanation_notes = [tree_shap_status_message or "Tree SHAP explainability is unavailable in the current runtime."]
        return _build_unavailable_explanation(method=TREE_EXPLANATION_METHOD, notes=explanation_notes)

    try:
        shap_output = tree_shap_explainer(transformed_frame)
        shap_values = _normalize_tree_shap_values(shap_output)
    except Exception as exc:
        explanation_notes = [
            f"Tree SHAP explainability could not be computed for this request: {type(exc).__name__}: {exc}"
        ]
        return _build_unavailable_explanation(method=TREE_EXPLANATION_METHOD, notes=explanation_notes)

    row_values = shap_values[0]
    feature_names = feature_schema["tree_feature_names"]
    ranked_indices = np.argsort(np.abs(row_values))[::-1]

    top_features: list[PredictionExplanationFeature] = []
    for index in ranked_indices:
        shap_value = float(row_values[index])
        if np.isclose(shap_value, 0.0):
            continue

        feature_name = feature_names[index]
        top_features.append(
            PredictionExplanationFeature(
                feature=feature_name,
                display_name=FEATURE_DISPLAY_NAMES.get(feature_name, feature_name),
                shap_value=round(shap_value, 6),
                direction="increases_churn_score" if shap_value > 0 else "decreases_churn_score",
            )
        )
        if len(top_features) == TREE_EXPLANATION_TOP_K:
            break

    if not top_features:
        return _build_unavailable_explanation(
            method=TREE_EXPLANATION_METHOD,
            notes=["Tree SHAP explainability produced no non-zero feature contributions for this request."],
        )

    return PredictionExplanationBody(
        available=True,
        method=TREE_EXPLANATION_METHOD,
        top_features=top_features,
        notes=TREE_EXPLANATION_NOTES,
    )


@router.post("/predict/mlp", response_model=TreePredictionResponse)
def predict_mlp(request: Request, payload: TreePredictionRequest) -> TreePredictionResponse:
    _ensure_mlp_resources_loaded()
    inference_start: float | None = None

    try:
        preprocessing_start = perf_counter()
        input_frame = _build_tree_input_frame(payload)
        categorical_tensor, numeric_tensor = _build_mlp_tensors(input_frame)
        preprocessing_ms = _elapsed_ms(preprocessing_start)

        model = _require_mlp_model()

        inference_start = record_model_inference_started("mlp")
        try:
            with torch.inference_mode():
                logits = model(categorical_tensor, numeric_tensor)
                probability = float(torch.sigmoid(logits).cpu().item())
        except Exception:
            record_model_inference_error("mlp")
            raise
        finally:
            if inference_start is not None:
                record_model_inference_finished("mlp", inference_start)
        inference_ms = _elapsed_ms(inference_start)
    except HTTPException:
        raise
    except Exception as exc:
        _log_inference_error(request, "mlp", exc)
        raise HTTPException(status_code=500, detail="Prediction failed") from exc

    prediction = "positive" if probability >= PREDICTION_THRESHOLD else "negative"
    response_start = perf_counter()
    response = _build_prediction_response(
        request,
        model_key="mlp",
        model_name="PyTorch MLP with embeddings",
        model_family="pytorch_mlp",
        prediction=prediction,
        probability=probability,
        interpretation_notes=BASE_INTERPRETATION_NOTES + MLP_EXPLANATION_UNAVAILABLE_NOTES,
        feature_level_explanation_available=False,
        explanation=_build_unavailable_explanation(method=None, notes=MLP_EXPLANATION_UNAVAILABLE_NOTES),
    )
    response_ms = _elapsed_ms(response_start)
    _log_prediction_timing(
        request,
        model_name="mlp",
        preprocessing_ms=preprocessing_ms,
        inference_ms=inference_ms,
        response_ms=response_ms,
    )
    return response


@router.post("/predict/tree", response_model=TreePredictionResponse)
def predict_tree(request: Request, payload: TreePredictionRequest) -> TreePredictionResponse:
    _ensure_tree_resources_loaded()
    inference_start: float | None = None

    try:
        preprocessing_start = perf_counter()
        input_frame = _build_tree_input_frame(payload)
        transformed_frame = _build_tree_transformed_frame(input_frame)
        preprocessing_ms = _elapsed_ms(preprocessing_start)

        inference_start = record_model_inference_started("tree")
        try:
            probability = float(tree_model.predict_proba(transformed_frame)[0][1])
        except Exception:
            record_model_inference_error("tree")
            raise
        finally:
            if inference_start is not None:
                record_model_inference_finished("tree", inference_start)
        inference_ms = _elapsed_ms(inference_start)

        explanation_start = perf_counter()
        explanation = _build_tree_explanation(transformed_frame)
        explanation_ms = _elapsed_ms(explanation_start)
    except HTTPException:
        raise
    except Exception as exc:
        _log_inference_error(request, "tree", exc)
        raise HTTPException(status_code=500, detail="Prediction failed") from exc

    # The exported files do not define a label-name mapping, so keep a neutral mapping.
    prediction = "positive" if probability >= PREDICTION_THRESHOLD else "negative"

    response_start = perf_counter()
    response = _build_prediction_response(
        request,
        model_key="tree",
        model_name="XGBoost",
        model_family="xgboost",
        prediction=prediction,
        probability=probability,
        interpretation_notes=BASE_INTERPRETATION_NOTES + explanation.notes,
        feature_level_explanation_available=explanation.available,
        explanation=explanation,
    )
    response_ms = _elapsed_ms(response_start)
    _log_prediction_timing(
        request,
        model_name="tree",
        preprocessing_ms=preprocessing_ms,
        inference_ms=inference_ms,
        explanation_ms=explanation_ms,
        response_ms=response_ms,
    )
    return response


def _ensure_tree_resources_loaded() -> None:
    if tree_feature_schema is None or tree_preprocessor is None or tree_model is None:
        raise HTTPException(status_code=503, detail="Tree prediction resources are not loaded.")


def _ensure_mlp_resources_loaded() -> None:
    if (
        tree_feature_schema is None
        or mlp_preprocessor is None
        or mlp_category_maps is None
        or mlp_checkpoint is None
        or mlp_model is None
        or mlp_device is None
    ):
        raise HTTPException(status_code=503, detail="MLP prediction resources are not loaded.")


def _build_tree_input_frame(payload: TreePredictionRequest) -> pd.DataFrame:
    feature_schema = _require_tree_feature_schema()
    feature_columns = feature_schema["feature_columns"]
    payload_dict = payload.model_dump()
    missing_columns = [column for column in feature_columns if column not in payload_dict]
    if missing_columns:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing_columns}")

    ordered_row = {column: payload_dict[column] for column in feature_columns}
    return pd.DataFrame([ordered_row], columns=feature_columns)


def _build_mlp_tensors(input_frame: pd.DataFrame) -> tuple[torch.Tensor, torch.Tensor]:
    preprocessor = _require_mlp_preprocessor()
    category_maps = _require_mlp_category_maps()
    feature_schema = _require_tree_feature_schema()
    device = _require_mlp_device()

    categorical_features = feature_schema["categorical_features"]
    numeric_features = feature_schema["numeric_features"]

    categorical_arrays = []
    for feature in categorical_features:
        mapping = category_maps[feature]
        values = input_frame[feature].fillna("missing").astype(str)
        encoded = values.map(lambda value: mapping.get(value, 0)).astype("int64").to_numpy()
        categorical_arrays.append(encoded)

    if categorical_arrays:
        categorical_matrix = pd.DataFrame({feature: values for feature, values in zip(categorical_features, categorical_arrays)}).to_numpy(dtype="int64")
    else:
        categorical_matrix = pd.DataFrame(index=input_frame.index).to_numpy(dtype="int64")

    numeric_imputer = preprocessor["numeric_imputer"]
    numeric_scaler = preprocessor["numeric_scaler"]
    numeric_matrix = numeric_imputer.transform(input_frame[numeric_features])
    numeric_matrix = numeric_scaler.transform(numeric_matrix)

    categorical_tensor = torch.tensor(categorical_matrix, dtype=torch.long, device=device)
    numeric_tensor = torch.tensor(numeric_matrix, dtype=torch.float32, device=device)
    return categorical_tensor, numeric_tensor
