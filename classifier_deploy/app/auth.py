import hmac

from fastapi import Header, HTTPException

from app.config import settings


AUTH_FAILURE_DETAIL = "Authentication required"


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.api_auth_enabled:
        return

    expected_api_key = settings.api_key
    if not expected_api_key:
        raise RuntimeError("API authentication is enabled but API_KEY is not configured.")

    if x_api_key is None or not hmac.compare_digest(x_api_key, expected_api_key):
        raise HTTPException(status_code=401, detail=AUTH_FAILURE_DETAIL)
