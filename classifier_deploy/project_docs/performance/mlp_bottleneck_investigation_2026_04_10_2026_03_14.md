# MLP Bottleneck Investigation 2026-04-10

This note records the first lightweight bottleneck investigation for `assignments/assignment_2/classifier_deploy`.

The goal was diagnosis only: identify why the MLP prediction path becomes the primary hotspot under concurrent load without changing the API contract.

## What Was Instrumented

Instrumentation was added only in `app/predict.py`.

For each prediction request, the backend now logs structured timing for:

- preprocessing
- model inference
- explanation time for tree requests
- response assembly
- handler-total time as the sum of those measured components

The log line format is:

```text
Prediction timing: ... model=<model> preprocessing_ms=<...> inference_ms=<...> explanation_ms=<...> response_ms=<...> handler_total_ms=<...>
```

This keeps the request and response contract unchanged. No schema or endpoint behavior was modified.

## Why It Was Instrumented

Workstream 1 showed that:

- correctness remained stable
- MLP became the slowest path under stress
- health also slowed down under stress

That suggested two competing possibilities:

- the MLP path is intrinsically heavier
- shared runtime contention is inflating multiple paths together

The added timing logs let us separate preprocessing from inference and compare tree against MLP directly under the existing expected and stress profiles.

## What Else Was Captured

Lightweight runtime resource visibility was captured outside the container using sampled `docker stats` during each run.

Captured signals:

- container CPU percent
- container memory percent
- memory usage in MiB
- PID count

This is intentionally lightweight. It is not a full observability system.

## Evidence Files

Expected-load investigation evidence:

- `project_docs/performance/mlp_timing_expected_2026_04_10.log`
- `project_docs/performance/mlp_expected_docker_stats_2026_04_10.log`
- `project_docs/performance/mlp_expected_locust_output_2026_04_10.log`

Stress-load investigation evidence:

- `project_docs/performance/mlp_timing_stress_2026_04_10.log`
- `project_docs/performance/mlp_stress_docker_stats_2026_04_10.log`
- `project_docs/performance/mlp_stress_locust_output_2026_04_10.log`

## Timing Findings

### Expected Load

Measured handler timing from the instrumented logs:

| Model | Samples | Preprocessing Avg ms | Inference Avg ms | Explanation Avg ms | Handler Avg ms | Handler p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| `mlp` | 467 | 9.74 | 1.57 | n/a | 11.42 | 24.69 |
| `tree` | 453 | 9.11 | 5.02 | 7.16 | 21.36 | 37.74 |

Interpretation:

- At expected load, MLP handler time is mostly preprocessing.
- MLP inference itself is small on average at this load.
- Tree is slower inside the handler because it carries both model inference and SHAP explanation work.

### Stress Load

Measured handler timing from the instrumented logs:

| Model | Samples | Preprocessing Avg ms | Inference Avg ms | Explanation Avg ms | Handler Avg ms | Handler p95 ms |
|---|---:|---:|---:|---:|---:|---:|
| `mlp` | 2048 | 38.77 | 202.54 | n/a | 241.45 | 417.12 |
| `tree` | 2095 | 34.79 | 28.20 | 37.08 | 100.15 | 214.67 |

Interpretation:

- Under stress, MLP inference becomes the dominant internal cost by a wide margin.
- MLP preprocessing also increases materially, but inference is the main driver.
- Tree also slows down under stress, and both preprocessing and explanation inflate, but tree remains much cheaper than MLP inside the handler.

## Answers To The Main Questions

### 1. Is the MLP bottleneck primarily inside model inference time?

Supported by evidence: yes, under stress.

At expected load, MLP inference averaged only `1.57 ms`, so it was not the dominant cost there.

At stress load, MLP inference averaged `202.54 ms`, versus `38.77 ms` for preprocessing. That makes inference the dominant internal component of the MLP path under concurrency.

### 2. Is preprocessing time a significant contributor?

Supported by evidence: yes, but it is not the main MLP bottleneck once the system is stressed.

