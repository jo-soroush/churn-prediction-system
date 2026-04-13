import json
import os
from pathlib import Path

from locust import HttpUser, between, task


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_INPUT_PATH = PROJECT_ROOT / "artifacts" / "sample_input.json"
ACTIVE_PROFILE = os.getenv("LOCUST_PROFILE", "smoke").strip().lower()


def load_sample_payload() -> dict[str, object]:
    # Load the request body from the shipped artifact so the smoke test stays aligned with the real contract.
    with SAMPLE_INPUT_PATH.open("r", encoding="utf-8-sig") as file_handle:
        payload = json.load(file_handle)

    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"Sample payload at {SAMPLE_INPUT_PATH} must be a non-empty JSON object.")
    return payload


class BaseClassifierDeployUser(HttpUser):
    abstract = True
    sample_payload = load_sample_payload()

    def _assert_success(self, response, *, expect_json_body: bool) -> None:
        if response.status_code != 200:
            response.failure(f"Expected HTTP 200 but received {response.status_code}.")
            return

        if not expect_json_body:
            response.success()
            return

        try:
            payload = response.json()
        except ValueError:
            response.failure("Expected a JSON response body.")
            return

        if not isinstance(payload, dict) or not payload:
            response.failure("Expected a non-empty JSON object response body.")
            return

        response.success()

    @task
    def health_check(self) -> None:
        # Use the versioned route because /api/v1/* is the formal contract in the FastAPI app.
        with self.client.get("/api/v1/health", name="GET /api/v1/health", catch_response=True) as response:
            self._assert_success(response, expect_json_body=False)

    @task
    def predict_tree(self) -> None:
        with self.client.post(
            "/api/v1/predict/tree",
            json=self.sample_payload,
            name="POST /api/v1/predict/tree",
            catch_response=True,
        ) as response:
            self._assert_success(response, expect_json_body=True)

    @task
    def predict_mlp(self) -> None:
        with self.client.post(
            "/api/v1/predict/mlp",
            json=self.sample_payload,
            name="POST /api/v1/predict/mlp",
            catch_response=True,
        ) as response:
            self._assert_success(response, expect_json_body=True)

    @task
    def compare_flow(self) -> None:
        # Compare mode is frontend orchestration, so the smoke flow issues the same payload to both model endpoints.
        with self.client.post(
            "/api/v1/predict/tree",
            json=self.sample_payload,
            name="POST /api/v1/predict/tree [compare-flow]",
            catch_response=True,
        ) as response:
            self._assert_success(response, expect_json_body=True)

        with self.client.post(
            "/api/v1/predict/mlp",
            json=self.sample_payload,
            name="POST /api/v1/predict/mlp [compare-flow]",
            catch_response=True,
        ) as response:
            self._assert_success(response, expect_json_body=True)


class ClassifierDeploySmokeUser(BaseClassifierDeployUser):
    abstract = ACTIVE_PROFILE != "smoke"
    wait_time = between(1, 3)


class ClassifierDeployExpectedLoadUser(BaseClassifierDeployUser):
    abstract = ACTIVE_PROFILE != "expected"
    wait_time = between(0.2, 1.0)


class ClassifierDeployStressUser(BaseClassifierDeployUser):
    abstract = ACTIVE_PROFILE != "stress"
    wait_time = between(0.0, 0.2)
