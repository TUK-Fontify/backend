from datetime import datetime

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import DownloadRecord, GeneratedFont, GenerationJob, User


router = APIRouter()


class MeResponse(BaseModel):
    user_id: str
    email: str
    nickname: str
    created_at: datetime


class MeUpdateRequest(BaseModel):
    nickname: str


class RecentFontResponse(BaseModel):
    generated_font_id: int
    name: str
    created_at: datetime


class DownloadListResponse(BaseModel):
    generated_font_id: int
    name: str
    downloaded_at: datetime


@router.get("/me", response_model=MeResponse)
def get_me(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MeResponse:
    user = db.scalar(select(User).where(User.user_id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return MeResponse(user_id=user.user_id, email=user.email, nickname=user.nickname, created_at=user.created_at)


@router.patch("/me")
def patch_me(
    payload: MeUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = db.scalar(select(User).where(User.user_id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    user.nickname = payload.nickname
    db.commit()
    return {"message": "수정 완료"}


@router.get("/me/recent", response_model=list[RecentFontResponse])
def get_recent_fonts(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[RecentFontResponse]:
    rows = db.execute(
        select(GeneratedFont.generated_font_id, GeneratedFont.name, GeneratedFont.created_at)
        .join(GenerationJob, GenerationJob.job_id == GeneratedFont.job_id)
        .where(GenerationJob.user_id == user_id)
        .order_by(GeneratedFont.created_at.desc())
    ).all()
    return [RecentFontResponse(generated_font_id=r[0], name=r[1], created_at=r[2]) for r in rows]


@router.get("/me/downloadlist", response_model=list[DownloadListResponse])
def get_download_list(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[DownloadListResponse]:
    rows = db.execute(
        select(GeneratedFont.generated_font_id, GeneratedFont.name, DownloadRecord.downloaded_at)
        .join(DownloadRecord, DownloadRecord.generated_font_id == GeneratedFont.generated_font_id)
        .where(DownloadRecord.user_id == user_id)
        .order_by(DownloadRecord.downloaded_at.desc())
    ).all()
    return [DownloadListResponse(generated_font_id=r[0], name=r[1], downloaded_at=r[2]) for r in rows]
