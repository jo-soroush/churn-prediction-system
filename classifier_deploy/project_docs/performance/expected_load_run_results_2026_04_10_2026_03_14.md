# Expected-Load Run Results 2026-04-10

This document records the first measured expected-load Locust baseline for the Dockerized runtime of `assignments/assignment_2/classifier_deploy`.

## Runtime Used

- Docker Compose runtime from `docker-compose.yml`
- API image built from `docker/Dockerfile.api`
- Frontend image built from `docker/Dockerfile.frontend`
- Locust executed from the project virtual environment against the Docker-published API port
- Locust version observed in execution output: `2.43.4`
- Locust profile: `expected`

## Load Profile Definition

The first expected-load profile used:

- Concurrent users: `5`
- Spawn rate: `2 users/second`
- Duration: `2 minutes`
- Locust user wait time for this profile: `0.2-1.0` seconds between tasks

This profile was chosen because it is clearly stronger than the smoke baseline while still staying modest for a first expected-load pass. It increases concurrency, shortens think time, and runs long enough to produce a stable first endpoint-level baseline without turning into a stress or capacity test.

## Commands Used

Docker startup:

```powershell
docker compose up --build -d
```

Container state:

```powershell
docker compose ps
```

API logs:

```powershell
docker compose logs api
```

Health verification:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health
```

Expected-load execution:

```powershell
$env:LOCUST_PROFILE = "expected"
.venv\Scripts\locust.exe -f tests/performance/locustfile.py --host http://127.0.0.1:8000 --headless -u 5 -r 2 -t 2m
Remove-Item Env:LOCUST_PROFILE
```

Docker shutdown:

```powershell
docker compose down
```

## Startup And Health

Docker startup succeeded. `docker compose ps` showed both services running and the API port published on `0.0.0.0:8000`.

The API container logs showed successful startup, successful artifact loading from `/app/artifacts`, and backend readiness `True`.

Health passed with HTTP 200 and returned:

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

## Endpoints Exercised

- `GET /api/v1/health`
- `POST /api/v1/predict/tree`
- `POST /api/v1/predict/mlp`
- `POST /api/v1/predict/tree [compare-flow]`
- `POST /api/v1/predict/mlp [compare-flow]`

Compare mode remained modeled as two sequential POST requests with the same payload, which matches the verified frontend-only orchestration contract.

## Measured Locust Summary

Final expected-load totals:

- Total requests: `1180`
- Failures: `0`
- Failure rate: `0.00%`
- Aggregated average response time: `19 ms`
- Aggregated minimum response time: `3 ms`
- Aggregated maximum response time: `267 ms`
- Aggregated median response time: `17 ms`
- Aggregated throughput: `9.94 req/s`

Per request name at shutdown:

| Request | Requests | Failures | Avg ms | Min ms | Max ms | Median ms |
|---|---:|---:|---:|---:|---:|---:|
| `GET /api/v1/health` | 246 | 0 | 7 | 3 | 30 | 6 |
| `POST /api/v1/predict/mlp` | 215 | 0 | 19 | 11 | 255 | 14 |
| `POST /api/v1/predict/mlp [compare-flow]` | 252 | 0 | 17 | 11 | 267 | 14 |
| `POST /api/v1/predict/tree` | 215 | 0 | 26 | 19 | 96 | 23 |
| `POST /api/v1/predict/tree [compare-flow]` | 252 | 0 | 27 | 19 | 155 | 23 |

Aggregated percentiles reported by Locust:

- p50: `17 ms`
- p66: `22 ms`
- p75: `23 ms`
- p80: `24 ms`
- p90: `32 ms`
- p95: `39 ms`
- p98: `51 ms`
- p99: `67 ms`
- p100: `270 ms`

## Comparison Vs Docker Smoke Baseline

Docker smoke baseline reference from `docker_smoke_run_results_2026_04_10_2026_03_14.md`:

- Smoke total requests: `38`
- Expected-load total requests: `1180`
- Difference: expected-load exercised materially more traffic and sustained a higher steady request rate

- Smoke aggregated average latency: `23 ms`
- Expected-load aggregated average latency: `19 ms`
- Difference: expected-load average was `4 ms` lower in this run

- Smoke aggregated median latency: `21 ms`
- Expected-load aggregated median latency: `17 ms`
- Difference: expected-load median was `4 ms` lower in this run

- Smoke aggregated p95: `76 ms`
- Expected-load aggregated p95: `39 ms`
- Difference: expected-load showed a lower p95 than the earlier Docker smoke run

- Smoke throughput: `0.65 req/s`
- Expected-load throughput: `9.94 req/s`
- Difference: expected-load increased observed throughput substantially

- Smoke failures: `0`
- Expected-load failures: `0`
- New failures under expected load: none

The container runtime did not show contract instability under this first expected-load profile. Tail outliers still appeared, especially on MLP compare-flow requests, but they did not cause request failures.

## Issues And Fixes

One minimal test-suite fix was required before the run:

- The new profile toggle introduced an indentation regression in `tests/performance/locustfile.py`.
- The exact failing point was Python import/parse time for the Locust file, classified as a Locust profile issue.
- The fix was minimal: restore the second compare-flow POST block to the `compare_flow()` method body.

No backend contract, payload, route, artifact-loading, or Docker runtime defect was discovered during the expected-load execution.

As in prior Docker runs, PowerShell wrapped streamed `docker compose` and `locust.exe` output as `NativeCommandError` text while the underlying commands still succeeded. This was an output-capture artifact, not a runtime failure.

## Result

The first expected-load Docker baseline passed.

Evidence files generated during the run:

- `project_docs/performance/expected_docker_compose_up_2026_04_10.log`
- `project_docs/performance/expected_docker_ps_2026_04_10.log`
- `project_docs/performance/expected_docker_api_logs_2026_04_10.log`
- `project_docs/performance/expected_docker_health_2026_04_10.json`
- `project_docs/performance/expected_docker_locust_output_2026_04_10.log`
- `project_docs/performance/expected_docker_compose_down_2026_04_10.log`
