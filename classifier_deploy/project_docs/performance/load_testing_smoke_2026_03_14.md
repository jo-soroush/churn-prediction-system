# Locust Smoke Test Baseline

This document describes the first Locust smoke test baseline for `assignments/assignment_2/classifier_deploy`.

The purpose is narrow: verify that the deployed versioned API contract can handle basic load-test traffic against the real smoke paths without changing application behavior. This is the first baseline only, not a full stress, soak, or capacity test suite.

## Endpoints Covered

- `GET /api/v1/health`
- `POST /api/v1/predict/tree`
- `POST /api/v1/predict/mlp`

Compare mode is represented as two sequential POST requests with the same payload because the project does not expose a dedicated compare endpoint.

The request body is loaded directly from `artifacts/sample_input.json` so the smoke test stays aligned with the artifact-backed contract already used by the backend tests.

## Run Locally

Start the API first from `assignments/assignment_2/classifier_deploy`:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Install Locust in the same environment if it is not already available:

```powershell
python -m pip install locust
```

Run the smoke suite from `assignments/assignment_2/classifier_deploy`:

```powershell
locust -f tests/performance/locustfile.py --host http://127.0.0.1:8000
```

Example headless smoke command:

```powershell
locust -f tests/performance/locustfile.py --host http://127.0.0.1:8000 --headless -u 1 -r 1 -t 1m
```

This baseline covers health, tree prediction, MLP prediction, and frontend-style compare orchestration. It does not yet include multiple payload profiles, threshold gates, stress profiles, or automated report export.

## Available Profiles

The default profile is `smoke`. It preserves the original low-intensity validation behavior with a `1-3` second user wait time.

An additional `expected` profile is also available for the first expected-load baseline. It keeps the same verified endpoints and artifact-backed payload but uses a shorter `0.2-1.0` second wait time so the suite can represent a modest steady request flow without changing the API contract.

Run the expected profile by setting `LOCUST_PROFILE=expected` before invoking Locust. Example:

```powershell
$env:LOCUST_PROFILE = "expected"
locust -f tests/performance/locustfile.py --host http://127.0.0.1:8000 --headless -u 5 -r 2 -t 2m
```

A `stress` profile is also available for controlled saturation checks. It keeps the same endpoints and payload but uses a `0.0-0.2` second wait time so users generate much denser traffic. This profile should always be run with explicit user, spawn-rate, and duration limits rather than as an open-ended test.

Example:

```powershell
$env:LOCUST_PROFILE = "stress"
locust -f tests/performance/locustfile.py --host http://127.0.0.1:8000 --headless -u 15 -r 5 -t 2m
```
