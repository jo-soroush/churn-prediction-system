import os

import pandas as pd
import requests
import streamlit as st

DEFAULT_API_BASE_URL = os.getenv("FRONTEND_API_BASE_URL", "http://127.0.0.1:8000")
FRONTEND_API_KEY = os.getenv("FRONTEND_API_KEY", "").strip()
METADATA_ENDPOINT_PATH = "/metadata"
MODEL_OPTIONS = {
    "Tree (XGBoost)": "/predict/tree",
    "MLP (PyTorch MLP with embeddings)": "/predict/mlp",
}
DEFAULT_FORM_VALUES = {
    "gender": "Female",
    "seniorcitizen": 0,
    "partner": "No",
    "dependents": "No",
    "tenure": 12.0,
    "phoneservice": "Yes",
    "multiplelines": "No",
    "internetservice": "DSL",
    "onlinesecurity": "No",
    "onlinebackup": "No",
    "deviceprotection": "No",
    "techsupport": "No",
    "streamingtv": "No",
    "streamingmovies": "No",
    "contract": "Month-to-month",
    "paperlessbilling": "Yes",
    "paymentmethod": "Electronic check",
    "monthlycharges": 65.3,
    "totalcharges": 780.2,
    "selected_model_label": "Tree (XGBoost)",
    "prediction_mode": "Single model",
}


def _initialize_form_state() -> None:
    for key, value in DEFAULT_FORM_VALUES.items():
        st.session_state.setdefault(key, value)


def _reset_form_state() -> None:
    for key, value in DEFAULT_FORM_VALUES.items():
        st.session_state[key] = value


def _get_nested_value(payload: dict[str, object], *path: str) -> object:
    current_value: object = payload
    for key in path:
        if not isinstance(current_value, dict):
            return None
        current_value = current_value.get(key)
    return current_value


def _normalize_prediction_response(result: dict[str, object]) -> dict[str, object]:
    prediction_probability = _get_nested_value(result, "prediction_result", "probability")
    prediction_label = _get_nested_value(result, "prediction_result", "label")
    model_name = _get_nested_value(result, "model", "model_name")

    return {
        "request_id": _get_nested_value(result, "request", "request_id"),
        "timestamp_utc": _get_nested_value(result, "request", "timestamp_utc"),
        "contract_version": _get_nested_value(result, "contract", "contract_version"),
        "schema_version": _get_nested_value(result, "contract", "schema_version"),
        "model_key": _get_nested_value(result, "model", "model_key"),
        "model_name": model_name,
        "model_family": _get_nested_value(result, "model", "model_family"),
        "artifact_set": _get_nested_value(result, "model", "artifact_set"),
        "prediction_label": prediction_label,
        "prediction_probability": prediction_probability,
        "prediction_threshold": _get_nested_value(result, "prediction_result", "threshold"),
        "prediction_threshold_rule": _get_nested_value(result, "prediction_result", "threshold_rule"),
        "label_source": _get_nested_value(result, "interpretation_basis", "label_source"),
        "feature_level_explanation_available": _get_nested_value(
            result, "interpretation_basis", "feature_level_explanation_available"
        ),
        "interpretation_notes": _get_nested_value(result, "interpretation_basis", "notes"),
        "explanation": _get_nested_value(result, "explanation"),
    }


def _format_display_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    if value is None:
        return "Unavailable"
    return str(value)


def _build_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"API returned {response.status_code} and the response body was not valid JSON."

    error_body = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error_body, dict):
        return f"API returned {response.status_code} without the expected structured error body."

    error_type = error_body.get("type", "unknown_error")
    error_message = error_body.get("message", "Request failed")
    details = error_body.get("details")

    detail_lines: list[str] = []
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict):
                location = item.get("loc")
                message = item.get("msg")
                location_text = ".".join(str(part) for part in location) if isinstance(location, list) else None
                if location_text and message:
                    detail_lines.append(f"{location_text}: {message}")
                elif message:
                    detail_lines.append(str(message))
                else:
                    detail_lines.append(str(item))
            else:
                detail_lines.append(str(item))
    elif isinstance(details, dict):
        for key, value in details.items():
            detail_lines.append(f"{key}: {value}")
    elif details is not None:
        detail_lines.append(str(details))

    if detail_lines:
        return f"{error_type}: {error_message} ({'; '.join(detail_lines)})"
    return f"{error_type}: {error_message}"


