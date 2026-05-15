from datetime import datetime

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import FontFile, GeneratedFont, GenerationJob, Handwriting
from app.services.handwriting_generation import list_preview_urls, run_handwriting_generation_job


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
    preview_image_urls: list[str]
    generated_font_id: int | None
    generated_font_url: str | None


def _absolute_url(request: Request, path: str | None) -> str | None:
    if path is None:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return str(request.base_url).rstrip("/") + "/" + path.lstrip("/")


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

    job = GenerationJob(user_id=user_id, font_file_id=payload.font_file_id, status="GOOGLEPENDING", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_handwriting_generation_job, job.job_id)
    return GenerationJobResponse(job_id=job.job_id, status=job.status, requested_at=job.requested_at)


@router.post("/handwriting", response_model=GenerationJobResponse)
def create_handwriting_generation(
    payload: HandwritingGenerationRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GenerationJobResponse:
    
    print(
        f"[REQUEST] handwriting "
        f"user={user_id} "
        f"handwriting_id="
        f"{payload.handwriting_id}"
    )

    handwriting = db.scalar(select(Handwriting).where(Handwriting.handwriting_id == payload.handwriting_id))
    if not handwriting:
        print(
          "[ERROR] "
          "handwriting not found"
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="handwriting not found")
    if handwriting.user_id != user_id:
        print(
           "[ERROR] "
           "not your handwriting"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your handwriting")

    job = GenerationJob(
        user_id=user_id,
        handwriting_id=payload.handwriting_id,
        status="HANDWRITINGPENDING",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    print(
        f"[JOB CREATED] "
        f"job_id={job.job_id} "
        f"status={job.status}"
    )

    background_tasks.add_task(run_handwriting_generation_job, job.job_id)
    return GenerationJobResponse(job_id=job.job_id, status=job.status, requested_at=job.requested_at)


@router.get("/{job_id}", response_model=GenerationStatusResponse)
def get_generation_status(
    job_id: int,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GenerationStatusResponse:
    job = db.scalar(select(GenerationJob).where(GenerationJob.job_id == job_id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your job")

    generated_font = db.scalar(select(GeneratedFont).where(GeneratedFont.job_id == job.job_id))
    preview_image_urls = [_absolute_url(request, path) for path in list_preview_urls(job.job_id)]
    similarity = float(job.similarity_percent) if job.similarity_percent is not None else None
    return GenerationStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        similarity_percent=similarity,
        fail_reason=job.fail_reason,
        preview_image_urls=[url for url in preview_image_urls if url is not None],
        generated_font_id=generated_font.generated_font_id if generated_font else None,
        generated_font_url=_absolute_url(request, generated_font.file_url) if generated_font else None,
    )
