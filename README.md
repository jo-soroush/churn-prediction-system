# Telecom Customer Churn Prediction System

End-to-end machine learning system for predicting telecom customer churn, served through a FastAPI backend and a Streamlit frontend. The project packages model training outputs, inference APIs, authentication, containers, CI validation, registry publishing, and cloud deployment into a portfolio-ready ML product prototype.

## Live Demo

The active cloud deployment runs on AWS EC2.

- Frontend application: `http://13.53.132.103:8501`
- Backend health check: `http://13.53.132.103:8000/health`

The Streamlit frontend is the intended public entry point for the system. Backend prediction, metadata, and metrics endpoints remain protected and require `X-API-Key`.

## 1. Project Overview

Customer churn prediction helps retention teams identify accounts that are likely to cancel service before the cancellation happens. The business value is prioritization: a reviewer can enter a customer profile, receive a churn probability, compare two deployed model families, and use the result to guide follow-up decisions.

This repository demonstrates the full path from trained tabular models to a deployable application:

- A FastAPI service exposes prediction, metadata, health, and metrics endpoints.
- Two inference models are available behind the same input contract: XGBoost and a PyTorch MLP with embeddings.
- A Streamlit frontend provides single-model and comparison workflows for user interaction.
- API key authentication protects inference, metadata, and metrics routes.
- Docker Compose runs the API and frontend locally or on a single EC2 instance.
- GitHub Actions validates tests, containers, authenticated endpoint checks, and GHCR publishing.

High-level flow:

```text
User
  -> Streamlit frontend
  -> FastAPI backend
  -> Preprocessing + model inference
  -> Structured prediction response
```

## 2. Architecture

### Backend: FastAPI

The backend lives under `classifier_deploy/app/` and serves the production-style inference contract. It loads model artifacts at startup, validates request payloads, applies preprocessing, runs inference, returns structured responses, and exports Prometheus-compatible metrics.

The API supports both unversioned routes and `/api/v1/*` routes. The unversioned routes are retained for compatibility; `/api/v1/*` is the formal versioned contract.

### Frontend: Streamlit

The frontend lives under `classifier_deploy/frontend/`. It provides a form-based workflow for entering telecom customer attributes and calling the backend with `X-API-Key`. It supports:

- Tree model prediction
- MLP prediction
- Side-by-side model comparison
- Model metadata display
- Tree model contribution display when SHAP output is available

### Model Layer

The model layer uses exported artifacts from the training workflow:

- `xgb_model.json`
- `tree_preprocessor.pkl`
- `mlp_model.pt`
- `mlp_preprocessor.pkl`
- `category_maps.json`
- `feature_schema.json`
- `model_metadata.json`

Artifacts are mounted into the API container as read-only files in Docker Compose.

### Communication Flow

```text
Streamlit UI
  -> POST /predict/tree or /predict/mlp
  -> FastAPI validates X-API-Key
  -> FastAPI validates request schema
  -> Model-specific preprocessing
  -> XGBoost or PyTorch inference
  -> JSON response with probability, label, metadata, and explanation status
```

## 3. Models

### Tree Model: XGBoost

The XGBoost model is the deployed tree-based model. It uses the tree preprocessing pipeline and returns:

- Churn label derived from a probability threshold
- Churn probability
- Contract and schema metadata
- SHAP-based feature contribution details when the SHAP runtime is available

### Neural Model: PyTorch MLP with Embeddings

The neural endpoint serves a PyTorch multilayer perceptron designed for mixed tabular input. Categorical features are encoded through embeddings, numeric features are normalized through the MLP preprocessing path, and the output is converted to a churn probability.

### Explainability

Tree-model explainability is implemented with SHAP. The API returns the top feature contributions for the tree endpoint, including direction and contribution value.

The MLP endpoint does not expose feature-level explanations. Its response explicitly marks feature-level explanation as unavailable so consumers do not confuse a probability score with an interpretable feature attribution.

## 4. Security

The backend uses service-level API key authentication through the `X-API-Key` header.

Protected endpoints require a valid API key:

- `/predict/tree`
- `/predict/mlp`
- `/metadata`
- `/metrics`
- The corresponding `/api/v1/*` routes

Public endpoints:

- `/health`
- `/api/v1/health`

`/health` is public by design because it is used by container health checks, deployment platforms, and uptime checks. It reports service readiness without exposing prediction capability or customer-level data.

