from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

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

        ttf_path = _resolve_font_path(font_file.file_path)
        with _gan_run_lock:
            _get_gan().generate_from_ttf(str(ttf_path), output_base_dir=str(OUTPUT_BASE_DIR))

        output_dir = OUTPUT_BASE_DIR / Path(ttf_path).stem / "output"
    except Exception as exc:
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
