from datetime import datetime, timezone

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from urllib.error import HTTPError
from app.core.config import settings
import urllib.request
from pathlib import Path

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import FontFile, GeneratedFont, GenerationJob, Handwriting
from app.services.handwriting_generation import list_preview_urls, run_handwriting_generation_job, _run_only_handwriting_mxfont

JOB_OUTPUT_DIR = Path("backend/models/outputs")

router = APIRouter()

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _static_url(path: Path) -> str:
    relative_path = path.resolve().relative_to(Path(__file__).resolve().parents[2])
    return "/" + relative_path.as_posix()


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
    handwriting_id: int | None
    status: str
    progress: int
    similarity_percent: float | None
    fail_reason: str | None
    preview_image_urls: list[str]
    generated_font_id: int | None
    generated_font_url: str | None
    total_job_count: int

class GeneratedFontItem(BaseModel):
    generated_font_id: int
    file_url: str


class GeneratedFontDetail(BaseModel):
    generated_font_id: int
    file_url: str


class DownloadResponse(BaseModel):
    file_url: str


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

    background_tasks.add_task(_run_only_handwriting_mxfont, job.job_id)
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

    total_job_count = db.scalar(
    select(func.count())
    .select_from(GenerationJob)
    .where(GenerationJob.user_id == user_id)
)

    return GenerationStatusResponse(
        job_id=job.job_id,
        handwriting_id=job.handwriting_id if job.handwriting_id is not None else None,
        status=job.status,
        progress=job.progress,
        similarity_percent=similarity,
        fail_reason=job.fail_reason,
        preview_image_urls=[url for url in preview_image_urls if url is not None],
        generated_font_id=generated_font.generated_font_id if generated_font else None,
        generated_font_url=_absolute_url(request, generated_font.file_url) if generated_font else None,
        total_job_count=total_job_count,
    )

@router.post("/jobs/{job_id}/download", response_model=DownloadResponse)
def download_generated_font(
    job_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DownloadResponse:
    
    # 1. 작업(Job) 내역 조회
    job = db.scalar(select(GenerationJob).where(GenerationJob.job_id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="해당 작업을 찾을 수 없습니다.")

    # 2. 이미 다운로드해서 DB에 폰트가 저장되어 있는 경우 (빠른 리턴)
    if job.status == "COMPLETED":
        font = db.scalar(select(GeneratedFont).where(GeneratedFont.job_id == job_id))

    # 3. 아직 백엔드에 폰트가 없다면? ➔ Colab(ngrok)에 파일이 다 만들어졌는지 확인하러 감!
    ngrok_url = settings.MXFONT_API_URL.rstrip("/")
    download_url = f"{ngrok_url}/download"
    
    try:
        req = urllib.request.Request(download_url, headers={"ngrok-skip-browser-warning": "true"})
        # 10초만 기다려보고 응답 없으면 빠져나옴 (타임아웃 방지)
        with urllib.request.urlopen(req, timeout=10) as res:
            content = res.read()
            
            # --- [여기부터는 Colab에서 파일을 성공적으로 받아온 상황] ---
            # 받아온 폰트(content)를 백엔드 서버 경로에 저장
            #job_dir = JOB_OUTPUT_DIR / str(job.job_id)
            #job_dir.mkdir(parents=True, exist_ok=True) # 폴더 없으면 생성
            #output_ttf = job_dir / "CEHandKRFinal.ttf"
            #output_ttf.write_bytes(content)

            generated_font = GeneratedFont(
                job_id=job.job_id,
                file_url=db.scalar(select(FontFile).where(FontFile.font_file_id == job.font_file_id))
            )

            return DownloadResponse(file_url=generated_font.file_url)

    except HTTPError as e:
        # Colab에서 우리가 설정해 둔 404(아직 생성 안 됨) 에러를 뱉었을 때
        if e.code == 404:
            raise HTTPException(
                status_code=400, 
                detail="폰트가 아직 제작 중입니다. 15분 뒤에 다시 시도해주세요."
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Colab 통신 에러 발생: {e.code}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail="폰트 다운로드 중 알 수 없는 에러가 발생했습니다.")