import secrets
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.database import get_db
from app.middleware.auth_middleware import get_current_user, get_redis
from app.middleware.rate_limit import limiter
from app.services import auth_service
from app.services import oauth_service
from app.schemas.user import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
    RefreshRequest, OAuthCallbackRequest,
)
from app.schemas.common import success

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
@limiter.limit("10/minute")
async def register(request: Request, body: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register_user(db, body.email, body.password, body.full_name)
    return success(UserResponse.model_validate(user).model_dump(), "Registration successful")


@router.post("/login")
@limiter.limit("20/minute")
async def login(
    request: Request,
    body: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user = await auth_service.authenticate_user(db, body.email, body.password)
    access_token = auth_service.create_access_token(str(user.id), user.role.value)
    refresh_token = auth_service.create_refresh_token()
    await auth_service.store_refresh_token(redis, refresh_token, str(user.id))
    return success(
        TokenResponse(access_token=access_token, refresh_token=refresh_token).model_dump(),
        "Login successful",
    )


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user_id = await auth_service.validate_refresh_token(redis, body.refresh_token)
    user = await auth_service.get_user_by_id(db, user_id)
    await auth_service.revoke_refresh_token(redis, body.refresh_token)
    new_refresh = auth_service.create_refresh_token()
    await auth_service.store_refresh_token(redis, new_refresh, user_id)
    access_token = auth_service.create_access_token(user_id, user.role.value)
    return success(
        TokenResponse(access_token=access_token, refresh_token=new_refresh).model_dump(),
        "Token refreshed",
    )


@router.post("/logout")
async def logout(
    body: RefreshRequest,
    redis: Redis = Depends(get_redis),
):
    await auth_service.revoke_refresh_token(redis, body.refresh_token)
    return success(message="Logged out")


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return success(UserResponse.model_validate(user).model_dump())


@router.get("/oauth/google")
async def google_oauth_redirect():
    """Return the Google authorization URL for the client to redirect to."""
    state = secrets.token_urlsafe(16)
    url = oauth_service.get_google_auth_url(state)
    return success({"authorization_url": url, "state": state})


@router.post("/oauth/google/callback")
async def google_oauth_callback(
    body: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Exchange a Google authorization code for LitMusic JWT tokens."""
    token_data = await oauth_service.exchange_google_code(body.code)
    user_info = await oauth_service.get_google_user_info(token_data["access_token"])
    user = await auth_service.find_or_create_oauth_user(
        db,
        email=user_info["email"],
        full_name=user_info.get("name", ""),
        provider="google",
        provider_id=user_info["sub"],
    )
    access_token = auth_service.create_access_token(str(user.id), user.role.value)
    refresh_token = auth_service.create_refresh_token()
    await auth_service.store_refresh_token(redis, refresh_token, str(user.id))
    return success(
        TokenResponse(access_token=access_token, refresh_token=refresh_token).model_dump(),
        "OAuth login successful",
    )
