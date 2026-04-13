from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Assignment 2 Telecom Churn API"
    database_url: str | None = None
    # Local-friendly default; Docker overrides this to 0.0.0.0 via compose/env.
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "info"
    metrics_enabled: bool = True
    metrics_multiprocess_enabled: bool = False
    prometheus_multiproc_dir: str = "/tmp/prometheus-multiproc"
    artifacts_dir: str = "artifacts"
    feature_schema_path: str = "artifacts/feature_schema.json"
    model_metadata_path: str = "artifacts/model_metadata.json"
    tree_preprocessor_path: str = "artifacts/tree_preprocessor.pkl"
    xgb_model_path: str = "artifacts/xgb_model.json"
    mlp_model_path: str = "artifacts/mlp_model.pt"
    mlp_preprocessor_path: str = "artifacts/mlp_preprocessor.pkl"
    category_maps_path: str = "artifacts/category_maps.json"
    mlp_torch_num_threads: int = 1
    mlp_torch_num_interop_threads: int = 1

    def resolve_project_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else PROJECT_DIR / path


settings = Settings()
