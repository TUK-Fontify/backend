from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
import requests
import tempfile
from urllib.parse import urlparse

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import FontFile, GeneratedFont, GenerationJob


BACKEND_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BACKEND_DIR / "models"
CKPT_PATH = MODEL_DIR / "checkpoints" / "epoch_0200.pt"
NANUM_PATH = MODEL_DIR / "NanumGothic.ttf"
OUTPUT_BASE_DIR = BACKEND_DIR / "new_font_test"

_gan = None
_gan_init_lock = Lock()
_gan_run_lock = Lock()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _get_gan():
    global _gan
    if _gan is None:
        with _gan_init_lock:
            if _gan is None:
                from models.infer import GlyphGAN

                _gan = GlyphGAN(str(CKPT_PATH), str(NANUM_PATH))
    return _gan


def _resolve_font_path(file_path: str) -> Path:
    normalized = file_path.lstrip("/").replace("\\", "/")
    if normalized.startswith("fonts/"):
        normalized = f"static/{normalized}"

    path = Path(normalized)
    candidates = [
        path,
        BACKEND_DIR / path,
        BACKEND_DIR.parent / path,
        BACKEND_DIR.parent / "backend" / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"font file not found: {file_path}")


def _relative_to_backend(path: Path) -> str:
    try:
        return path.resolve().relative_to(BACKEND_DIR).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def run_google_generation_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.scalar(select(GenerationJob).where(GenerationJob.job_id == job_id))
        if not job:
            return

        font_file = db.scalar(select(FontFile).where(FontFile.font_file_id == job.font_file_id))
        if not font_file:
            job.status = "FAILED"
            job.progress = 100
            job.fail_reason = "font file not found"
            job.finished_at = _now()
            db.commit()
            return

        job.status = "RUNNING"
        job.progress = 10
        job.fail_reason = None
        db.commit()


        ttf_url = font_file.file_path
        print("ttf_url =", ttf_url)


        # S3에서 ttf 다운로드
        response = requests.get(ttf_url)
        response.raise_for_status()


        # 임시 ttf 파일 저장
        with tempfile.NamedTemporaryFile(
            suffix=".ttf",
            delete=False
        ) as tmp:

            tmp.write(response.content)
            temp_ttf = Path(tmp.name)


        print("temp_ttf =", temp_ttf)


        with _gan_run_lock:
            _get_gan().generate_from_ttf(
                str(temp_ttf),
                output_base_dir=str(OUTPUT_BASE_DIR)
            )


        # 원래 파일명 추출
        font_name = Path(
            urlparse(ttf_url).path
        ).stem


        output_dir = (
            OUTPUT_BASE_DIR
            / font_name
            / "output"
        )

        print("output_dir =", output_dir)

        """
        ttf_path = font_file.file_path
        print("ttf_path =", ttf_path)
        with _gan_run_lock:
            _get_gan().generate_from_ttf(str(ttf_path), output_base_dir=str(OUTPUT_BASE_DIR))

        output_dir = OUTPUT_BASE_DIR / ttf_path.stem / "output"
        """
        generated_font = GeneratedFont(
            job_id=job.job_id,
            name=f"{font_file.font_family.name} Generated",
            file_url=_relative_to_backend(output_dir),
        )
        db.add(generated_font)

        job.status = "COMPLETED"
        job.progress = 100
        job.finished_at = _now()
        db.commit()
    except Exception as exc:
        print(exc)
        db.rollback()
        job = db.scalar(select(GenerationJob).where(GenerationJob.job_id == job_id))
        if job:
            job.status = "FAILED"
            job.progress = 100
            job.fail_reason = str(exc)[:255]
            job.finished_at = _now()
            db.commit()
    finally:
        db.close()
