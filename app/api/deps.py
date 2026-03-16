from fastapi import Header, HTTPException, status

from app.core.config import settings


def get_current_user_id(x_user_id: str | None = Header(default=None)) -> str:
    if x_user_id:
        return x_user_id

    if settings.DEV_BYPASS_AUTH:
        return settings.DEV_USER_ID

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="x-user-id header is required (or enable DEV_BYPASS_AUTH=true)",
    )
