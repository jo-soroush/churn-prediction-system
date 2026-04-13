import os
from time import perf_counter

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.multiprocess import MultiProcessCollector


HTTP_METRICS_ENDPOINTS = {
    "/health": "/health",
    "/api/v1/health": "/health",
    "/predict/mlp": "/predict/mlp",
    "/api/v1/predict/mlp": "/predict/mlp",
    "/predict/tree": "/predict/tree",
    "/api/v1/predict/tree": "/predict/tree",
}
UNMAPPED_ENDPOINT = "other"


api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests handled by the application.",
    labelnames=("method", "endpoint"),
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "End-to-end API request duration in seconds.",
    labelnames=("method", "endpoint"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

api_inprogress_requests = Gauge(
    "api_inprogress_requests",
    "Number of in-flight API requests currently being processed.",
    labelnames=("method", "endpoint"),
    multiprocess_mode="livesum",
)

api_response_status_total = Counter(
    "api_response_status_total",
    "Total number of API responses by status code.",
    labelnames=("method", "endpoint", "status_code"),
)

model_inference_requests_total = Counter(
    "model_inference_requests_total",
    "Total number of model inference requests.",
    labelnames=("model",),
)

model_inference_duration_seconds = Histogram(
    "model_inference_duration_seconds",
    "Model inference duration in seconds.",
    labelnames=("model",),
    buckets=(0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

model_inference_errors_total = Counter(
    "model_inference_errors_total",
    "Total number of model inference failures.",
    labelnames=("model",),
)


def normalize_endpoint(path: str) -> str:
    return HTTP_METRICS_ENDPOINTS.get(path, UNMAPPED_ENDPOINT)


def record_request_started(method: str, endpoint: str) -> None:
    api_inprogress_requests.labels(method=method, endpoint=endpoint).inc()


def record_request_finished(method: str, endpoint: str, status_code: int, started_at: float) -> None:
    duration_seconds = perf_counter() - started_at
    api_requests_total.labels(method=method, endpoint=endpoint).inc()
    api_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration_seconds)
    api_response_status_total.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    api_inprogress_requests.labels(method=method, endpoint=endpoint).dec()


def record_model_inference_started(model: str) -> float:
    model_inference_requests_total.labels(model=model).inc()
    return perf_counter()


def record_model_inference_finished(model: str, started_at: float) -> None:
    model_inference_duration_seconds.labels(model=model).observe(perf_counter() - started_at)


def record_model_inference_error(model: str) -> None:
    model_inference_errors_total.labels(model=model).inc()


def build_metrics_payload(*, multiprocess_enabled: bool, multiprocess_dir: str) -> tuple[bytes, str]:
    if multiprocess_enabled:
        registry = CollectorRegistry()
        if not multiprocess_dir:
            raise RuntimeError("Prometheus multiprocess metrics are enabled but no PROMETHEUS_MULTIPROC_DIR is configured.")
        if not os.path.isdir(multiprocess_dir):
            raise RuntimeError(
                f"Prometheus multiprocess metrics directory does not exist or is not a directory: {multiprocess_dir}"
            )
        MultiProcessCollector(registry)
    else:
        registry = REGISTRY

    return generate_latest(registry), CONTENT_TYPE_LATEST