def _build_auth_headers() -> tuple[dict[str, str] | None, str | None]:
    if not FRONTEND_API_KEY:
        return None, "Frontend API key is not configured. Set FRONTEND_API_KEY before calling protected backend routes."

    return {"X-API-Key": FRONTEND_API_KEY}, None


def _render_result_field(label: str, value: object) -> None:
    st.caption(label)
    st.write(value)


def _run_prediction_request(
    api_base_url: str, endpoint_path: str, payload: dict[str, object]
) -> tuple[dict[str, object] | None, str | None]:
    headers, configuration_error = _build_auth_headers()
    if configuration_error is not None:
        return None, configuration_error

    try:
        response = requests.post(
            f"{api_base_url}{endpoint_path}",
            json=payload,
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as error:
        return None, f"Could not reach the API: {error}"

    if not response.ok:
        return None, _build_error_message(response)

    return response.json(), None


def _run_metadata_request(api_base_url: str) -> tuple[dict[str, object] | None, str | None]:
    headers, configuration_error = _build_auth_headers()
    if configuration_error is not None:
        return None, configuration_error

    try:
        response = requests.get(f"{api_base_url}{METADATA_ENDPOINT_PATH}", headers=headers, timeout=10)
    except requests.RequestException as error:
        return None, f"Could not reach the API: {error}"

    if not response.ok:
        return None, _build_error_message(response)

    payload = response.json()
    if not isinstance(payload, dict):
        return None, "API returned deployment metadata in an unexpected format."
    return payload, None


def _render_interpretation_basis(normalized_result: dict[str, object]) -> None:
    st.markdown("### Interpretation Basis")
    _render_result_field("Label Source", _format_display_value(normalized_result["label_source"]))
    _render_result_field(
        "Feature-Level Explanation Available",
        _format_display_value(normalized_result["feature_level_explanation_available"]),
    )

    notes = normalized_result["interpretation_notes"]
    if isinstance(notes, list) and notes:
        st.caption("Notes")
        for note in notes:
            st.write(f"- {note}")
    else:
        st.write("No interpretation notes were returned by the API.")


def _render_response_metadata(normalized_result: dict[str, object]) -> None:
    st.markdown("### Response Metadata")
    metadata_columns = st.columns(2, gap="medium")
    with metadata_columns[0]:
        _render_result_field("Request ID", _format_display_value(normalized_result["request_id"]))
        _render_result_field("Timestamp (UTC)", _format_display_value(normalized_result["timestamp_utc"]))
        _render_result_field("Contract Version", _format_display_value(normalized_result["contract_version"]))
        _render_result_field("Schema Version", _format_display_value(normalized_result["schema_version"]))
    with metadata_columns[1]:
        _render_result_field("Model Key", _format_display_value(normalized_result["model_key"]))
        _render_result_field("Model Name", _format_display_value(normalized_result["model_name"]))
        _render_result_field("Model Family", _format_display_value(normalized_result["model_family"]))
        _render_result_field("Artifact Set", _format_display_value(normalized_result["artifact_set"]))


def _render_named_values(fields: list[tuple[str, object]]) -> None:
    for label, value in fields:
        _render_result_field(label, _format_display_value(value))


def _format_technical_value(value: object) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return _format_display_value(value)


def _render_technical_mapping(label: str, values: object) -> None:
    st.caption(label)
    if isinstance(values, dict) and values:
        technical_rows = pd.DataFrame(
            [{"Field": key, "Value": _format_technical_value(value)} for key, value in values.items()]
        )
        st.table(technical_rows)
    else:
        st.write("Unavailable")


def _render_string_list(label: str, values: object) -> None:
    st.caption(label)
    if isinstance(values, list) and values:
        for item in values:
            st.write(f"- {item}")
    else:
        st.write("Unavailable")


def _render_model_deployment_metadata(metadata_payload: dict[str, object] | None, metadata_error: str | None) -> None:
    with st.expander("Model / Deployment Metadata", expanded=False):
        if metadata_payload is None:
            st.info(f"Deployment metadata is unavailable. {metadata_error}" if metadata_error else "Deployment metadata is unavailable.")
            return

        st.caption("Artifact-backed deployment metadata loaded from the shipped model bundle.")
        provenance_columns = st.columns(3, gap="medium")
        provenance_fields = [
            ("Artifact Bundle Version", metadata_payload.get("artifact_bundle_version")),
            ("Schema Version", metadata_payload.get("schema_version")),
            ("Feature Order Version", metadata_payload.get("feature_order_version")),
        ]
        for column, field in zip(provenance_columns, provenance_fields):
            with column:
                _render_named_values([field])

        selection_protocol = metadata_payload.get("selection_protocol")
        if isinstance(selection_protocol, dict):
            st.caption("Offline Model Selection Protocol")
            _render_named_values(
                [
                    ("Training Split", selection_protocol.get("training_split")),
                    ("Model Selection Split", selection_protocol.get("selection_split")),
                    ("Final Reporting Split", selection_protocol.get("final_reporting_split")),
                ]
            )

        dependency_compatibility = metadata_payload.get("dependency_compatibility")
        with st.expander("Validated Runtime Compatibility", expanded=False):
            if isinstance(dependency_compatibility, dict):
                compatibility_columns = st.columns(2, gap="medium")
                left_fields = [
                    ("Python Version", dependency_compatibility.get("python_version")),
                    ("PyTorch Version", dependency_compatibility.get("pytorch_version")),
                    ("XGBoost Version", dependency_compatibility.get("xgboost_version")),
                    ("scikit-learn Version", dependency_compatibility.get("scikit_learn_version")),
                ]
                right_fields = [
                    ("joblib Version", dependency_compatibility.get("joblib_version")),
                    ("pandas Version", dependency_compatibility.get("pandas_version")),
                    ("NumPy Version", dependency_compatibility.get("numpy_version")),
                ]
                with compatibility_columns[0]:
                    _render_named_values(left_fields)
                with compatibility_columns[1]:
                    _render_named_values(right_fields)
                _render_result_field("Compatibility Notes", dependency_compatibility.get("notes"))
            else:
                st.write("Unavailable")

        input_schema = metadata_payload.get("input_schema")
        with st.expander("Expected Input Features", expanded=False):
            if isinstance(input_schema, dict):
                _render_string_list("All Input Features", input_schema.get("feature_columns"))
                _render_string_list("Numeric Input Features", input_schema.get("numeric_features"))
                _render_string_list("Categorical Input Features", input_schema.get("categorical_features"))
            else:
                st.write("Unavailable")

        technical_models = metadata_payload.get("technical_models")
        with st.expander("Technical Model Configuration", expanded=False):
            if isinstance(technical_models, dict):
                technical_columns = st.columns(2, gap="medium")
                with technical_columns[0]:
                    _render_result_field("Tree Model Family", technical_models.get("tree_model_family"))
                    _render_technical_mapping(
                        "Selected Tree Model Parameters",
                        technical_models.get("tree_model_parameters"),
                    )
                with technical_columns[1]:
                    _render_result_field("Neural Model Family", technical_models.get("neural_model_family"))
                    _render_technical_mapping(
                        "Selected Neural Model Configuration",
                        technical_models.get("neural_model_configuration"),
                    )
            else:
                st.write("Unavailable")


def _format_explanation_direction(direction: object) -> str:
    if direction == "increases_churn_score":
        return "↑ Increases risk"
    if direction == "decreases_churn_score":
        return "↓ Decreases risk"
    return _format_display_value(direction)


def _render_explanation_notes(notes: object) -> None:
    if isinstance(notes, list) and notes:
        st.caption("Notes")
        for note in notes:
            st.write(f"- {note}")
    else:
        st.write("No explanation notes were returned by the API.")


def _render_feature_contribution_section(result: dict[str, object]) -> None:
    explanation = _get_nested_value(result, "explanation")
    if not isinstance(explanation, dict):
        return

    st.divider()
    st.subheader("Feature Contribution (Tree Model Only)")

    if explanation.get("available") is True:
        top_features = explanation.get("top_features")
        if isinstance(top_features, list) and top_features:
            contribution_rows = []
            for item in top_features:
                if not isinstance(item, dict):
                    continue
                contribution_rows.append(
                    {
                        "Feature": item.get("display_name", item.get("feature", "Unavailable")),
                        "Contribution": item.get("shap_value"),
                        "Direction": _format_explanation_direction(item.get("direction")),
                    }
                )

            if contribution_rows:
                st.table(pd.DataFrame(contribution_rows))
            else:
                st.info("Feature-level explanation is not available for this model.")
        else:
            st.info("Feature-level explanation is not available for this model.")
    else:
        st.info("Feature-level explanation is not available for this model.")

    _render_explanation_notes(explanation.get("notes"))


def _render_single_model_interpretation(result: dict[str, object]) -> None:
    normalized_result = _normalize_prediction_response(result)

    st.divider()
    st.markdown("### Interpretation Notes")
    st.write(
        "This view displays the backend's returned prediction label, probability, threshold metadata, and "
        "interpretation notes without adding extra model explanations or business policy outputs."
    )
    st.write("Feature-level contribution details are shown only when the backend provides them.")
    _render_interpretation_basis(normalized_result)


def _render_compare_mode_interpretation(comparison_results: list[tuple[str, dict[str, object]]]) -> None:
    normalized_results = {
        model_label: _normalize_prediction_response(result) for model_label, result in comparison_results
    }
    tree_result = normalized_results["Tree (XGBoost)"]
    mlp_result = normalized_results["MLP (PyTorch MLP with embeddings)"]

    tree_prediction = tree_result["prediction_label"]
    mlp_prediction = mlp_result["prediction_label"]
    models_agree = tree_prediction == mlp_prediction
    tree_probability = tree_result["prediction_probability"]
    mlp_probability = mlp_result["prediction_probability"]

    st.divider()
    st.markdown("### Interpretation Notes")
    st.write(
        "Compare mode displays the outputs returned by each deployed model endpoint for the same submitted request."
    )
    if models_agree:
        st.write("Both endpoints returned the same prediction label for this submitted profile.")
    else:
        st.write("The endpoints returned different prediction labels for this submitted profile.")

    if isinstance(tree_probability, (int, float)) and isinstance(mlp_probability, (int, float)):
        probability_gap = abs(float(tree_probability) - float(mlp_probability))
        st.write(
            f"The absolute probability difference between the two returned probabilities is `{probability_gap:.6f}`."
        )
    else:
        st.write("The probability difference is unavailable because one or both returned probabilities were not numeric.")

    for model_label, normalized_result in normalized_results.items():
        with st.expander(f"{model_label} interpretation details", expanded=False):
            _render_interpretation_basis(normalized_result)


def _render_single_model_result(selected_model_label: str, result: dict[str, object]) -> None:
    st.subheader("Prediction Result")
    normalized_result = _normalize_prediction_response(result)
    probability = normalized_result["prediction_probability"]
    prediction = normalized_result["prediction_label"]

    st.markdown("#### Executive Summary")
    summary_columns = st.columns(2, gap="medium")
    with summary_columns[0]:
        _render_result_field("Prediction Label", _format_display_value(prediction))
        _render_result_field("Requested Model", selected_model_label)
        _render_result_field("Returned Probability", _format_display_value(probability))
    with summary_columns[1]:
        _render_result_field("Returned Model", _format_display_value(normalized_result["model_name"]))
        _render_result_field("Threshold", _format_display_value(normalized_result["prediction_threshold"]))
        _render_result_field("Threshold Rule", _format_display_value(normalized_result["prediction_threshold_rule"]))

    if isinstance(probability, (int, float)):
        st.progress(min(max(float(probability), 0.0), 1.0))
        st.caption("Predicted churn probability")

    st.divider()
    _render_response_metadata(normalized_result)
    _render_feature_contribution_section(result)


def _render_compare_mode_result(comparison_results: list[tuple[str, dict[str, object]]]) -> None:
    st.subheader("Comparison Result")

    normalized_results = {
        model_label: _normalize_prediction_response(result) for model_label, result in comparison_results
    }
    tree_result = normalized_results["Tree (XGBoost)"]
    mlp_result = normalized_results["MLP (PyTorch MLP with embeddings)"]
    tree_prediction = tree_result["prediction_label"]
    mlp_prediction = mlp_result["prediction_label"]
    models_agree = tree_prediction == mlp_prediction

    st.markdown("#### Executive Comparison Summary")
    summary_columns = st.columns(2, gap="medium")
    tree_probability = tree_result["prediction_probability"]
    mlp_probability = mlp_result["prediction_probability"]
    with summary_columns[0]:
        _render_result_field("Outcome", "Models agree" if models_agree else "Models disagree")
        _render_result_field("Tree Label", _format_display_value(tree_prediction))
    with summary_columns[1]:
        _render_result_field("MLP Label", _format_display_value(mlp_prediction))
        if isinstance(tree_probability, (int, float)) and isinstance(mlp_probability, (int, float)):
            probability_gap = abs(float(tree_probability) - float(mlp_probability))
            _render_result_field("Absolute Probability Difference", f"{probability_gap:.6f}")
        else:
            _render_result_field("Absolute Probability Difference", "Unavailable")

    probability_rows = []

    for model_label, result in comparison_results:
        normalized_result = normalized_results[model_label]
        probability = normalized_result["prediction_probability"]
        prediction = normalized_result["prediction_label"]
        returned_model_name = normalized_result["model_name"]

        st.divider()
        st.markdown(f"#### {model_label}")
        model_columns = st.columns(2, gap="medium")
        with model_columns[0]:
            _render_result_field("Prediction Label", _format_display_value(prediction))
            _render_result_field("Returned Probability", _format_display_value(probability))
        with model_columns[1]:
            _render_result_field("Returned Model", _format_display_value(returned_model_name))
            _render_result_field("Threshold", _format_display_value(normalized_result["prediction_threshold"]))
            _render_result_field(
                "Threshold Rule", _format_display_value(normalized_result["prediction_threshold_rule"])
            )

        with st.expander(f"{model_label} response details", expanded=False):
            _render_response_metadata(normalized_result)
            _render_feature_contribution_section(result)

        if isinstance(probability, (int, float)):
            probability_rows.append(
                {
                    "Model": model_label,
                    "Probability": float(probability),
                }
            )

    st.divider()
    st.subheader("Comparison Summary")
    st.write("Models agree" if models_agree else "Models disagree")
    if isinstance(tree_probability, (int, float)) and isinstance(mlp_probability, (int, float)):
        st.write(f"Absolute probability difference: {abs(float(tree_probability) - float(mlp_probability)):.6f}")

    if probability_rows:
        st.subheader("Probability Comparison")
        st.bar_chart(probability_rows, x="Model", y="Probability", horizontal=True)


st.set_page_config(page_title="Churn Risk Predictor", layout="wide")
_initialize_form_state()

st.sidebar.markdown("## System & Control Panel")
api_base_url = st.sidebar.text_input("API base URL", value=DEFAULT_API_BASE_URL).rstrip("/")
st.sidebar.markdown("### API Connection")
try:
    health_response = requests.get(f"{api_base_url}/health", timeout=10)
except requests.RequestException as error:
    st.sidebar.error(f"API status: unreachable ({error})")
else:
    if health_response.ok:
        st.sidebar.success("API status: reachable")
        health_payload = health_response.json()
        readiness_fields = [
            "tree_model_loaded",
            "tree_preprocessor_loaded",
            "tree_feature_schema_loaded",
            "mlp_model_loaded",
            "mlp_preprocessor_loaded",
            "mlp_category_maps_loaded",
        ]
        for field_name in readiness_fields:
            readiness_value = health_payload.get(field_name)
            readiness_label = field_name.replace("_", " ").capitalize()
            st.sidebar.write(f"{readiness_label}: {readiness_value}")
    else:
        st.sidebar.error(f"API status: unreachable (health check returned {health_response.status_code})")

st.sidebar.markdown("### Prediction Settings")
prediction_mode = st.sidebar.selectbox("Prediction Mode", ["Single model", "Compare both models"], key="prediction_mode")
selected_model_label = st.session_state.get("selected_model_label", list(MODEL_OPTIONS.keys())[0])
if prediction_mode == "Single model":
    selected_model_label = st.sidebar.selectbox("Prediction Model", list(MODEL_OPTIONS.keys()), key="selected_model_label")
selected_endpoint_path = MODEL_OPTIONS[selected_model_label]
metadata_payload, metadata_error = _run_metadata_request(api_base_url)

st.markdown("# Telecom Churn Risk Predictor")
st.markdown("Estimate churn risk for a single customer profile using the deployed API models.")
st.caption("Use the workspace below to enter a customer profile and review single-model or compare-mode results.")

left_column, right_column = st.columns([1.0, 1.25], gap="large")

with left_column:
    st.markdown("### Customer Profile")
    st.caption("Enter the customer attributes used for the current churn prediction request.")
    with st.form("prediction_form"):
        st.markdown("#### Demographics")
        gender = st.selectbox("Customer Gender", ["Female", "Male"], key="gender")
        seniorcitizen = st.selectbox(
            "Senior Citizen Status",
            [0, 1],
            key="seniorcitizen",
            format_func=lambda value: "Yes" if value == 1 else "No",
            help="Select whether the customer is classified as a senior citizen.",
        )
        partner = st.selectbox(
            "Partner Status",
            ["No", "Yes"],
            key="partner",
            help="Indicates whether the customer has a partner.",
        )
        dependents = st.selectbox(
            "Dependents Status",
            ["No", "Yes"],
            key="dependents",
            help="Indicates whether the customer has dependents on the household account.",
        )
        tenure = st.number_input(
            "Tenure (Months)",
            min_value=0.0,
            step=1.0,
            key="tenure",
            help="Number of months the customer has stayed with the company.",
        )

        st.markdown("#### Services")
        phoneservice = st.selectbox(
            "Phone Service",
            ["No", "Yes"],
            key="phoneservice",
            help="Indicates whether the customer has phone service.",
        )
        multiplelines = st.selectbox(
            "Multiple Lines",
            ["No", "No phone service", "Yes"],
            key="multiplelines",
            help="Applies only when phone service is included on the account.",
        )
        internetservice = st.selectbox(
            "Internet Service Type",
            ["DSL", "Fiber optic", "No"],
            key="internetservice",
            help="Primary internet service currently used by the customer.",
        )
        onlinesecurity = st.selectbox(
            "Online Security",
            ["No", "No internet service", "Yes"],
            key="onlinesecurity",
            help="Security add-on tied to the customer's internet service.",
        )
        onlinebackup = st.selectbox(
            "Online Backup",
            ["No", "No internet service", "Yes"],
            key="onlinebackup",
            help="Backup service tied to the customer's internet service.",
        )
        deviceprotection = st.selectbox(
            "Device Protection",
            ["No", "No internet service", "Yes"],
            key="deviceprotection",
            help="Device protection add-on tied to the customer's internet service.",
        )
        techsupport = st.selectbox(
            "Tech Support",
            ["No", "No internet service", "Yes"],
            key="techsupport",
            help="Technical support service available with the customer's internet plan.",
        )
        streamingtv = st.selectbox(
            "Streaming TV",
            ["No", "No internet service", "Yes"],
            key="streamingtv",
            help="TV streaming service that depends on internet service.",
        )
        streamingmovies = st.selectbox(
            "Streaming Movies",
            ["No", "No internet service", "Yes"],
            key="streamingmovies",
            help="Movie streaming service that depends on internet service.",
        )

        st.markdown("#### Contract & Billing")
        contract = st.selectbox(
            "Contract Type",
            ["Month-to-month", "One year", "Two year"],
            key="contract",
            help="Current contract term for the customer account.",
        )
        paperlessbilling = st.selectbox(
            "Paperless Billing",
            ["No", "Yes"],
            key="paperlessbilling",
            help="Indicates whether billing statements are delivered digitally.",
        )
        paymentmethod = st.selectbox(
            "Payment Method",
            [
                "Bank transfer (automatic)",
                "Credit card (automatic)",
                "Electronic check",
                "Mailed check",
            ],
            key="paymentmethod",
            help="Primary billing payment method used by the customer.",
        )
        monthlycharges = st.number_input(
            "Monthly Charges ($)",
            min_value=0.0,
            step=0.1,
            key="monthlycharges",
            help="Current recurring monthly bill amount in dollars.",
        )
        totalcharges = st.number_input(
            "Total Charges ($)",
            min_value=0.0,
            step=0.1,
            key="totalcharges",
            help="Cumulative amount billed to the customer over time, in dollars.",
        )

        st.divider()
        st.markdown("#### Actions")
        st.caption("Run the prediction when the profile is ready, or reset the form to start over.")
        action_columns = st.columns([1.7, 1.0], gap="small")
        with action_columns[0]:
            submitted = st.form_submit_button("Run Churn Prediction", use_container_width=True)
        with action_columns[1]:
            reset_requested = st.form_submit_button("Reset Form", use_container_width=True)

with right_column:
    st.markdown("### Results")
    st.caption("Review the prediction summary and supporting notes after running the profile.")
    result_container = st.container()

if reset_requested:
    _reset_form_state()
    st.rerun()

if not submitted:
    with result_container:
        st.info(
            "No prediction has been run yet. Complete the customer profile, then select `Run Churn Prediction` "
            "to review the latest result here."
        )

if submitted:
    try:
        totalcharges_value = float(totalcharges)
    except ValueError:
        with result_container:
            st.error("Enter a valid numeric value for Total Charges ($) before running the prediction.")
    else:
        payload = {
            "gender": gender,
            "seniorcitizen": seniorcitizen,
            "partner": partner,
            "dependents": dependents,
            "tenure": tenure,
            "phoneservice": phoneservice,
            "multiplelines": multiplelines,
            "internetservice": internetservice,
            "onlinesecurity": onlinesecurity,
            "onlinebackup": onlinebackup,
            "deviceprotection": deviceprotection,
            "techsupport": techsupport,
            "streamingtv": streamingtv,
            "streamingmovies": streamingmovies,
            "contract": contract,
            "paperlessbilling": paperlessbilling,
            "paymentmethod": paymentmethod,
            "monthlycharges": monthlycharges,
            "totalcharges": totalcharges_value,
        }

        if prediction_mode == "Single model":
            with result_container:
                with st.spinner("Running churn prediction..."):
                    result, error_message = _run_prediction_request(api_base_url, selected_endpoint_path, payload)
            if error_message is not None:
                with result_container:
                    st.error(f"Prediction could not be completed. {error_message}")
            else:
                with result_container:
                    st.success("Prediction complete. The current result is ready for review.")
                    _render_single_model_result(selected_model_label, result)
                    _render_single_model_interpretation(result)
        else:
            comparison_results = []
            comparison_errors = []

            with result_container:
                with st.spinner("Running churn prediction comparison..."):
                    for model_label, endpoint_path in MODEL_OPTIONS.items():
                        result, error_message = _run_prediction_request(api_base_url, endpoint_path, payload)
                        if error_message is not None:
                            comparison_errors.append(f"{model_label}: {error_message}")
                        else:
                            comparison_results.append((model_label, result))

            if comparison_errors:
                with result_container:
                    for error_message in comparison_errors:
                        st.error(f"Prediction could not be completed. {error_message}")

            if len(comparison_results) == len(MODEL_OPTIONS):
                with result_container:
                    st.success("Prediction comparison complete. The current results are ready for review.")
                    _render_compare_mode_result(comparison_results)
                    _render_compare_mode_interpretation(comparison_results)

with right_column:
    _render_model_deployment_metadata(metadata_payload, metadata_error)

st.divider()
st.subheader("Limitations")
st.caption("Operational boundaries for using this prototype in a decision-support context.")
st.write("This frontend is a prototype for demonstrating the deployed churn prediction API.")
st.write("It does not include live CRM integration or direct access to customer systems.")
st.write("Predictions depend on the API being available and its model artifacts loading correctly.")
st.write("Use the output as decision support only, not as a standalone business decision.")
