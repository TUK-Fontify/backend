from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import User


router = APIRouter()


class GoogleIdTokenRequest(BaseModel):
    google_id_token: str


class AuthResponse(BaseModel):
    user_id: str
    email: str
    nickname: str
    created_at: datetime


def _parse_google_id_token(google_id_token: str) -> Dict[str, Any]:
    # NOTE: In a real app, validate the token with Firebase / Google APIs.
    # Here we support a simple base64-encoded JSON payload for local testing.
    try:
        padded = google_id_token + "=" * (-len(google_id_token) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid google_id_token")


def _extract_user_info(payload: Dict[str, Any]) -> tuple[str, str, str]:
    user_id = payload.get("sub") or payload.get("user_id") or payload.get("uid")
    email = payload.get("email")
    nickname = payload.get("name") or payload.get("nickname")

    if not user_id or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="google_id_token must include user_id and email")

    if not nickname:
        nickname = email.split("@", 1)[0]

    return user_id, email, nickname


@router.post("/signup", response_model=AuthResponse)
def signup(payload: GoogleIdTokenRequest, db: Session = Depends(get_db)) -> AuthResponse:
    payload_data = _parse_google_id_token(payload.google_id_token)
    user_id, email, nickname = _extract_user_info(payload_data)

    user = User(user_id=user_id, email=email, nickname=nickname)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user_id or email already exists")

    return AuthResponse(user_id=user.user_id, email=user.email, nickname=user.nickname, created_at=user.created_at)


@router.post("/login", response_model=AuthResponse)
def login(payload: GoogleIdTokenRequest, db: Session = Depends(get_db)) -> AuthResponse:
    payload_data = _parse_google_id_token(payload.google_id_token)
    user_id, _, _ = _extract_user_info(payload_data)

    user = db.scalar(select(User).where(User.user_id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    return AuthResponse(user_id=user.user_id, email=user.email, nickname=user.nickname, created_at=user.created_at)


class DevLoginRequest(BaseModel):
    user_id: str = "dev-user-001"
    email: str = "dev@example.com"
    nickname: str = "개발테스트유저"


@router.post("/dev-login")
def dev_login(payload: DevLoginRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    if not settings.DEV_BYPASS_AUTH:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="DEV_BYPASS_AUTH is disabled")

    user = db.scalar(select(User).where(User.user_id == payload.user_id))
    if not user:
        user = User(user_id=payload.user_id, email=payload.email, nickname=payload.nickname)
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "message": "개발 로그인 성공",
        "user_id": user.user_id,
        "nickname": user.nickname,
        "use_header": {"x-user-id": user.user_id},
    }
