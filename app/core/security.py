"""jwt security helpers - token creation and decoding."""

import hashlib
import hmac as _hmac
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """create a signed jwt access token.

    Args:
        data: claims to encode into the token.
        expires_delta: custom expiry window. defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        signed jwt string.
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return str(jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM))


def decode_token(token: str) -> dict[str, Any]:
    """decode and validate a jwt token.

    Args:
        token: jwt string to decode.

    Returns:
        decoded claims dict.

    Raises:
        HTTPException: 401 if token is invalid or expired.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def sign_payload(secret: str, body: bytes) -> str:
    """compute an hmac-sha256 signature over body using secret.

    args:
        secret: the subscriber's signing secret.
        body: the raw request body bytes.

    returns:
        a string of the form 'sha256=<hex_digest>'.
    """
    digest = _hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
