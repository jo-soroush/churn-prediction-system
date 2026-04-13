## MLP optimization pass 1

This pass applied the smallest high-confidence changes supported by the Phase 1 timing evidence. The goal was to reduce MLP inference overhead under concurrency without changing the API contract.

### What changed

1. The MLP prediction path now uses `torch.inference_mode()` instead of `torch.no_grad()`.
2. MLP request tensors are now created directly on the already-loaded device instead of being created and then moved during the request.
3. The API startup now pins the PyTorch CPU runtime to `1` intra-op thread and `1` inter-op thread to reduce CPU oversubscription inside the single-process container runtime.

Code references:
- [config.py](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/app/config.py)
- [main.py](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/app/main.py)
- [predict.py](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/app/predict.py)

### Why these changes were chosen

Phase 1 showed that MLP inference became the dominant internal cost under stress, while memory pressure stayed flat and CPU contention rose sharply. These changes target avoidable per-request PyTorch overhead and reduce thread contention without redesigning deployment.

### Contract impact

The backend contract did not change.

- No routes changed
- No request schema changed
- No response schema changed
- Existing Locust profiles remained intact

### Measurement setup

The same timing instrumentation from Phase 1 was kept in place. The optimized build was rerun against the existing Docker expected-load and stress-load profiles.

Evidence files:
- [opt1_mlp_timing_expected_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/opt1_mlp_timing_expected_2026_04_10.log)
- [opt1_mlp_timing_stress_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/opt1_mlp_timing_stress_2026_04_10.log)
- [opt1_expected_locust_output_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/opt1_expected_locust_output_2026_04_10.log)
- [opt1_stress_locust_output_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/opt1_stress_locust_output_2026_04_10.log)
- [opt1_expected_docker_stats_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/opt1_expected_docker_stats_2026_04_10.log)
- [opt1_stress_docker_stats_2026_04_10.log](/D:/ml_course_classroom/ml-1-course-jo-soroush/assignments/assignment_2/classifier_deploy/project_docs/performance/opt1_stress_docker_stats_2026_04_10.log)

### MLP timing before vs after

Expected load:

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| preprocessing avg | 9.74 ms | 8.48 ms | -1.26 ms |
| inference avg | 1.57 ms | 1.94 ms | +0.37 ms |
| handler total avg | 11.42 ms | 10.53 ms | -0.89 ms |
| handler total p95 | 24.69 ms | 23.97 ms | -0.72 ms |

Stress load:

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| preprocessing avg | 38.77 ms | 33.82 ms | -4.95 ms |
| inference avg | 202.54 ms | 175.41 ms | -27.13 ms |
| handler total avg | 241.45 ms | 209.38 ms | -32.07 ms |
| handler total p95 | 417.12 ms | 371.14 ms | -45.98 ms |

Interpretation:

- The MLP path improved modestly under expected load.
- The MLP path improved materially under stress.
- The biggest internal gain came from MLP inference time under stress.

### Expected-load end-to-end comparison

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| total requests | 1180 | 1183 | +3 |
| failures | 0 | 0 | unchanged |
| avg latency | 19 ms | 18 ms | -1 ms |
| median latency | 17 ms | 17 ms | unchanged |
| p95 | 39 ms | 39 ms | unchanged |
| p99 | 67 ms | 68 ms | +1 ms |
| throughput | 9.94 req/s | 9.98 req/s | +0.04 req/s |

Endpoint averages:

- `GET /api/v1/health`: 7 ms -> 6 ms
- `POST /api/v1/predict/mlp`: 19 ms -> 17 ms
- `POST /api/v1/predict/mlp [compare-flow]`: 17 ms -> 17 ms
- `POST /api/v1/predict/tree`: 26 ms -> 23 ms
- `POST /api/v1/predict/tree [compare-flow]`: 27 ms -> 23 ms

Expected-load conclusion:

- Correctness remained stable.
- The optimized build still passes the expected-load baseline.
- The end-to-end improvement is real but small, which is consistent with the fact that the system was not yet saturated at expected load.

### Stress-load end-to-end comparison

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| total requests | 5595 | 5377 | -218 |
| failures | 0 | 0 | unchanged |
| avg latency | 231 ms | 246 ms | +15 ms |
| median latency | 220 ms | 240 ms | +20 ms |
| p95 | 450 ms | 470 ms | +20 ms |
| p99 | 600 ms | 570 ms | -30 ms |
| throughput | 46.95 req/s | 45.11 req/s | -1.84 req/s |

Endpoint averages:

- `GET /api/v1/health`: 100 ms -> 116 ms
- `POST /api/v1/predict/mlp`: 330 ms -> 338 ms
- `POST /api/v1/predict/mlp [compare-flow]`: 320 ms -> 329 ms
- `POST /api/v1/predict/tree`: 205 ms -> 224 ms
- `POST /api/v1/predict/tree [compare-flow]`: 205 ms -> 227 ms

Stress-load conclusion:

- Correctness still remained stable with zero failures.
- The optimization reduced measured MLP handler cost, but that did not translate into a clear end-to-end stress improvement.
- The p99 tail improved slightly, but the average, median, and p95 did not.

### Runtime signals

Expected load Docker stats:

- CPU avg: 8.04% -> 6.83%
- CPU max: 38.40% -> 23.44%
- memory avg: 282.2 MiB -> 281.3 MiB

Stress load Docker stats:

- CPU avg: 66.64% -> 61.84%
- CPU max: 134.14% -> 125.31%
- memory avg: 287.12 MiB -> 287.45 MiB

Interpretation:

- CPU pressure fell somewhat after the optimization.
- Memory behavior stayed effectively unchanged.
- This supports the earlier conclusion that CPU contention matters more than memory pressure here.

### Honest interpretation

What improved:

- MLP internal handler time improved, especially stress-load inference time.
- CPU pressure dropped somewhat in both expected and stress runs.
- Correctness remained stable.

What did not improve enough:

- Stress end-to-end latency did not improve materially.
- Shared slowdown is still visible in tree requests and health checks.
- The single-process runtime still appears to be a meaningful part of the bottleneck picture.

Does the optimization move the bottleneck?

- It helps the MLP path itself.
- It does not remove the main system-level bottleneck under stress.
- The dominant remaining issue is still shared runtime contention in the current single-process container setup, with MLP compute remaining the most sensitive path inside that environment.

### Recommended next step

The next step should not be another micro-optimization in the request path first. The evidence now supports testing a runtime/process-model change, such as a controlled multi-worker serving experiment, because the path-level improvement did not materially shift the full stress profile.

### Limitations

- Timing logs measure handler internals, not the full FastAPI and socket lifecycle.
- Logging itself adds some overhead.
- The before and after runs are still single samples, so small differences at expected load should not be overinterpreted.
