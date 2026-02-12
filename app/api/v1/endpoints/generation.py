from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import GenerationJob


router = APIRouter()


class GenerationStatusResponse(BaseModel):
    job_id: int
    status: str
    progress: int
    similarity_percent: float | None
    fail_reason: str | None


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
