"""unit tests for jwt security helpers."""

from datetime import timedelta

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, decode_token


def test_create_access_token_returns_decodable_jwt() -> None:
    """token encodes claims and is decodable with the same secret."""
    data = {"sub": "service-a"}
    token = create_access_token(data)

    assert isinstance(token, str)
    claims = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    assert claims["sub"] == "service-a"
    assert "exp" in claims


def test_create_access_token_respects_custom_expiry() -> None:
    """custom expires_delta is reflected in the exp claim."""
    data = {"sub": "service-b"}
    token = create_access_token(data, expires_delta=timedelta(hours=2))
    claims = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    assert "exp" in claims


def test_decode_token_returns_claims_for_valid_token() -> None:
    """decode_token returns the full claims dict for a fresh token."""
    data = {"sub": "service-c", "role": "worker"}
    token = create_access_token(data)
    claims = decode_token(token)
    assert claims["sub"] == "service-c"
    assert claims["role"] == "worker"


def test_decode_token_raises_401_for_expired_token() -> None:
    """decode_token raises http 401 when the token is already expired."""
    token = create_access_token({"sub": "service-d"}, expires_delta=timedelta(days=-1))
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers is not None
    assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"


def test_decode_token_raises_401_for_garbage_token() -> None:
    """decode_token raises http 401 for a completely invalid token string."""
    with pytest.raises(HTTPException) as exc_info:
        decode_token("not.a.real.token")
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers is not None
    assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"
