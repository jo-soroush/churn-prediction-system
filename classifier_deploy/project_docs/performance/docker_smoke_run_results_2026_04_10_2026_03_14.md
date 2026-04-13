# Docker Smoke Run Results 2026-04-10

This document records the first measured Locust smoke baseline for the Dockerized runtime of `assignments/assignment_2/classifier_deploy`.

## Runtime Used

- Docker Compose runtime from `docker-compose.yml`
- API image built from `docker/Dockerfile.api`
- Frontend image built from `docker/Dockerfile.frontend`
- Locust executed from the project virtual environment against the Docker-published API port
- Locust version observed in execution output: `2.43.4`

## Docker Commands Used

Startup:

```powershell
docker compose up --build -d
```

Container state:

```powershell
docker compose ps
```

API log capture:

```powershell
docker compose logs api
```

Health verification:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health
```

Headless smoke run:

```powershell
.venv\Scripts\locust.exe -f tests/performance/locustfile.py --host http://127.0.0.1:8000 --headless -u 1 -r 1 -t 1m
```

Shutdown:

```powershell
docker compose down
```

## Container Startup Evidence

Container startup succeeded.

`docker compose ps` reported both services running and the API port published:

- `classifier_deploy-api-1` status `Up`, port `0.0.0.0:8000->8000/tcp`
- `classifier_deploy-frontend-1` status `Up`, port `0.0.0.0:8501->8501/tcp`

The API container logs showed:

- FastAPI startup began successfully
- all required artifacts were resolved under `/app/artifacts`
- tree and MLP resources loaded successfully
- backend inference readiness was `True`
- Uvicorn reached `http://0.0.0.0:8000`

## Health Verification

The Dockerized API health check passed with HTTP 200 and returned:

```json
{
  "status": "ok",
  "tree_model_loaded": true,
  "tree_preprocessor_loaded": true,
  "tree_feature_schema_loaded": true,
  "mlp_model_loaded": true,
  "mlp_preprocessor_loaded": true,
  "mlp_category_maps_loaded": true
}
```

Readiness-style fields remained `true` in Docker.

## Endpoints Exercised

- `GET /api/v1/health`
- `POST /api/v1/predict/tree`
- `POST /api/v1/predict/mlp`
- `POST /api/v1/predict/tree [compare-flow]`
- `POST /api/v1/predict/mlp [compare-flow]`

Compare mode was exercised as two sequential POST requests with the same artifact-backed payload, matching the confirmed project contract.

## Locust Summary

Final Docker Locust totals:

- Total requests: `38`
- Failures: `0`
- Failure rate: `0.00%`
- Aggregated average response time: `23 ms`
- Aggregated minimum response time: `4 ms`
- Aggregated maximum response time: `84 ms`
- Aggregated median response time: `21 ms`
- Aggregated throughput: `0.65 req/s`

Per request name at shutdown:

| Request | Requests | Failures | Avg ms | Min ms | Max ms | Median ms |
|---|---:|---:|---:|---:|---:|---:|
| `GET /api/v1/health` | 9 | 0 | 5 | 4 | 8 | 6 |
| `POST /api/v1/predict/mlp` | 6 | 0 | 23 | 14 | 29 | 25 |
| `POST /api/v1/predict/mlp [compare-flow]` | 7 | 0 | 28 | 14 | 73 | 22 |
| `POST /api/v1/predict/tree` | 9 | 0 | 29 | 17 | 84 | 22 |
| `POST /api/v1/predict/tree [compare-flow]` | 7 | 0 | 33 | 21 | 75 | 26 |

Aggregated percentiles reported by Locust:

- p50: `22 ms`
- p66: `26 ms`
- p75: `27 ms`
- p80: `30 ms`
- p90: `35 ms`
- p95: `76 ms`
- p98: `85 ms`
- p99: `85 ms`
- p100: `85 ms`

## Comparison Vs Local Smoke Baseline

Local baseline reference from `smoke_run_results_2026_04_10_2026_03_14.md`:

- Local aggregated average latency: `22 ms`
- Docker aggregated average latency: `23 ms`
- Difference: Docker was `1 ms` slower on the aggregated average in this run

- Local aggregated p95: `33 ms`
- Docker aggregated p95: `76 ms`
- Difference: Docker showed a materially higher tail latency in this first run

- Local failures: `0`
- Docker failures: `0`
- Failures appearing only in Docker: none

The container runtime did not change contract behavior or correctness. It did show slower tail latency than the local non-Docker run, especially on prediction requests that hit the higher response-time outliers.

## Issues Discovered

No backend contract defect was discovered during the Docker smoke run. The API container started successfully, health passed, and all smoke endpoints returned successful responses.

The command capture includes PowerShell `NativeCommandError` wrappers around streaming output from `docker compose` and `locust.exe`, but the actual process results were successful:

- `docker compose up --build -d` completed and both containers reached `Up`
- Locust shut down with `exit code 0`
- `docker compose down` completed and cleaned up the stack

This was a PowerShell output-wrapping artifact, not a Docker or API runtime failure.

## Result

The first Docker smoke baseline passed.

Evidence files generated during the run:

- `project_docs/performance/docker_compose_up_2026_04_10.log`
- `project_docs/performance/docker_ps_2026_04_10.log`
- `project_docs/performance/docker_api_logs_2026_04_10.log`
- `project_docs/performance/docker_health_2026_04_10.json`
- `project_docs/performance/docker_locust_smoke_output_2026_04_10.log`
- `project_docs/performance/docker_compose_down_2026_04_10.log`
