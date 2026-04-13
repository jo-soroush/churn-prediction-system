from pydantic import BaseModel


class ErrorBody(BaseModel):
    type: str
    message: str
    details: list[object] | dict[str, object] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str


class PredictionRequestMetadata(BaseModel):
    request_id: str
    timestamp_utc: str


class PredictionContractMetadata(BaseModel):
    contract_version: str
    schema_version: str


class PredictionModelMetadata(BaseModel):
    model_key: str
    model_name: str
    model_family: str
    artifact_set: str


class PredictionResultBody(BaseModel):
    label: str
    probability: float
    threshold: float
    threshold_rule: str


class InterpretationBasis(BaseModel):
    label_source: str
    feature_level_explanation_available: bool
    notes: list[str]


class PredictionExplanationFeature(BaseModel):
    feature: str
    display_name: str
    shap_value: float
    direction: str


class PredictionExplanationBody(BaseModel):
    available: bool
    method: str | None = None
    top_features: list[PredictionExplanationFeature]
    notes: list[str]


class ModelSelectionProtocol(BaseModel):
    training_split: str
    selection_split: str
    final_reporting_split: str


class RuntimeCompatibilityMetadata(BaseModel):
    python_version: str
    pytorch_version: str
    xgboost_version: str
    scikit_learn_version: str
    joblib_version: str
    pandas_version: str
    numpy_version: str
    notes: str


class InputSchemaMetadata(BaseModel):
    feature_columns: list[str]
    numeric_features: list[str]
    categorical_features: list[str]


class TechnicalModelMetadata(BaseModel):
    tree_model_family: str
    tree_model_parameters: dict[str, int | float | str]
    neural_model_family: str
    neural_model_configuration: dict[str, int | float | str | list[int]]


class DeploymentMetadataResponse(BaseModel):
    artifact_bundle_version: str
    schema_version: str
    feature_order_version: str
    selection_protocol: ModelSelectionProtocol
    dependency_compatibility: RuntimeCompatibilityMetadata
    input_schema: InputSchemaMetadata
    technical_models: TechnicalModelMetadata


class TreePredictionRequest(BaseModel):
    gender: str
    seniorcitizen: int
    partner: str
    dependents: str
    tenure: float
    phoneservice: str
    multiplelines: str
    internetservice: str
    onlinesecurity: str
    onlinebackup: str
    deviceprotection: str
    techsupport: str
    streamingtv: str
    streamingmovies: str
    contract: str
    paperlessbilling: str
    paymentmethod: str
    monthlycharges: float
    totalcharges: float


class TreePredictionResponse(BaseModel):
    request: PredictionRequestMetadata
    contract: PredictionContractMetadata
    model: PredictionModelMetadata
    prediction_result: PredictionResultBody
    interpretation_basis: InterpretationBasis
    explanation: PredictionExplanationBody
