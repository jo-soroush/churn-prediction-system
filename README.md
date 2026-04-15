# Telecom Customer Churn Risk Predictor

## A Production-Style AI Decision-Support System for Customer Retention

---

## Overview

**Telecom Customer Churn Risk Predictor** is a deployable AI-powered decision-support system designed to estimate the likelihood of customer churn in a telecom context.

The system transforms structured customer data into actionable churn-risk insights through a fully integrated pipeline that includes:

- machine learning models
- a backend inference API
- a user-facing interface
- explainability support
- monitoring and validation infrastructure
- CI/CD-backed container delivery

This project goes beyond a typical ML assignment and demonstrates how a churn prediction model can be packaged into a **usable, observable, and deployable AI product prototype**.

---

## Live Deployment

- **Frontend (User Interface):**  
  `https://assignment2-frontend-yugh.onrender.com`

- **Backend API (Health Check):**  
  `https://assignment2-api-3615.onrender.com/health`

- **API Documentation (Swagger):**  
  `https://assignment2-api-3615.onrender.com/docs`

---

## Key Features

### Prediction System
- Binary churn classification (positive / negative)
- Probability-based prediction output
- Configurable threshold logic
- Shared schema across multiple models

### Dual Model Architecture
- **XGBoost (Tree-Based Model)**
  - Primary production model
  - Supports feature-level explainability

- **PyTorch MLP (Neural Network)**
  - Embedding-based categorical handling
  - Alternative modeling strategy

- **RandomForest Baseline**
  - Retained for evaluation reference

### Explainability
- SHAP-based feature contribution (tree model)
- Top feature drivers returned per prediction
- Clear distinction between explainable and non-explainable models

### API Design
- FastAPI backend
- Versioned and unversioned endpoints
- Structured prediction contract
- Metadata and health endpoints

### Security
- API key authentication (`X-API-Key`)
- Protected prediction, metadata, and metrics routes
- Public health endpoints

### User Interface
- Streamlit-based frontend
- Single-model and compare-mode prediction
- Customer profile input form
- Model metadata and interpretation display

### Monitoring & Observability
- Prometheus metrics endpoint
- Grafana dashboard (local stack)
- Request/latency/error tracking
- Load testing via Locust

### Deployment & DevOps
- Dockerized services (API + frontend)
- Docker Compose for local orchestration
- GitHub Actions CI pipeline
- Container validation and testing
- GHCR (GitHub Container Registry) publishing
- Render cloud deployment (API + frontend)

---

## System Architecture

    User (Streamlit UI)
            ↓
    Frontend (Streamlit App)
            ↓
    Backend API (FastAPI)
            ↓
    Model Layer (XGBoost / MLP)
            ↓
    Artifacts (preprocessors, schema, metadata)

Additional layers:
- Monitoring: Prometheus + Grafana
- CI/CD: GitHub Actions + GHCR
- Deployment: Render (cloud-hosted services)

---

## Example API Request

    curl -X POST "https://assignment2-api-3615.onrender.com/predict/tree" \
      -H "Content-Type: application/json" \
      -H "X-API-Key: YOUR_API_KEY" \
      -d '{
        "gender": "Female",
        "seniorcitizen": 0,
        "partner": "Yes",
        "dependents": "No",
        "tenure": 12,
        "phoneservice": "Yes",
        "multiplelines": "No",
        "internetservice": "DSL",
        "onlinesecurity": "No",
        "onlinebackup": "Yes",
        "deviceprotection": "No",
        "techsupport": "No",
        "streamingtv": "No",
        "streamingmovies": "No",
        "contract": "Month-to-month",
        "paperlessbilling": "Yes",
        "paymentmethod": "Electronic check",
        "monthlycharges": 70.35,
        "totalcharges": 845.5
      }'

---

## Example API Response

    {
      "prediction_result": {
        "label": "positive",
        "probability": 0.508867,
        "threshold": 0.5
      },
      "model": {
        "model_name": "XGBoost"
      },
      "explanation": {
        "available": true,
        "method": "shap_tree",
        "top_features": [
          {"feature": "contract", "direction": "increases_churn_score"},
          {"feature": "monthlycharges", "direction": "decreases_churn_score"},
          {"feature": "internetservice", "direction": "decreases_churn_score"}
        ]
      }
    }

---

## Project Structure

    classifier_deploy/
    │
    ├── app/                    # FastAPI backend
    ├── frontend/               # Streamlit UI
    ├── artifacts/              # Active model artifacts
    ├── artifact_versions/      # Versioned artifacts
    ├── tests/                  # Test suite
    ├── docker/                 # Docker + monitoring config
    └── project_docs/           # Docs & screenshots

---

## Running Locally

### 1. Clone Repository

    git clone <repo-url>
    cd classifier_deploy

### 2. Set Environment Variables

    API_KEY=your_key
    FRONTEND_API_KEY=your_key

### 3. Run

    docker-compose up --build

### 4. Access

- Frontend: http://localhost:8501
- API: http://localhost:8000

---

## CI/CD Pipeline

- pytest backend tests
- frontend validation
- Docker build (Buildx)
- container smoke tests
- protected endpoint validation
- GHCR publishing

---

## Limitations

- no database persistence
- no user login system
- no CRM integration
- no batch processing
- no retraining pipeline
- no MLP explainability

---

## Tech Stack

- FastAPI
- Streamlit
- XGBoost
- PyTorch
- Docker
- Prometheus
- Grafana
- GitHub Actions
- GHCR
- Render

---

## Final Note

This project shows how a machine learning model can be turned into a **real, deployable AI product prototype** with:

- inference API
- user interface
- explainability
- monitoring
- CI/CD
- cloud deployment

It is designed as a **portfolio-grade system** bridging ML and real-world product engineering.
