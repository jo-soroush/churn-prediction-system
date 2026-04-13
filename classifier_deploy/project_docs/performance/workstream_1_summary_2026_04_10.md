# Workstream 1 Summary

This note closes Workstream 1 for `assignments/assignment_2/classifier_deploy`.

## What Was Implemented

Workstream 1 established a versioned Locust performance suite backed by the real API contract and the real artifact-backed payload in `artifacts/sample_input.json`.

The suite now supports three distinct profiles:

- `smoke`
- `expected`
- `stress`

Across these profiles, the suite exercises:

- `GET /api/v1/health`
- `POST /api/v1/predict/tree`
- `POST /api/v1/predict/mlp`
- frontend-style compare flow modeled as two sequential prediction POSTs with the same payload

Workstream 1 also produced saved evidence logs and markdown reports for local smoke, Docker smoke, Docker expected-load, Docker stress-load, bottleneck analysis, and explicit performance acceptance thresholds.

## What Was Measured

Measured baselines now exist for:

- local smoke
- Docker smoke
- Docker expected-load
- Docker stress-load

Headline measured results:

- local smoke: avg `22 ms`, p95 `33 ms`, failures `0`
- Docker smoke: avg `23 ms`, p95 `76 ms`, failures `0`
- expected-load: avg `19 ms`, p95 `39 ms`, throughput `9.94 req/s`, failures `0`
- stress-load: avg `231 ms`, p95 `450 ms`, throughput `46.95 req/s`, failures `0`

## What Passed

The following passed cleanly:

- application startup on local runtime
- application startup on Docker runtime
- health availability and readiness-style checks
- contract correctness across all tested endpoints
- smoke validation
- expected-load validation
- controlled stress validation

Most importantly, correctness remained stable across all measured profiles. No route failures, payload mismatches, startup contract problems, or artifact-loading regressions were observed in the completed runs.

## What Degraded

Performance degraded substantially under the stress profile.

The degradation was not catastrophic, but it was clear:

- aggregated median latency rose from `17 ms` at expected load to `220 ms` at stress
- aggregated p95 rose from `39 ms` to `450 ms`
- aggregated p99 rose from `67 ms` to `600 ms`
- health latency also rose under stress, which suggests shared runtime contention

This means the service remained correct, but performance headroom under stronger concurrency is limited.

## First Bottleneck

The first visible bottleneck is the MLP inference path under concurrent load.

At expected load, the MLP path looked competitive or faster than the tree path. Under stress, that flipped:

- MLP direct avg `330 ms`
- MLP compare-flow avg `320 ms`
- tree direct avg `205 ms`
- tree compare-flow avg `205 ms`

The bottleneck analysis also suggests broader shared runtime contention inside the single API container, because even health requests slowed materially during the stress run.

## Completion Decision

Workstream 1 can now be considered complete.

Reason:

- real contract-based performance tests were implemented
- smoke, expected, and stress profiles were all executed
- measured evidence was saved
- bottleneck analysis was written
- explicit pass, warning, and fail acceptance thresholds were defined

This is enough to claim evidence-backed performance validation for the current project scope.

## Important Limitation

Completion of Workstream 1 does not mean the system is proven ready for unlimited scale.

The correct interpretation is:

- correctness remained stable
- the application degraded gracefully under the bounded stress run
- latency headroom under stronger concurrency is limited
- the current evidence supports a portfolio-defensible performance story, not a production-scale readiness claim

## Recommended Next Workstream

The recommended next workstream is performance optimization and runtime hardening focused on the bottleneck already identified.

Priority order:

- profile and optimize the MLP inference path under concurrency
- inspect whether the single-process Uvicorn container setup is the dominant shared bottleneck
- add lightweight runtime observability for CPU, memory, and per-endpoint timing during load
- rerun expected and stress profiles after optimization to confirm whether p95 and p99 improve materially

If you want a compact label for that next phase, the clean name is:

- Workstream 2: Performance Optimization and Runtime Hardening
