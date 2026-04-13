# Monitoring Closeout

## Scope Statement

This note closes Workstream 3 for the local Docker monitoring stack only. The implemented scope covers API metrics exposure, Prometheus scraping, Grafana provisioning, and basic Prometheus alert rule loading and evaluation. It does not include Alertmanager, notification routing, external deployment targets, or broader production operations work.

## Step 1–5 Summary

**Step 1: API metrics instrumentation**

The API was instrumented with Prometheus-compatible metrics for request counts, request duration, in-flight requests, response status totals, model inference request counts, model inference duration, and model inference errors. A `/metrics` endpoint was exposed from the FastAPI application for Prometheus scraping.

**Step 2: `/metrics` instrumentation cleanup**

Request instrumentation was adjusted so the `/metrics` endpoint no longer instruments itself. This prevented monitoring traffic from showing up as regular application traffic and removed `/metrics` from the in-flight request gauge behavior during scrapes.

**Step 3: Prometheus scrape integration**

Prometheus was added to the local Docker stack and configured to scrape the API service at `api:8000/metrics`. The scrape target was validated as reachable and the Prometheus query layer returned application metrics after real API traffic and at least one scrape interval.

**Step 4: Grafana dashboard integration**

Grafana was added to the local Docker stack and provisioned automatically through mounted configuration. A Prometheus datasource pointing to `http://prometheus:9090` was provisioned automatically, and an `API Overview` dashboard was provisioned automatically with panels based on currently exposed metrics.

**Step 5: Basic alert rules**

Prometheus alert rules were added and loaded successfully. The initial rule set covers API target availability, 5xx response detection, elevated p95 API latency, and model inference error detection. Validation confirmed rule loading and evaluation health. It did not include alert delivery.

## Current Monitoring Stack Inventory

- FastAPI `/metrics` endpoint exposed by the API service
- Prometheus in Docker scraping `api:8000/metrics`
- Grafana in Docker, provisioned automatically
- Provisioned Prometheus datasource in Grafana
- Provisioned `API Overview` dashboard in Grafana
- Prometheus alert rules for:
  - `ApiTargetDown`
  - `ApiHighErrorResponses`
  - `ApiHighP95Latency`
  - `ModelInferenceErrorsDetected`

## Validated Runtime Behavior

The following behaviors were validated during Workstream 3:

- Single-process `/metrics` worked correctly.
- Multi-process `/metrics` with `API_WORKERS=2` worked correctly.
- Metrics appeared after real API requests.
- `/metrics` no longer instrumented itself.
- Request metrics and request-duration histogram data were exposed correctly.
- Prometheus ran successfully in the Docker stack.
- The Prometheus scrape target for `api:8000/metrics` reported `UP`.
- Prometheus queries returned data after real API traffic and a scrape interval.
- Grafana ran successfully in the Docker stack.
- Grafana login was reachable.
- The Prometheus datasource was provisioned automatically.
- The datasource pointed to `http://prometheus:9090`.
- The `API Overview` dashboard was provisioned automatically and was discoverable.
- Prometheus loaded the `api-monitoring` alert rule group successfully.
- All four initial alert rules reported health `ok`.
- Inactive alert state was accepted during validation because this step only required successful loading and evaluation.

## Important Constraints

- The monitoring stack is wired for local Docker networking. Container-to-container connections use Docker service names such as `api` and `prometheus`, not `localhost`.
- Useful application metrics depend on real API traffic. Some counters, histogram series, and dashboard panels may remain empty until requests are made and scraped.
- The API metrics path is `/metrics`, and that endpoint is intentionally excluded from request instrumentation to avoid scrape traffic distorting application metrics.
- Multi-process metrics depend on Prometheus multiprocess mode and a valid `PROMETHEUS_MULTIPROC_DIR`.
- Prometheus is evaluating alert rules locally, but no alert delivery path exists yet.
- Grafana provisioning is file-based. Datasource and dashboard availability depend on the mounted provisioning files remaining in sync with the Compose service configuration.
- Local host ports currently in use for the monitoring stack include `9090` for Prometheus and `3000` for Grafana.

## Current Limitations

- No Alertmanager is configured.
- No email, Slack, webhook, or paging integration exists.
- Alert rules are loaded and evaluated only; they are not routed anywhere.
- The Grafana setup includes one baseline dashboard, not a broader dashboard suite.
- The monitoring setup is documented here for project closeout, but README-level user guidance has not been updated yet.
- Validation covered the local Docker stack, not deployment environments beyond that scope.
- The current monitoring stack should not be described as complete production observability. It is a validated local monitoring baseline.

## Future Monitoring Work

The following items remain reasonable future monitoring work and were not implemented in Workstream 3:

- Add Alertmanager for alert routing, grouping, silences, and notification delivery.
- Define notification channels and escalation paths.
- Expand Grafana dashboards for endpoint-level drilldowns, worker behavior, and model-specific operational views.
- Add recording rules if query cost or dashboard responsiveness becomes a concern.
- Add runbooks or operator-facing response guidance for each alert.
- Update README or deployment-facing documentation when the monitoring stack is ready for broader user guidance.
- Extend validation beyond local Docker to any future hosted or production-like environments.

## Closeout Statement

Workstream 3 is complete for the approved scope. A local Docker monitoring baseline now exists with validated API metrics exposure, Prometheus scraping, Grafana provisioning, and Prometheus alert rule loading and evaluation. Alert delivery, broader operational workflows, and production-facing monitoring maturity remain future work.
