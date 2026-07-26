from datetime import datetime

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user_id
from app.db.session import get_db
from app.models import DownloadRecord, FontFamily, FontFile, GeneratedFont, GenerationJob, Rating, User


router = APIRouter()

class MeResponse(BaseModel):
    user_id: str
    email: str
    nickname: str
    created_at: datetime


class MeUpdateRequest(BaseModel):
    nickname: str


class MeUpdateResponse(BaseModel):
    user_id: str
    nickname: str
    updated_at: datetime


class RatingItem(BaseModel):
    rating_id: int
    user_id: str
    generated_font_id: int
    score: int
    comment: str | None
    rated_at: datetime


class GenerationJobItem(BaseModel):
    job_id: int
    user_id: str
    status: str
    progress: int
    similarity_percent: float | None
    requested_at: datetime
    finished_at: datetime | None
    font_name: str | None


class DownloadItem(BaseModel):
    download_id: int
    user_id: str
    font_id: int | None
    generated_font_id: int | None
    file_url: str
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


@router.patch("/me", response_model=MeUpdateResponse)
def patch_me(
    payload: MeUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MeUpdateResponse:
    user = db.scalar(select(User).where(User.user_id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    user.nickname = payload.nickname
    db.commit()
    db.refresh(user)
    return MeUpdateResponse(user_id=user.user_id, nickname=user.nickname, updated_at=user.updated_at)


@router.get("/me/ratings", response_model=list[RatingItem])
def get_my_ratings(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[RatingItem]:
    rows = db.execute(
        select(Rating.rating_id, Rating.generated_font_id, Rating.score, Rating.comment, Rating.rated_at)
        .join(GeneratedFont, GeneratedFont.generated_font_id == Rating.generated_font_id)
        .where(Rating.user_id == user_id)
        .order_by(Rating.rated_at.desc())
    ).all()
    return [
    RatingItem(
        rating_id=r[0],
        user_id=user_id,
        generated_font_id=r[1],
        score=r[2],
        comment=r[3],
        rated_at=r[4],
    )
    for r in rows
]


@router.get("/me/generations", response_model=list[GenerationJobItem])
def get_my_generations(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[GenerationJobItem]:
    rows = db.execute(
        select(
            GenerationJob.job_id,
            GenerationJob.status,
            GenerationJob.progress,
            GenerationJob.similarity_percent,
            GenerationJob.requested_at,
            GenerationJob.finished_at,
            FontFamily.name,
        )
        .outerjoin(FontFile, FontFile.font_file_id == GenerationJob.font_file_id)
        .outerjoin(FontFamily, FontFamily.font_family_id == FontFile.font_family_id)
        .where(GenerationJob.user_id == user_id)
        .order_by(GenerationJob.requested_at.desc())
    ).all()

    return [
        GenerationJobItem(
            job_id=r[0],
            user_id=user_id,
            status=r[1],
            progress=r[2],
            similarity_percent=float(r[3]) if r[3] is not None else None,
            requested_at=r[4],
            finished_at=r[5],
            font_name=r[6] or "",
        )
        for r in rows
    ]


@router.get("/me/downloads", response_model=list[DownloadItem])
def get_my_downloads(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[DownloadItem]:
    rows = db.execute(
        select(
            DownloadRecord.download_id,
            GeneratedFont.generated_font_id,
            GeneratedFont.file_url,
            DownloadRecord.downloaded_at,
        )
        .join(GeneratedFont, GeneratedFont.generated_font_id == DownloadRecord.generated_font_id)
        .where(DownloadRecord.user_id == user_id)
        .order_by(DownloadRecord.downloaded_at.desc())
    ).all()

    return [
        DownloadItem(
            download_id=r[0],
            font_id=None,
            user_id=user_id,
            generated_font_id=r[1],
            file_url=r[3],
            downloaded_at=r[4],
        )
        for r in rows
    ]
