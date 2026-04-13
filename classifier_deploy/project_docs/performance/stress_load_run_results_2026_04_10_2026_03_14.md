# Stress-Load Run Results 2026-04-10

This document records the first controlled stress-load Locust baseline for the Dockerized runtime of `assignments/assignment_2/classifier_deploy`.

## Runtime Used

- Docker Compose runtime from `docker-compose.yml`
- API image built from `docker/Dockerfile.api`
- Frontend image built from `docker/Dockerfile.frontend`
- Locust executed from the project virtual environment against the Docker-published API port
- Locust version observed in execution output: `2.43.4`
- Locust profile: `stress`

## Stress Profile Definition

The first controlled stress profile used:

- Concurrent users: `15`
- Spawn rate: `5 users/second`
- Duration: `2 minutes`
- Locust user wait time for this profile: `0.0-0.2` seconds between tasks
- Explicit stop condition: fixed `2m` runtime with headless execution, followed by `docker compose down`

This profile was chosen because it is materially stronger than the expected-load baseline while still bounded. It increases concurrency by 3x, shortens think time to near-zero, and keeps a hard runtime limit so the run reveals degradation patterns without turning into an open-ended saturation test.

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

Stress execution:

```powershell
$env:LOCUST_PROFILE = "stress"
.venv\Scripts\locust.exe -f tests/performance/locustfile.py --host http://127.0.0.1:8000 --headless -u 15 -r 5 -t 2m
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

Final stress-load totals:

- Total requests: `5595`
- Failures: `0`
- Failure rate: `0.00%`
- Aggregated average response time: `231 ms`
- Aggregated minimum response time: `4 ms`
- Aggregated maximum response time: `808 ms`
- Aggregated median response time: `220 ms`
- Aggregated throughput: `46.95 req/s`

Per request name at shutdown:

| Request | Requests | Failures | Avg ms | Min ms | Max ms | Median ms |
|---|---:|---:|---:|---:|---:|---:|
| `GET /api/v1/health` | 1134 | 0 | 100 | 4 | 449 | 90 |
| `POST /api/v1/predict/mlp` | 1108 | 0 | 330 | 12 | 808 | 330 |
| `POST /api/v1/predict/mlp [compare-flow]` | 1083 | 0 | 320 | 15 | 788 | 320 |
| `POST /api/v1/predict/tree` | 1185 | 0 | 205 | 27 | 534 | 200 |
| `POST /api/v1/predict/tree [compare-flow]` | 1085 | 0 | 205 | 25 | 575 | 190 |

Aggregated percentiles reported by Locust:

- p50: `220 ms`
- p66: `270 ms`
- p75: `310 ms`
- p80: `340 ms`
- p90: `400 ms`
- p95: `450 ms`
- p98: `530 ms`
- p99: `600 ms`
- p100: `810 ms`

## Comparison Vs Expected-Load Baseline

Expected-load reference from `expected_load_run_results_2026_04_10_2026_03_14.md`:

- Expected total requests: `1180`
- Stress total requests: `5595`
- Difference: stress drove substantially more total traffic

- Expected aggregated average latency: `19 ms`
- Stress aggregated average latency: `231 ms`
- Difference: stress increased the average latency by `212 ms`

- Expected aggregated median latency: `17 ms`
- Stress aggregated median latency: `220 ms`
- Difference: stress increased the median latency by `203 ms`

- Expected aggregated p95: `39 ms`
- Stress aggregated p95: `450 ms`
- Difference: stress increased p95 by `411 ms`

- Expected aggregated p99: `67 ms`
- Stress aggregated p99: `600 ms`
- Difference: stress increased p99 by `533 ms`

- Expected throughput: `9.94 req/s`
- Stress throughput: `46.95 req/s`
- Difference: stress increased observed throughput by roughly `4.7x`

- Expected failures: `0`
- Stress failures: `0`
- New failures under stress: none

## Conclusion

The stress run passed in the narrow correctness sense: no request failures occurred, health remained available, and the API contract held under the stronger load.

The degradation was graceful rather than catastrophic, but it was clearly significant. Latency increased sharply across all paths, with MLP endpoints degrading the most. No timeout or route-failure threshold was reached in this bounded run, but saturation signals were visible in median, p95, and p99 latency.

## Issues Discovered

No backend contract, payload, route, artifact-loading, or Docker startup defect was discovered during the stress execution.

As in earlier Docker runs, PowerShell wrapped streamed `docker compose` and `locust.exe` output as `NativeCommandError` text while the underlying commands still succeeded. This was an output-capture artifact, not a runtime failure.

One runtime warning appeared from gevent/libuv:

- `libuv only supports millisecond timer resolution; all times less will be set to 1 ms`

This warning matches the stress profile's near-zero wait time and did not prevent execution.

## Result

The first controlled stress baseline completed successfully and exposed clear latency-growth behavior without request failures.

Evidence files generated during the run:

- `project_docs/performance/stress_docker_compose_up_2026_04_10.log`
- `project_docs/performance/stress_docker_ps_2026_04_10.log`
- `project_docs/performance/stress_docker_api_logs_2026_04_10.log`
- `project_docs/performance/stress_docker_health_2026_04_10.json`
- `project_docs/performance/stress_docker_locust_output_2026_04_10.log`
- `project_docs/performance/stress_docker_compose_down_2026_04_10.log`
