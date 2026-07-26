from datetime import datetime
from pathlib import Path

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user_id
from app.db.session import get_db
from app.models import GenerationJob, Handwriting
from app.services.handwriting_generation import run_handwriting_generation_job

import shutil


router = APIRouter()
UPLOAD_DIR = Path("uploads")


class UploadResponse(BaseModel):
    handwriting_id: int
    image_url: str


class CreateRequest(BaseModel):
    handwriting_id: int


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

    # upload 폴더 내부 파일 삭제
    for file in UPLOAD_DIR.iterdir():
        if file.is_file():
            file.unlink()
        elif file.is_dir():
            shutil.rmtree(file)

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
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CreateResponse:
    handwriting = db.scalar(select(Handwriting).where(Handwriting.handwriting_id == payload.handwriting_id))
    if not handwriting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="handwriting not found")
    if handwriting.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your handwriting")

    job = GenerationJob(
        user_id=user_id,
        handwriting_id=payload.handwriting_id,
        status="PENDING",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_handwriting_generation_job, job.job_id)
    return CreateResponse(job_id=job.job_id, status=job.status)
