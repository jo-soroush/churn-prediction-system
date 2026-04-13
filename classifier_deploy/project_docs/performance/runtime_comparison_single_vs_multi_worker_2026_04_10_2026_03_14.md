# Runtime Comparison: Single Worker vs Multi Worker

This note compares the latest measured single-worker runtime against a controlled two-worker runtime for `assignments/assignment_2/classifier_deploy`.

The goal was narrow: keep the API contract and Locust profiles unchanged, switch only the serving process model, and measure whether multi-worker serving reduces the remaining stress-load degradation.

## Runtime Modes Compared

Baseline single-worker mode:

- Docker Compose API startup from [docker-compose.yml](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/docker-compose.yml)
- API container command from [Dockerfile.api](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/docker/Dockerfile.api)
- Effective startup: `uvicorn app.main:app --workers 1`

Experimental multi-worker mode:

- Same Docker Compose stack
- Same FastAPI app
- Same endpoints and schemas
- Same Locust profiles
- Only change: `API_WORKERS=2`, which starts `uvicorn app.main:app --workers 2`

Local startup remains the same app as well:

- baseline: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- experiment: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`

## Contract Status

The backend contract remained unchanged.

- No routes changed
- No request schema changed
- No response schema changed
- No endpoints were added
- Existing Locust profiles in [locustfile.py](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/tests/performance/locustfile.py) were reused as-is
- Existing MLP path optimizations were kept in place

## Measurement Basis

Single-worker baseline:

- Latest measured baseline note: [mlp_optimization_pass_1_2026_04_10.md](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/mlp_optimization_pass_1_2026_04_10.md)
- Timing logs: [opt1_mlp_timing_expected_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/opt1_mlp_timing_expected_2026_04_10.log), [opt1_mlp_timing_stress_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/opt1_mlp_timing_stress_2026_04_10.log)

Two-worker experiment:

- Expected-load health: [mw_expected_health_2026_04_10.json](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/mw_expected_health_2026_04_10.json)
- Expected-load Locust: [mw_expected_locust_output_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/mw_expected_locust_output_2026_04_10.log)
- Expected-load API logs: [mw_expected_api_logs_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/mw_expected_api_logs_2026_04_10.log)
- Stress-load health: [mw_stress_health_2026_04_10.json](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/mw_stress_health_2026_04_10.json)
- Stress-load Locust: [mw_stress_locust_output_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/mw_stress_locust_output_2026_04_10.log)
- Stress-load API logs: [mw_stress_api_logs_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/mw_stress_api_logs_2026_04_10.log)

## Health Results

Both two-worker runs returned HTTP 200 health responses with all readiness fields `true`.

Expected-load health:

- status `ok`
- all model/preprocessor/schema readiness flags `true`

Stress-load health:

- status `ok`
- all model/preprocessor/schema readiness flags `true`

## Expected-Load Comparison

| Metric | Single worker | Two workers | Change |
| --- | ---: | ---: | ---: |
| total requests | 1183 | 1160 | -23 |
| failures | 0 | 0 | unchanged |
| avg latency | 18 ms | 25 ms | +7 ms |
| median latency | 17 ms | 19 ms | +2 ms |
| p95 | 39 ms | 59 ms | +20 ms |
| p99 | 68 ms | 76 ms | +8 ms |
| throughput | 9.98 req/s | 9.74 req/s | -0.24 req/s |
| threshold result | pass | pass | unchanged |

Endpoint averages:

- `GET /api/v1/health`: `6 ms` -> `6 ms`
- `POST /api/v1/predict/mlp`: `17 ms` -> `17 ms`
- `POST /api/v1/predict/mlp [compare-flow]`: `17 ms` -> `57 ms`
- `POST /api/v1/predict/tree`: `23 ms` -> `23 ms`
- `POST /api/v1/predict/tree [compare-flow]`: `23 ms` -> `22 ms`

Expected-load interpretation:

- Correctness stayed stable with zero failures.
- Expected-load still passes the documented thresholds.
- Two-worker serving did not improve expected-load latency or throughput.
- The run introduced a visible regression on the MLP compare-flow path, even though the overall profile still passed.

## Stress-Load Comparison

| Metric | Single worker | Two workers | Change |
| --- | ---: | ---: | ---: |
| total requests | 5377 | 8439 | +3062 |
| failures | 0 | 0 | unchanged |
| avg latency | 246 ms | 126 ms | -120 ms |
| median latency | 240 ms | 110 ms | -130 ms |
| p95 | 470 ms | 290 ms | -180 ms |
| p99 | 570 ms | 380 ms | -190 ms |
| throughput | 45.11 req/s | 70.74 req/s | +25.63 req/s |
| threshold result | pass | pass | unchanged |

Endpoint averages:

- `GET /api/v1/health`: `116 ms` -> `47 ms`
- `POST /api/v1/predict/mlp`: `338 ms` -> `165 ms`
- `POST /api/v1/predict/mlp [compare-flow]`: `329 ms` -> `186 ms`
- `POST /api/v1/predict/tree`: `224 ms` -> `118 ms`
- `POST /api/v1/predict/tree [compare-flow]`: `227 ms` -> `117 ms`

Stress-load interpretation:

- Correctness stayed stable with zero failures.
- Stress degradation improved materially across every measured latency percentile.
- Throughput improved materially.
- Health latency improved materially, which supports the shared-runtime-contention hypothesis.

## Internal Timing Comparison

Measured from the structured `Prediction timing` logs.

Expected-load MLP handler timing:

| Metric | Single worker | Two workers | Change |
| --- | ---: | ---: | ---: |
| preprocessing avg | 8.48 ms | 8.60 ms | +0.12 ms |
| inference avg | 1.94 ms | 1.11 ms | -0.83 ms |
| handler total avg | 10.53 ms | 9.81 ms | -0.72 ms |
| handler total p95 | 23.95 ms | 17.72 ms | -6.23 ms |

Stress-load MLP handler timing:

| Metric | Single worker | Two workers | Change |
| --- | ---: | ---: | ---: |
| preprocessing avg | 33.82 ms | 28.93 ms | -4.89 ms |
| inference avg | 175.41 ms | 83.79 ms | -91.62 ms |
| handler total avg | 209.38 ms | 112.86 ms | -96.52 ms |
| handler total p95 | 371.01 ms | 252.01 ms | -119.00 ms |

Additional internal signal:

- Under stress, the MLP path still dominates internal handler cost.
- Two-worker stress timing still shows MLP above tree handler time: `112.86 ms` vs `67.14 ms`.
- So the MLP path still dominates, but much less severely than in single-worker mode.

## Handler-Time vs End-to-End Gap

This was one of the key questions from the previous phase.

Expected load:

- single-worker MLP direct end-to-end avg vs MLP handler avg: `17 ms` vs `10.53 ms`
- two-worker MLP direct end-to-end avg vs MLP handler avg: `17 ms` vs `9.81 ms`
- direct-path gap did not shrink meaningfully at expected load

Stress load:

- single-worker mean MLP end-to-end avg across the two MLP Locust names: about `333.5 ms`
- two-worker mean MLP end-to-end avg across the two MLP Locust names: about `175.5 ms`
- single-worker MLP handler avg: `209.38 ms`
- two-worker MLP handler avg: `112.86 ms`
- approximate handler-to-end-to-end gap shrank from about `124 ms` to about `63 ms`

Interpretation:

- Under stress, multi-worker serving materially reduced the extra runtime/framework/socket overhead on top of the handler itself.
- Under expected load, the system was already unsaturated, so that gap was not the limiting factor.

## Resource Tradeoff

The two-worker runtime increases resident memory noticeably because the model stack is loaded in more than one worker process.

- single-worker expected-load API memory average from the prior run: about `281.3 MiB`
- two-worker expected-load post-run API memory snapshot: about `570.4 MiB`
- single-worker stress-load API memory average from the prior run: about `287.45 MiB`
- two-worker stress-load post-run API memory snapshot: about `579.1 MiB`

This is consistent with duplicated in-process model state across workers.

## Honest Decision

Conclusion: multi-worker serving materially helps and should be kept.

Why this conclusion is justified:

- The experiment produced a large stress-load win without any contract change.
- Health slowdown under stress improved materially.
- The MLP path still dominates, but the shared-runtime contention signal weakened substantially.
- The gap between internal handler time and end-to-end time shrank materially under stress.

Important nuance:

- Two workers did not help expected-load performance.
- The expected-load MLP compare-flow path regressed and should be watched in repeat runs.
- Even with two workers, the MLP path remains the slowest prediction path under stress.

Recommended decision:

- Keep the `API_WORKERS` runtime toggle.
- Prefer `API_WORKERS=2` for this project’s current container runtime when stress resilience matters more than minimal memory use.
- Do not treat this as the final scalability answer; it is a measured runtime improvement, not a full architecture redesign.