This project does not implement user accounts, roles, sessions, or OAuth. Authentication is service-level protection for API access.

## 5. API Endpoints

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | Runtime readiness and artifact load status |
| `POST` | `/predict/tree` | Protected | XGBoost churn prediction with SHAP explanation when available |
| `POST` | `/predict/mlp` | Protected | PyTorch MLP churn prediction |
| `GET` | `/metadata` | Protected | Deployment, schema, model, and runtime metadata |
| `GET` | `/metrics` | Protected | Prometheus-compatible API and model metrics |

Versioned equivalents are available under `/api/v1`, for example `/api/v1/predict/tree`.

Protected requests must include:

```http
X-API-Key: <your_api_key>
```

## 6. Deployment

### 6.1 Docker / Local

The Docker deployment files are in `classifier_deploy/`.

```bash
cd classifier_deploy
cp .env.example .env
docker compose up --build
```

Required environment variables:

- `API_KEY`: backend API key for protected routes
- `FRONTEND_API_KEY`: key used by the Streamlit frontend when calling the backend
- `FRONTEND_API_BASE_URL`: backend URL used by the frontend

For local Compose networking, the default `FRONTEND_API_BASE_URL=http://api:8000` is used inside the frontend container. The `.env.example` file documents the artifact paths and runtime settings.

Local services:

- Frontend: `http://localhost:8501`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics` with `X-API-Key`

The Compose file also includes Prometheus and Grafana configuration assets for local monitoring.

### 6.2 AWS EC2

AWS EC2 is the active cloud deployment. The deployment is designed for a single instance running Docker Compose from `classifier_deploy/`, using the same containerized API and frontend services validated by CI.

Active endpoints:

- Frontend application: `http://13.53.132.103:8501`
- Backend health check: `http://13.53.132.103:8000/health`

Minimal setup:

1. Provision an EC2 instance with Docker and Docker Compose.
2. Pull the published GHCR images or build from the repository on the instance.
3. Configure `.env` with `API_KEY`, `FRONTEND_API_KEY`, and service URLs.
4. Start the stack from `classifier_deploy/` with `docker compose up -d`.

Ports:

- API container: `8000`
- Streamlit frontend: `8501`

Security group requirements:

- Allow inbound access to `8501` for the frontend if it is intended to be public.
- Allow inbound access to `8000` only when the API should be reachable directly.
- Keep SSH restricted to trusted IPs.
- In a stricter setup, expose only the frontend and keep the API private to the instance or VPC.

## 7. CI/CD

GitHub Actions is defined in `.github/workflows/ci.yml`.

The pipeline includes:

- Python dependency installation
- Full backend test suite with `pytest`
- Streamlit frontend syntax validation
- API container build validation
- Frontend container build validation
- Runtime smoke checks against the built API image
- Authenticated checks for `/predict/tree`, `/predict/mlp`, and `/metrics`
- Public health check validation for `/health`
- GHCR publishing on `main`
- Image delivery for AWS EC2 Docker Compose deployment

Published images:

- `ghcr.io/<repo>/assignment2-api`
- `ghcr.io/<repo>/assignment2-frontend`

Tagging strategy:

- `main`: latest validated image from the main branch
- `sha-<short_sha>`: immutable commit-specific image tag

## 8. How to Run

### Local

```bash
cd classifier_deploy
cp .env.example .env
# Edit API_KEY and FRONTEND_API_KEY so both values match.
docker compose up --build
```

Open:

- `http://localhost:8501` for the Streamlit frontend
- `http://localhost:8000/docs` for API documentation

### EC2

```bash
cd classifier_deploy
cp .env.example .env
# Set API_KEY, FRONTEND_API_KEY, and public/private service URLs for the instance.
docker compose up -d
```

Then verify:

```bash
curl http://<ec2-host>:8000/health
```

## 9. Example Usage

Sample prediction request:

```bash
curl -X POST "http://localhost:8000/predict/tree" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "gender": "Female",
    "seniorcitizen": 0,
    "partner": "Yes",
    "dependents": "No",
    "tenure": 24,
    "phoneservice": "Yes",
    "multiplelines": "No",
    "internetservice": "Fiber optic",
    "onlinesecurity": "No",
    "onlinebackup": "Yes",
    "deviceprotection": "Yes",
    "techsupport": "No",
    "streamingtv": "Yes",
    "streamingmovies": "No",
    "contract": "One year",
    "paperlessbilling": "Yes",
    "paymentmethod": "Bank transfer (automatic)",
    "monthlycharges": 79.9,
    "totalcharges": 1917.6
  }'
```

