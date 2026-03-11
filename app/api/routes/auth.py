"""auth token endpoint."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import verify_jwt
from app.core.security import create_access_token
from app.db.schemas import TokenResponse

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
async def issue_token() -> TokenResponse:
    """issue a service-to-service jwt token.

    no user database check - any caller receives a valid jwt.

    Returns:
        token response with access_token and token_type.
    """
    token = create_access_token({"sub": "service"})
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me")
async def get_me(
    payload: Annotated[dict[str, Any], Depends(verify_jwt)],
) -> dict[str, Any]:
    """return the decoded jwt claims for the current token.

    Returns:
        decoded claims dict from the bearer token.
    """
    return payload
