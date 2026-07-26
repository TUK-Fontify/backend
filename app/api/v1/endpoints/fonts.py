from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user_id
from app.db.session import get_db
from app.models import DownloadRecord, FontFile, GeneratedFont, Rating


router = APIRouter()
generated_fonts_router = APIRouter()


class FontFileItem(BaseModel):
    font_id: int
    name: str
    file_url: str


class FontFileDetail(FontFileItem):
    pass


class GeneratedFontItem(BaseModel):
    generated_font_id: int
    file_url: str
    font_id : int


class GeneratedFontDetail(BaseModel):
    generated_font_id: int
    file_url: str
    font_id : int


class DownloadResponse(BaseModel):
    file_url: str


class RateRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = None


class RateResponse(BaseModel):
    rating_id: int
    score: int
    comment: str | None = None


class RatingItem(BaseModel):
    rating_id: int
    user_id: str
    generated_font_id: int
    score: int
    comment: str | None
    rated_at: datetime


def _to_file_url(file_path: str) -> str:
    if file_path.startswith("static/"):
        return "/" + file_path[len("static/") :]
    if file_path.startswith("/"):
        return file_path
    return "/" + file_path


@router.get("", response_model=list[FontFileItem])
def list_fonts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(get_db),
) -> list[FontFileItem]:
    offset = (page - 1) * limit
    rows = db.scalars(
        select(FontFile).order_by(FontFile.font_id.desc()).offset(offset).limit(limit)
    ).all()
    return [
        FontFileItem(
            font_id=r.font_id,
            name=r.font_family.name,
            file_url=_to_file_url(r.file_path),
        )
        for r in rows
    ]


@router.get("/{font_id}", response_model=FontFileDetail)
def get_font(font_id: int, db: Session = Depends(get_db)) -> FontFileDetail:
    font = db.scalar(select(FontFile).where(FontFile.font_id == font_id))
    if not font:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="font not found")
    return FontFileDetail(
        font_id=font.font_id,
        name=font.font_family.name,
        file_url=_to_file_url(font.file_path),
    )


@router.post("/{font_id}/download", response_model=DownloadResponse)
def download_font(
    font_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DownloadResponse:
    font = db.scalar(select(GeneratedFont).where(GeneratedFont.generated_font_id == font_id))
    if not font:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="font not found")

    db.add(DownloadRecord(user_id=user_id, generated_font_id=font_id))
    db.commit()

    return DownloadResponse(file_url=font.file_url)


@router.post("/{font_id}/tag")
def tag_font(font_id: int, user_id: str = Depends(get_current_user_id)) -> dict[str, str]:
    # Tagging is currently a no-op placeholder. Real implementation should associate
    # the font with the user's handwriting/tag data.
    return {"message": "tag registered"}


@generated_fonts_router.get("", response_model=list[GeneratedFontItem])
def list_generated_fonts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(get_db),
) -> list[GeneratedFontItem]:
    offset = (page - 1) * limit
    rows = db.scalars(
        select(GeneratedFont).order_by(GeneratedFont.generated_font_id.desc()).offset(offset).limit(limit)
    ).all()
    return [
        GeneratedFontItem(generated_font_id=r.generated_font_id, file_url=r.file_url)
        for r in rows
    ]


@generated_fonts_router.get("/{font_id}", response_model=GeneratedFontDetail)
def get_generated_font(font_id: int, db: Session = Depends(get_db)) -> GeneratedFontDetail:
    font = db.scalar(select(GeneratedFont).where(GeneratedFont.generated_font_id == font_id))
    if not font:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="font not found")
    return GeneratedFontDetail(generated_font_id=font.generated_font_id, file_url=font.file_url, font_id=font.font_id)


@generated_fonts_router.post("/{font_id}/rate", response_model=RateResponse)
def rate_generated_font(
    font_id: int,
    payload: RateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RateResponse:
    font = db.scalar(select(GeneratedFont).where(GeneratedFont.generated_font_id == font_id))
    if not font:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="font not found")

    rating = db.scalar(
        select(Rating).where(
            Rating.user_id == user_id,
            Rating.generated_font_id == font_id,
        )
    )
    if rating:
        rating.score = payload.score
        rating.comment = payload.comment
    else:
        rating = Rating(
            user_id=user_id,
            generated_font_id=font_id,
            score=payload.score,
            comment=payload.comment,
        )
        db.add(rating)

    db.commit()
    db.refresh(rating)
    return RateResponse(rating_id=rating.rating_id, score=rating.score, comment=rating.comment)


@generated_fonts_router.get("/{font_id}/rate", response_model=list[RatingItem])
def list_generated_font_ratings(font_id: int, db: Session = Depends(get_db)) -> list[RatingItem]:
    rows = db.execute(
        select(
            Rating.rating_id,
            Rating.user_id,
            Rating.generated_font_id,
            Rating.score,
            Rating.comment,
            Rating.rated_at,
        )
        .join(GeneratedFont, GeneratedFont.generated_font_id == Rating.generated_font_id)
        .where(Rating.generated_font_id == font_id)
        .order_by(Rating.rated_at.desc())
    ).all()

    return [
        RatingItem(
            rating_id=r[0],
            user_id=r[1],
            generated_font_id=r[2],
            score=r[4],
            comment=r[5],
            rated_at=r[6],
        )
        for r in rows
    ]
