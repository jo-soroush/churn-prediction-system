# Bottleneck Analysis 2026-04-10

This note synthesizes the measured smoke, expected-load, and stress-load results for `assignments/assignment_2/classifier_deploy`.

## Source Baselines

- Docker smoke baseline: `docker_smoke_run_results_2026_04_10_2026_03_14.md`
- Expected-load baseline: `expected_load_run_results_2026_04_10_2026_03_14.md`
- Stress-load baseline: `stress_load_run_results_2026_04_10_2026_03_14.md`

## Main Findings

The tree endpoints are consistently slower than health, but the MLP endpoints become the slowest prediction paths once the system is pushed into stress territory.

At smoke level:

- health averaged `5 ms`
- tree averaged `29-33 ms`
- mlp averaged `23-28 ms`

At expected load:

- health averaged `7 ms`
- tree averaged `26-27 ms`
- mlp averaged `17-19 ms`

At stress load:

- health averaged `100 ms`
- tree averaged `205 ms`
- mlp averaged `320-330 ms`

The first clear bottleneck signal is therefore on the MLP prediction path under stronger concurrency. Tree inference also degrades, but not as sharply.

## Tail Latency Growth

Tail latency grows modestly from smoke to expected load, then expands sharply under stress.

Aggregated tail progression:

- smoke p95 `76 ms`, p99 `85 ms`
- expected p95 `39 ms`, p99 `67 ms`
- stress p95 `450 ms`, p99 `600 ms`

This is the strongest saturation signal in the current evidence set. The service stays correct, but latency headroom collapses under stress.

Endpoint-specific tails under stress show the same pattern:

- `POST /api/v1/predict/mlp`: p95 `540 ms`, p99 `640 ms`, max `810 ms`
- `POST /api/v1/predict/mlp [compare-flow]`: p95 `530 ms`, p99 `670 ms`, max `790 ms`
- `POST /api/v1/predict/tree`: p95 `360 ms`, p99 `450 ms`, max `530 ms`
- `POST /api/v1/predict/tree [compare-flow]`: p95 `350 ms`, p99 `440 ms`, max `580 ms`
- `GET /api/v1/health`: p95 `210 ms`, p99 `290 ms`, max `450 ms`

## Compare-Flow Overhead

Compare flow does introduce overhead, but the extra cost is modest relative to the base model path at the same load level.

Under stress:

- tree direct avg `205 ms`
- tree compare-flow avg `205 ms`
- mlp direct avg `330 ms`
- mlp compare-flow avg `320 ms`

The compare-flow endpoints are not materially worse than their single-endpoint counterparts in the measured averages. The real overhead is the frontend orchestration model itself: compare mode performs two prediction requests instead of one, so total work per user action doubles even when each individual request remains similar.

## Sensitivity By Model Path

The MLP path appears more sensitive than the tree path as load rises.

Evidence:

- expected-load avg: mlp `17-19 ms`, tree `26-27 ms`
- stress avg: mlp `320-330 ms`, tree `205 ms`

That reversal is important. At lower load, MLP looked competitive or faster than tree on average, but under stress it becomes the most latency-sensitive path in the system.

## Correctness Under Load

Correctness remained stable across all three baselines.

- smoke failures: `0`
- expected failures: `0`
- stress failures: `0`

No route failures, payload mismatches, artifact-load issues, or health failures appeared during the measured runs. The visible problem is latency degradation, not correctness loss.

## First Visible Saturation Signals

The first visible saturation signals are:

- aggregated median latency jumping from `17 ms` at expected load to `220 ms` at stress
- aggregated p95 jumping from `39 ms` to `450 ms`
- aggregated p99 jumping from `67 ms` to `600 ms`
- MLP endpoints clustering around `320-330 ms` average response time under stress
- health checks slowing to `100 ms` average under stress, which suggests shared runtime contention rather than an isolated prediction-only issue

That last point matters: even a lightweight health endpoint slowed down substantially under stress, which suggests the bottleneck is likely shared CPU scheduling, Python process concurrency, or model/runtime contention inside the single API container rather than only request-body parsing or one narrow route implementation.

## What To Optimize First

The first optimization target should be the MLP inference path under concurrent load, because it shows the highest average latency and the heaviest tail expansion.

After that, the next priorities should be:

- inspect whether the single-process Uvicorn deployment is the dominant shared bottleneck
- measure CPU saturation and per-request model execution time inside the container
- separate health traffic from model traffic in later tests so health degradation can be isolated more clearly
- evaluate whether compare-mode traffic should be weighted differently in future performance profiles because it doubles prediction calls

At this stage, there is not yet evidence of correctness failure or API instability. The main issue is latency headroom under stronger concurrency, with MLP inference as the first hotspot to investigate.
