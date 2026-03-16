from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import User


router = APIRouter()


class SignUpRequest(BaseModel):
    user_id: str
    email: str
    nickname: str


class LoginRequest(BaseModel):
    user_id: str


class DevLoginRequest(BaseModel):
    user_id: str = "dev-user-001"
    email: str = "dev@example.com"
    nickname: str = "개발테스트유저"


@router.post("/signup")
def signup(payload: SignUpRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = User(**payload.model_dump())
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user_id or email already exists")
    return {"message": "회원가입 성공", "user_id": payload.user_id}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    # Firebase token verification should be done before calling this endpoint.
    user = db.scalar(select(User).where(User.user_id == payload.user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return {"message": "로그인 성공", "user_id": user.user_id, "nickname": user.nickname}


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