Tree response shape:

```json
{
  "request": {
    "request_id": "bc52457d-43ae-405f-b4ab-98a487c37cdb",
    "timestamp_utc": "2026-04-15T10:48:40Z"
  },
  "contract": {
    "contract_version": "v2",
    "schema_version": "telco_churn_schema_v1"
  },
  "model": {
    "model_key": "tree",
    "model_name": "XGBoost",
    "model_family": "xgboost",
    "artifact_set": "active"
  },
  "prediction_result": {
    "label": "positive",
    "probability": 0.508867,
    "threshold": 0.5,
    "threshold_rule": "probability >= threshold => positive"
  },
  "interpretation_basis": {
    "label_source": "thresholded_probability",
    "feature_level_explanation_available": true,
    "notes": [
      "The returned label is derived from the model probability using the current threshold rule."
    ]
  },
  "explanation": {
    "available": true,
    "method": "shap_tree",
    "top_features": [
      {
        "feature": "contract",
        "display_name": "Contract",
        "shap_value": 0.535769,
        "direction": "increases_churn_score"
      }
    ]
  }
}
```

MLP request uses the same payload:

```bash
curl -X POST "http://localhost:8000/predict/mlp" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  --data @classifier_deploy/artifacts/sample_input.json
```

MLP response shape:

```json
{
  "model": {
    "model_key": "mlp",
    "model_name": "PyTorch MLP with embeddings",
    "model_family": "pytorch_mlp",
    "artifact_set": "active"
  },
  "prediction_result": {
    "label": "negative",
    "probability": 0.312451,
    "threshold": 0.5,
    "threshold_rule": "probability >= threshold => positive"
  },
  "interpretation_basis": {
    "label_source": "thresholded_probability",
    "feature_level_explanation_available": false
  },
  "explanation": {
    "available": false,
    "method": null,
    "top_features": [],
    "notes": [
      "Feature-level explanation is not available for the deployed MLP endpoint."
    ]
  }
}
```

The numeric probabilities shown above are example values. Runtime values depend on the active model artifacts.

## 10. Limitations

- MLP feature-level explainability is not implemented in the deployed API.
- The project uses service-level API key authentication, not user-level authentication.
- The Streamlit frontend is a prototype interface, not a full production retention console.
- There is no CRM integration, batch scoring workflow, or persistence layer.
- Secrets and deployment environment settings are managed outside the repository.
- The current deployment pattern is suitable for a portfolio system and small demos, not high-scale enterprise traffic.

## 11. Future Work

- Add rate limiting for protected API routes.
- Add user-level authentication and authorization.
- Add monitoring dashboards for model drift, data quality, latency, and error budgets.
- Add a scheduled model retraining and evaluation pipeline.
- Add batch prediction and export workflows.
- Add deployment promotion stages between development, staging, and production.

## Repository Structure

```text
.
|-- README.md
|-- tabular.ipynb
|-- classifier_deploy/
|   |-- app/
|   |-- artifacts/
|   |-- artifact_versions/
|   |-- docker/
|   |-- frontend/
|   |-- tests/
|   |-- docker-compose.yml
|   `-- README.md
|-- project_docs/
|   `-- screenshots/
`-- notes/
```

## Supporting Documentation

Detailed implementation and deployment notes are available in `classifier_deploy/README.md`.

Screenshots and project artifacts are available under `project_docs/`, including:

- Tree model prediction result
- Compare mode result
- Deployed API docs
- Final model metrics table
- SHAP summary plot
- GitHub Actions workflow history

## Tech Stack

- Backend: FastAPI
- Frontend: Streamlit
- Models: XGBoost, PyTorch MLP with embeddings
- Explainability: SHAP for the tree endpoint
- Data tooling: pandas, scikit-learn
- Monitoring: Prometheus, Grafana
- Testing: pytest
- Containers: Docker, Docker Compose
- CI/CD: GitHub Actions
- Registry: GitHub Container Registry
- Deployments: AWS EC2, Docker Compose
