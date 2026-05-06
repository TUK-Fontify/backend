from datetime import datetime

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import FontFile, GenerationJob, Handwriting
from app.services.google_generation import run_google_generation_job


router = APIRouter()


class GenerationJobResponse(BaseModel):
    job_id: int
    status: str
    requested_at: datetime


class GoogleGenerationRequest(BaseModel):
    font_file_id: int


class HandwritingGenerationRequest(BaseModel):
    handwriting_id: int


class GenerationStatusResponse(BaseModel):
    job_id: int
    status: str
    progress: int
    similarity_percent: float | None
    fail_reason: str | None


@router.post("/google", response_model=GenerationJobResponse)
def create_google_generation(
    payload: GoogleGenerationRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GenerationJobResponse:
    font_file = db.scalar(select(FontFile).where(FontFile.font_file_id == payload.font_file_id))
    if not font_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="font file not found")

    job = GenerationJob(user_id=user_id, font_file_id=payload.font_file_id, status="PENDING", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_google_generation_job, job.job_id)
    return GenerationJobResponse(job_id=job.job_id, status=job.status, requested_at=job.requested_at)


@router.post("/handwriting", response_model=GenerationJobResponse)
def create_handwriting_generation(
    payload: HandwritingGenerationRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GenerationJobResponse:
    handwriting = db.scalar(select(Handwriting).where(Handwriting.handwriting_id == payload.handwriting_id))
    if not handwriting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="handwriting not found")
    if handwriting.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your handwriting")

    job = GenerationJob(user_id=user_id, handwriting_id=payload.handwriting_id, status="PENDING", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    return GenerationJobResponse(job_id=job.job_id, status=job.status, requested_at=job.requested_at)


@router.get("/{job_id}", response_model=GenerationStatusResponse)
def get_generation_status(
    job_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GenerationStatusResponse:
    job = db.scalar(select(GenerationJob).where(GenerationJob.job_id == job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your job")

    similarity = float(job.similarity_percent) if job.similarity_percent is not None else None
    return GenerationStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        similarity_percent=similarity,
        fail_reason=job.fail_reason,
    )
