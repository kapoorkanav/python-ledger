import hmac
import os

from fastapi import Header, HTTPException, status


def _configured_key() -> str:
    key = os.environ.get("LEDGER_API_KEY")
    if not key:
        raise RuntimeError(
            "LEDGER_API_KEY is not set. Money-moving endpoints refuse to run "
            "without a configured caller secret."
        )
    return key


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = _configured_key()
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
