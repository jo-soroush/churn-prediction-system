import json
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import joblib
import torch
import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from xgboost import XGBClassifier

from app.config import settings
from app.logging_config import configure_logging, get_logger
from app.metrics import build_metrics_payload, normalize_endpoint, record_request_finished, record_request_started
from app.schemas import (
    DeploymentMetadataResponse,
    ErrorBody,
    ErrorResponse,
    InputSchemaMetadata,
    ModelSelectionProtocol,
    RuntimeCompatibilityMetadata,
    TechnicalModelMetadata,
)
from app.predict import router as predict_router
import app.predict as predict_module


configure_logging(settings.log_level)
logger = get_logger("assignment2.api")
deployment_metadata: DeploymentMetadataResponse | None = None
backend_ready = False


def _clear_loaded_prediction_resources() -> None:
    global deployment_metadata

    deployment_metadata = None
    predict_module.tree_feature_schema = None
    predict_module.tree_preprocessor = None
    predict_module.tree_model = None
    predict_module.tree_shap_explainer = None
    predict_module.tree_shap_status_message = None
    predict_module.mlp_preprocessor = None
    predict_module.mlp_category_maps = None
    predict_module.mlp_checkpoint = None
    predict_module.mlp_model = None
    predict_module.mlp_device = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global deployment_metadata
    global backend_ready

    backend_ready = False

    logger.info("Application startup beginning")
    logger.info("API runtime configured: host=%s port=%s log_level=%s", settings.api_host, settings.api_port, settings.log_level)
    logger.info(
        "Metrics runtime configured: enabled=%s multiprocess_enabled=%s multiprocess_dir=%s",
        settings.metrics_enabled,
        settings.metrics_multiprocess_enabled,
        settings.prometheus_multiproc_dir,
    )
    if settings.metrics_enabled and settings.metrics_multiprocess_enabled:
        multiprocess_dir = Path(settings.prometheus_multiproc_dir)
        if not multiprocess_dir.is_dir():
            raise RuntimeError(
                f"Metrics multiprocess mode is enabled but PROMETHEUS_MULTIPROC_DIR is not ready: {multiprocess_dir}"
            )
    torch.set_num_threads(settings.mlp_torch_num_threads)
    torch.set_num_interop_threads(settings.mlp_torch_num_interop_threads)
    logger.info(
        "Configured PyTorch CPU runtime: num_threads=%s num_interop_threads=%s",
        torch.get_num_threads(),
        torch.get_num_interop_threads(),
    )

    feature_schema_path = settings.resolve_project_path(settings.feature_schema_path)
    model_metadata_path = settings.resolve_project_path(settings.model_metadata_path)
    tree_preprocessor_path = settings.resolve_project_path(settings.tree_preprocessor_path)
    xgb_model_path = settings.resolve_project_path(settings.xgb_model_path)
    mlp_model_path = settings.resolve_project_path(settings.mlp_model_path)
    mlp_preprocessor_path = settings.resolve_project_path(settings.mlp_preprocessor_path)
    category_maps_path = settings.resolve_project_path(settings.category_maps_path)

    required_paths = [
        feature_schema_path,
        model_metadata_path,
        tree_preprocessor_path,
        xgb_model_path,
        mlp_model_path,
        mlp_preprocessor_path,
        category_maps_path,
    ]
    logger.info(
        "Resolved active artifact files: feature_schema=%s model_metadata=%s tree_preprocessor=%s xgb_model=%s mlp_model=%s mlp_preprocessor=%s category_maps=%s",
        feature_schema_path,
        model_metadata_path,
        tree_preprocessor_path,
        xgb_model_path,
        mlp_model_path,
        mlp_preprocessor_path,
        category_maps_path,
    )

    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        logger.error(
            "Prediction backend is not ready because required artifacts are missing: %s. "
            "Application startup will continue; prediction endpoints will fail until artifacts are available and loaded.",
            missing_paths,
        )
        _clear_loaded_prediction_resources()
        yield
        logger.info("Application shutdown complete")
        return

    logger.info("Loading artifact: feature_schema path=%s", feature_schema_path)
    try:
        with feature_schema_path.open("r", encoding="utf-8") as file_handle:
            predict_module.tree_feature_schema = json.load(file_handle)
    except Exception:
        logger.exception("Failed to load artifact: feature_schema path=%s", feature_schema_path)
        raise
    logger.info(
        "Loaded artifact successfully: feature_schema schema_version=%s path=%s",
        predict_module.tree_feature_schema.get("schema_version", "unknown"),
        feature_schema_path,
    )

    logger.info("Loading artifact: model_metadata path=%s", model_metadata_path)
    try:
        with model_metadata_path.open("r", encoding="utf-8") as file_handle:
            raw_model_metadata = json.load(file_handle)
        deployment_metadata = DeploymentMetadataResponse(
            artifact_bundle_version=str(raw_model_metadata["artifact_bundle_version"]),
            schema_version=str(predict_module.tree_feature_schema.get("schema_version", "unknown")),
            feature_order_version=str(raw_model_metadata["feature_order_version"]),
            selection_protocol=ModelSelectionProtocol(**raw_model_metadata["selection_protocol"]),
            dependency_compatibility=RuntimeCompatibilityMetadata(**raw_model_metadata["dependency_compatibility"]),
            input_schema=InputSchemaMetadata(
                feature_columns=[str(value) for value in predict_module.tree_feature_schema["feature_columns"]],
                numeric_features=[str(value) for value in predict_module.tree_feature_schema["numeric_features"]],
                categorical_features=[str(value) for value in predict_module.tree_feature_schema["categorical_features"]],
            ),
            technical_models=TechnicalModelMetadata(
                tree_model_family=str(raw_model_metadata["main_tree_model"]["name"]),
                tree_model_parameters={
                    str(key): value for key, value in raw_model_metadata["main_tree_model"]["best_params"].items()
                },
                neural_model_family=str(raw_model_metadata["main_neural_model"]["name"]),
                neural_model_configuration={
                    str(key): value for key, value in raw_model_metadata["main_neural_model"]["best_config"].items()
                },
            ),
        )
    except Exception:
        logger.exception("Failed to load artifact: model_metadata path=%s", model_metadata_path)
        raise
    logger.info("Loaded artifact successfully: model_metadata path=%s", model_metadata_path)

    logger.info("Loading artifact: tree_preprocessor path=%s", tree_preprocessor_path)
    try:
        predict_module.tree_preprocessor = joblib.load(tree_preprocessor_path)
    except Exception:
        logger.exception("Failed to load artifact: tree_preprocessor path=%s", tree_preprocessor_path)
        raise
    logger.info("Loaded artifact successfully: tree_preprocessor path=%s", tree_preprocessor_path)

    logger.info("Loading artifact: xgb_model path=%s", xgb_model_path)
    try:
        predict_module.tree_model = XGBClassifier()
        predict_module.tree_model.load_model(xgb_model_path)
    except Exception:
        logger.exception("Failed to load artifact: xgb_model path=%s", xgb_model_path)
        raise
    logger.info("Loaded artifact successfully: xgb_model path=%s", xgb_model_path)
    predict_module.initialize_tree_shap_explainer()

    logger.info("Loading artifact: mlp_preprocessor path=%s", mlp_preprocessor_path)
    try:
        predict_module.mlp_preprocessor = joblib.load(mlp_preprocessor_path)
    except Exception:
        logger.exception("Failed to load artifact: mlp_preprocessor path=%s", mlp_preprocessor_path)
        raise
    logger.info("Loaded artifact successfully: mlp_preprocessor path=%s", mlp_preprocessor_path)

    logger.info("Loading artifact: category_maps path=%s", category_maps_path)
    try:
        with category_maps_path.open("r", encoding="utf-8") as file_handle:
            predict_module.mlp_category_maps = json.load(file_handle)
    except Exception:
        logger.exception("Failed to load artifact: category_maps path=%s", category_maps_path)
        raise
    logger.info("Loaded artifact successfully: category_maps path=%s", category_maps_path)

    logger.info("Loading artifact: mlp_model path=%s", mlp_model_path)
    try:
        predict_module.mlp_device = torch.device("cpu")
        predict_module.mlp_checkpoint = torch.load(mlp_model_path, map_location=predict_module.mlp_device)
        predict_module.mlp_model = predict_module.build_mlp_model_from_checkpoint(predict_module.mlp_checkpoint)
        predict_module.mlp_model.to(predict_module.mlp_device)
        predict_module.mlp_model.eval()
    except Exception:
        logger.exception("Failed to load artifact: mlp_model path=%s", mlp_model_path)
        raise
    logger.info("Loaded artifact successfully: mlp_model path=%s device=%s", mlp_model_path, predict_module.mlp_device)

    logger.info(
        "Startup artifact loading complete: tree_model=%s tree_preprocessor=%s tree_feature_schema=%s mlp_model=%s mlp_preprocessor=%s mlp_category_maps=%s",
        predict_module.tree_model is not None,
        predict_module.tree_preprocessor is not None,
        predict_module.tree_feature_schema is not None,
        predict_module.mlp_model is not None,
        predict_module.mlp_preprocessor is not None,
        predict_module.mlp_category_maps is not None,
    )

    tree_ready = (
        predict_module.tree_model is not None
        and predict_module.tree_preprocessor is not None
        and predict_module.tree_feature_schema is not None
    )
    mlp_ready = (
        predict_module.mlp_model is not None
        and predict_module.mlp_preprocessor is not None
        and predict_module.mlp_category_maps is not None
        and predict_module.tree_feature_schema is not None
    )
    backend_ready = tree_ready and mlp_ready

    logger.info("Tree inference pipeline ready: %s", tree_ready)
    logger.info("MLP inference pipeline ready: %s", mlp_ready)
    logger.info("Backend inference readiness: ready=%s", backend_ready)

    yield

    logger.info("Application shutdown complete")


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = perf_counter()
    request.state.request_start_time = start_time
    request.state.request_id = str(uuid4())
    should_instrument_request = request.url.path != "/metrics"
    metrics_method = request.method
    metrics_endpoint = normalize_endpoint(request.url.path)
    if should_instrument_request:
        record_request_started(metrics_method, metrics_endpoint)
    response = None
    try:
        response = await call_next(request)
        return response
    except Exception:
        duration_ms = (perf_counter() - start_time) * 1000
        logger.exception(
            "Request failed with unhandled exception: method=%s path=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise
    finally:
        status_code = response.status_code if response is not None else 500
        if should_instrument_request:
            record_request_finished(metrics_method, metrics_endpoint, status_code, start_time)
        if response is not None:
            duration_ms = (perf_counter() - start_time) * 1000
            logger.info(
                "Request completed: method=%s path=%s status=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )


# Keep the original unversioned paths for backward compatibility while /api/v1/* is the formal contract.
api_v1_router = APIRouter(prefix="/api/v1")
app.include_router(predict_router)
api_v1_router.include_router(predict_router)


def _build_health_response() -> dict[str, object]:
    return {
        "status": "ok",
        "tree_model_loaded": predict_module.tree_model is not None,
        "tree_preprocessor_loaded": predict_module.tree_preprocessor is not None,
        "tree_feature_schema_loaded": predict_module.tree_feature_schema is not None,
        "mlp_model_loaded": predict_module.mlp_model is not None,
        "mlp_preprocessor_loaded": predict_module.mlp_preprocessor is not None,
        "mlp_category_maps_loaded": predict_module.mlp_category_maps is not None,
    }


def _ensure_deployment_metadata_loaded() -> DeploymentMetadataResponse:
    if deployment_metadata is None:
        raise HTTPException(status_code=503, detail="Deployment metadata is not loaded.")
    return deployment_metadata


def _build_error_response(error_type: str, message: str, details: list[object] | dict[str, object] | None = None) -> dict[str, object]:
    return ErrorResponse(error=ErrorBody(type=error_type, message=message, details=details)).model_dump()


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    field_names = []
    for error in errors:
        loc = error.get("loc", [])
        if len(loc) >= 2 and loc[0] == "body":
            field_names.append(str(loc[1]))
    unique_fields = ",".join(dict.fromkeys(field_names)) if field_names else "unknown"

    duration_ms = None
    start_time = getattr(request.state, "request_start_time", None)
    if start_time is not None:
        duration_ms = (perf_counter() - start_time) * 1000

    if duration_ms is None:
        logger.warning(
            "Validation error: method=%s path=%s status=422 error_count=%s fields=%s",
            request.method,
            request.url.path,
            len(errors),
            unique_fields,
        )
    else:
        logger.warning(
            "Validation error: method=%s path=%s status=422 error_count=%s fields=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            len(errors),
            unique_fields,
            duration_ms,
        )

    return JSONResponse(
        status_code=422,
        content=_build_error_response(
            error_type="validation_error",
            message="Request validation failed",
            details=errors,
        ),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        error_type = "prediction_error"
        message = "Prediction failed"
    else:
        error_type = "http_error"
        message = "Request could not be processed"

    details = exc.detail if isinstance(exc.detail, (list, dict)) else [exc.detail]
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_response(
            error_type=error_type,
            message=message,
            details=details,
        ),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_build_error_response(
            error_type="internal_error",
            message="An internal server error occurred",
            details=None,
        ),
    )


@app.get("/health")
def health() -> dict[str, object]:
    return _build_health_response()


@api_v1_router.get("/health")
def health_v1() -> dict[str, object]:
    return _build_health_response()


@app.get("/metadata", response_model=DeploymentMetadataResponse)
def metadata() -> DeploymentMetadataResponse:
    return _ensure_deployment_metadata_loaded()


@api_v1_router.get("/metadata", response_model=DeploymentMetadataResponse)
def metadata_v1() -> DeploymentMetadataResponse:
    return _ensure_deployment_metadata_loaded()


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Not found")

    payload, content_type = build_metrics_payload(
        multiprocess_enabled=settings.metrics_multiprocess_enabled,
        multiprocess_dir=settings.prometheus_multiproc_dir,
    )
    return Response(content=payload, media_type=content_type)


app.include_router(api_v1_router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, log_level=settings.log_level)
