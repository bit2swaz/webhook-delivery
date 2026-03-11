"""fastapi dependencies - db session injection, jwt verification."""

from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_token
from app.db.session import get_db as get_db

__all__ = ["get_db", "oauth2_scheme", "verify_jwt"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def verify_jwt(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict[str, Any]:
    """extract and validate the bearer token. raises http 401 on failure.

    Args:
        token: bearer token extracted from the Authorization header.

    Returns:
        decoded claims dict from the jwt payload.
    """
    return decode_token(token)
