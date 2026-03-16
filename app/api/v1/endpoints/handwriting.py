from datetime import datetime
from pathlib import Path

from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import FontFile, GenerationJob, Handwriting


router = APIRouter()
UPLOAD_DIR = Path("uploads")


class UploadResponse(BaseModel):
    handwriting_id: int
    image_url: str


class CreateRequest(BaseModel):
    handwriting_id: int
    font_file_id: int


class CreateResponse(BaseModel):
    job_id: int
    status: str


@router.post("/upload", response_model=UploadResponse)
async def upload_handwriting(
    image: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UploadResponse:
    if not image.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="image filename is required")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{image.filename}"
    saved_path = UPLOAD_DIR / saved_name
    content = await image.read()
    saved_path.write_bytes(content)

    item = Handwriting(image_url=f"/uploads/{saved_name}", user_id=user_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return UploadResponse(handwriting_id=item.handwriting_id, image_url=item.image_url)


@router.post("/create", response_model=CreateResponse)
def create_generation_job(
    payload: CreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CreateResponse:
    handwriting = db.scalar(select(Handwriting).where(Handwriting.handwriting_id == payload.handwriting_id))
    if not handwriting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="handwriting not found")
    if handwriting.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your handwriting")

    font_file = db.scalar(select(FontFile).where(FontFile.font_file_id == payload.font_file_id))
    if not font_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="font file not found")

    job = GenerationJob(
        user_id=user_id,
        font_file_id=payload.font_file_id,
        handwriting_id=payload.handwriting_id,
        status="PENDING",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return CreateResponse(job_id=job.job_id, status=job.status)