MLP preprocessing rose from `9.74 ms` expected to `38.77 ms` stress. Tree preprocessing also rose from `9.11 ms` to `34.79 ms`.

So preprocessing does contribute and inflates under load for both paths, but it does not explain why MLP overtakes tree under stress. The main differentiator is MLP inference time.

### 3. Is the slowdown mostly shared runtime contention inside the single API process/container?

Supported by evidence: yes, but not proven as the only cause.

Evidence supporting shared contention:

- health slowed from single-digit milliseconds at expected load to `100 ms` average under stress
- tree handler time also grew significantly, not just MLP
- container CPU rose sharply under stress
- the gap between internal handler time and end-to-end request time widened under stress

Expected-load comparison:

- MLP handler avg `11.42 ms` vs Locust request avg `19 ms`
- tree handler avg `21.36 ms` vs Locust request avg `28-30 ms`

Stress comparison:

- MLP handler avg `241.45 ms` vs Locust request avg `364-367 ms`
- tree handler avg `100.15 ms` vs Locust request avg `229-230 ms`

That widening gap suggests additional waiting or contention outside the directly measured compute blocks, such as request scheduling, validation, or single-process runtime backlog.

This supports the shared-runtime-contention hypothesis, but it does not prove the precise mechanism by itself.

### 4. Does the MLP path consume meaningfully more per-request time than tree under the same load?

Supported by evidence: yes, clearly under stress.

Stress handler averages:

- MLP `241.45 ms`
- tree `100.15 ms`

Stress Locust averages:

- MLP `364-367 ms`
- tree `229-230 ms`

The MLP path remains the dominant hotspot after direct timing measurement.

### 5. Is there evidence that the current single-process Uvicorn runtime is part of the bottleneck?

Weak-to-moderate support from evidence: yes.

Evidence:

- health request latency rose sharply under stress
- both model paths slowed together
- container CPU increased strongly during stress
- end-to-end request latency exceeded internal handler timing by a larger margin under stress than under expected load

Sampled `docker stats` summary:

Expected load:

- CPU avg `8.04%`, max `38.40%`
- memory avg `282.2 MiB`, max `284.3 MiB`
- PIDs avg `44.84`, max `53`

Stress load:

- CPU avg `66.64%`, max `134.14%`
- memory avg `287.12 MiB`, max `288.6 MiB`
- PIDs avg `117.37`, max `119`

Memory stayed fairly flat, while CPU rose sharply. That points more toward compute and scheduling pressure than memory pressure.

This does not prove that a multi-worker deployment would solve the problem, but it does support the view that the current runtime setup is part of the bottleneck story.

## Bottom Line

The MLP bottleneck is real and measurable.

The strongest evidence from this phase is:

- under expected load, MLP is not intrinsically expensive inside the handler
- under stress, MLP inference time explodes and becomes the dominant internal cost
- preprocessing also inflates for both paths
- health and tree also slow under stress, which supports shared runtime contention
- memory does not appear to be the first bottleneck signal
- CPU pressure and concurrent inference cost are the stronger signals

## Recommended Next Optimization Target

The next optimization target should be the MLP inference path under concurrent load.

After that, the next diagnostic or optimization steps should be:

- test whether runtime configuration changes reduce the gap between handler timing and end-to-end request timing
- profile the MLP forward pass more directly if deeper tuning is needed
- measure the effect of SHAP/tree explanation separately only after the MLP path is addressed, since tree is not the current primary hotspot

## Limitations And Risks

- Handler timing starts after request-body validation, so Pydantic parsing and some framework overhead are not included in `handler_total_ms`.
- Logging itself adds small overhead, especially under stress.
- `docker stats` is coarse-grained and sampled every 2 seconds, so it is useful for trends, not fine-grained attribution.
- The current evidence supports shared runtime contention, but does not prove the exact root cause inside Uvicorn, Python scheduling, or PyTorch internals.
- No optimization was attempted in this phase, by design.
