from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import BaseFont, DownloadRecord, GeneratedFont, Rating


router = APIRouter()


class BaseFontItem(BaseModel):
    base_font_id: int
    name: str


class GeneratedFontItem(BaseModel):
    generated_font_id: int
    name: str
    file_url: str


class GeneratedFontDetail(BaseModel):
    generated_font_id: int
    name: str
    file_url: str
    created_at: datetime


class RateRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = None


@router.get("")
def list_fonts(
    type: Literal["base", "generated"] = Query(...),
    db: Session = Depends(get_db),
) -> list[BaseFontItem] | list[GeneratedFontItem]:
    if type == "base":
        rows = db.scalars(select(BaseFont).order_by(BaseFont.base_font_id.desc())).all()
        return [BaseFontItem(base_font_id=r.base_font_id, name=r.name) for r in rows]

    rows = db.scalars(select(GeneratedFont).order_by(GeneratedFont.generated_font_id.desc())).all()
    return [GeneratedFontItem(generated_font_id=r.generated_font_id, name=r.name, file_url=r.file_url) for r in rows]


@router.get("/{font_id}", response_model=GeneratedFontDetail)
def get_font(font_id: int, db: Session = Depends(get_db)) -> GeneratedFontDetail:
    font = db.scalar(select(GeneratedFont).where(GeneratedFont.generated_font_id == font_id))
    if not font:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="font not found")
    return GeneratedFontDetail(
        generated_font_id=font.generated_font_id,
        name=font.name,
        file_url=font.file_url,
        created_at=font.created_at,
    )


@router.post("/{font_id}/download")
def download_font(
    font_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    font = db.scalar(select(GeneratedFont).where(GeneratedFont.generated_font_id == font_id))
    if not font:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="font not found")

    db.add(DownloadRecord(user_id=user_id, generated_font_id=font_id))
    db.commit()
    return {"message": "다운로드 기록 저장 완료"}


@router.post("/{font_id}/rate")
def rate_font(
    font_id: int,
    payload: RateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, str]:
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
    return {"message": "평점 등록 완료"}
