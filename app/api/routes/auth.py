"""auth token endpoint."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import verify_jwt
from app.api.openapi_examples import TOKEN_RESPONSE_EXAMPLE, UNAUTHORIZED_EXAMPLE
from app.core.security import create_access_token
from app.db.schemas import TokenResponse

router = APIRouter()


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Issue a service JWT",
    description=(
        "Issues a signed JWT for service-to-service authentication. "
        "No credentials are required — any caller receives a valid token. "
        "Include the returned `access_token` as a `Bearer` token in the "
        "`Authorization` header of all subsequent requests."
    ),
    response_description="JWT access token and token type.",
    responses={
        200: {"content": {"application/json": {"example": TOKEN_RESPONSE_EXAMPLE}}},
    },
)
async def issue_token() -> TokenResponse:
    """issue a service-to-service jwt token.

    no user database check - any caller receives a valid jwt.

    Returns:
        token response with access_token and token_type.
    """
    token = create_access_token({"sub": "service"})
    return TokenResponse(access_token=token, token_type="bearer")


@router.get(
    "/me",
    summary="Inspect current token",
    description="Returns the decoded JWT claims for the bearer token in the request.",
    response_description="Decoded JWT payload as a JSON object.",
    responses={
        401: {
            "description": "Missing or invalid token.",
            "content": {"application/json": {"example": UNAUTHORIZED_EXAMPLE}},
        },
    },
)
async def get_me(
    payload: Annotated[dict[str, Any], Depends(verify_jwt)],
) -> dict[str, Any]:
    """return the decoded jwt claims for the current token.

    Returns:
        decoded claims dict from the bearer token.
    """
    return payload
