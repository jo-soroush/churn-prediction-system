# Performance Acceptance Thresholds

This document defines practical performance acceptance thresholds for `assignments/assignment_2/classifier_deploy` based on the measured smoke, Docker smoke, expected-load, and stress-load evidence already captured in `project_docs/performance/`.

These thresholds are not enterprise SLOs. They are evidence-backed acceptance bands for this portfolio-grade ML deployment project so future test runs can be classified consistently as pass, warning, or fail.

## Principles

- Correctness is non-negotiable across all profiles. Wrong-status responses, schema failures, or broken health are failures even if latency is low.
- Smoke and expected-load are baseline validation profiles. They should remain fast and stable.
- Stress-load is a controlled degradation profile. Higher latency is acceptable there if correctness remains stable and degradation stays bounded.
- Thresholds are grounded in the measured runs:
  - local smoke: avg `22 ms`, p95 `33 ms`, p99 `72 ms`, failures `0`
  - Docker smoke: avg `23 ms`, p95 `76 ms`, p99 `85 ms`, failures `0`
  - expected-load: avg `19 ms`, p95 `39 ms`, p99 `67 ms`, failures `0`
  - stress-load: avg `231 ms`, p95 `450 ms`, p99 `600 ms`, failures `0`

## Shared Hard Failure Conditions

These are failure conditions for every profile:

- health check does not return HTTP 200
- readiness-style health fields are not all `true` at test start
- any endpoint returns non-200 responses for valid requests
- failure rate is greater than `1.0%`
- response body validation fails for the Locust contract checks
- artifact-loading or startup errors prevent the API from serving traffic

## Smoke Baseline Thresholds

Purpose: confirm the real deployed contract is alive, healthy, and fast at low load.

### Pass

- health available with all readiness fields `true`
- failure rate `0.0%`
- aggregated average latency `<= 50 ms`
- aggregated p95 `<= 100 ms`
- aggregated p99 `<= 150 ms`
- no correctness or contract regressions

### Warning

- health still available and correct
- failure rate remains `<= 1.0%`
- aggregated average latency `> 50 ms` and `<= 100 ms`
- or aggregated p95 `> 100 ms` and `<= 200 ms`
- or aggregated p99 `> 150 ms` and `<= 250 ms`
- degradation is visible but still well below stress-like behavior

### Fail

- any shared hard failure condition is met
- aggregated average latency `> 100 ms`
- or aggregated p95 `> 200 ms`
- or aggregated p99 `> 250 ms`
- or correctness is unstable even if latency is low

## Expected-Load Thresholds

Purpose: verify the application remains stable and low-latency under modest realistic concurrency.

### Pass

- health available with all readiness fields `true`
- failure rate `0.0%`
- aggregated average latency `<= 50 ms`
- aggregated p95 `<= 100 ms`
- aggregated p99 `<= 150 ms`
- throughput remains meaningfully above smoke-level throughput
- correctness remains stable across all exercised endpoints

### Warning

- health still available and correct
- failure rate remains `<= 1.0%`
- aggregated average latency `> 50 ms` and `<= 120 ms`
- or aggregated p95 `> 100 ms` and `<= 250 ms`
- or aggregated p99 `> 150 ms` and `<= 300 ms`
- throughput still scales upward, but tail latency suggests early headroom loss

### Fail

- any shared hard failure condition is met
- aggregated average latency `> 120 ms`
- or aggregated p95 `> 250 ms`
- or aggregated p99 `> 300 ms`
- or throughput does not improve meaningfully over smoke while latency worsens

## Stress-Load Thresholds

Purpose: measure whether the system degrades gracefully under a stronger, bounded load profile.

The stress profile is not expected to stay as fast as smoke or expected-load. The key acceptance question is whether correctness holds and whether degradation stays controlled rather than collapsing into failures or runaway latency.

### Pass

- health remains available during the run
- failure rate `<= 0.5%`
- correctness remains stable for valid requests
- aggregated average latency `<= 300 ms`
- aggregated p95 `<= 600 ms`
- aggregated p99 `<= 800 ms`
- degradation is visible but graceful: latency rises substantially while requests still complete successfully

### Warning

- health still available and correct
- failure rate remains `<= 1.0%`
- aggregated average latency `> 300 ms` and `<= 500 ms`
- or aggregated p95 `> 600 ms` and `<= 900 ms`
- or aggregated p99 `> 800 ms` and `<= 1200 ms`
- correctness holds, but saturation headroom is clearly narrow

### Fail

- any shared hard failure condition is met
- failure rate `> 1.0%`
- or health becomes unavailable during the run
- or aggregated average latency `> 500 ms`
- or aggregated p95 `> 900 ms`
- or aggregated p99 `> 1200 ms`
- or degradation is no longer graceful because timeouts, route failures, or persistent contract errors appear

## Current Result Against These Thresholds

Based on the measured evidence already in the repo:

- smoke baseline: `pass`
- expected-load baseline: `pass`
- stress-load baseline: `pass`

Important distinction:

- correctness remained stable across all measured profiles
- performance headroom under stress is limited
- this is enough to claim evidence-backed performance validation for Workstream 1
- this is not enough to claim unlimited scale readiness or production-grade capacity guarantees

## How To Use These Thresholds

Use these bands to classify future repeat runs of the same profiles.

- If smoke or expected-load falls into warning or fail, treat that as a meaningful regression.
- If stress falls into warning, treat that as a signal to investigate optimization priority rather than immediate contract breakage.
- If stress falls into fail, treat that as a genuine performance reliability issue under stronger concurrency.
