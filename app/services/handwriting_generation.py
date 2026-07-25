from datetime import UTC, datetime
import importlib.util
import mimetypes
from pathlib import Path
import shutil
from threading import Lock
from urllib.error import HTTPError, URLError
import urllib.request 
import time, json

from sqlalchemy.orm import Session
from app.utils.s3 import upload_font_to_s3

# 2. FastAPI의 Request는 그대로 가져옵니다. 
# 이제 이 파일 안에서 'Request'는 오직 FastAPI 것뿐입니다.
from fastapi import Request, HTTPException, Depends, status
from uuid import uuid4
import time

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import FontFile, GeneratedFont, GenerationJob, Handwriting


BACKEND_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BACKEND_DIR / "models"
CKPT_PATH = MODEL_DIR / "checkpoints" / "epoch_0200.pt"
NANUM_PATH = MODEL_DIR / "NanumGothic.ttf"
JOB_OUTPUT_DIR = BACKEND_DIR / "static" / "generation_jobs"
LOCAL_MXFONT_DIR = MODEL_DIR / "mxfont"
LOCAL_MXFONT_CHARS_JSON = LOCAL_MXFONT_DIR / "data" / "hangul_2350.json"
LOCAL_MXFONT_GENERATOR = LOCAL_MXFONT_DIR / "generator.pth"

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


def _resolve_backend_path(file_path: str) -> Path:
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
    raise FileNotFoundError(f"file not found: {file_path}")


def _static_url(path: Path) -> str:
    return "/" + path.resolve().relative_to(BACKEND_DIR / "static").as_posix()


def list_preview_urls(job_id: int) -> list[str]:
    preview_dir = JOB_OUTPUT_DIR / str(job_id) / "preview"
    if not preview_dir.exists():
        return []
    return [_static_url(path) for path in sorted(preview_dir.glob("*.png"))]


def _save_preview_images(ttf_path: Path, preview_dir: Path) -> list[Path]:
    print(
      "[GAN]",
      ttf_path,
      "lock 대기"
    )
    
    preview_dir.mkdir(parents=True, exist_ok=True)
    with _gan_run_lock:
        print(
          "[GAN]",
          ttf_path,
          "lock 획득"
        )
        
        _get_gan().generate_from_ttf(str(ttf_path), output_base_dir=str(preview_dir.parent))

        print(
          "[GAN]",
          ttf_path,
          "generation 완료"
        )

    output_dir = preview_dir.parent / Path(ttf_path).stem / "output"
    if not output_dir.exists():
        raise FileNotFoundError(f"infer output not found: {output_dir}")

    saved_paths = []
    for image_path in sorted(output_dir.glob("*.png")):
        target = preview_dir / image_path.name
        target.write_bytes(image_path.read_bytes())
        saved_paths.append(target)
    return saved_paths


def _multipart_body(
    files: list[Path],
    field_name: str,
    job_id: str,
) -> tuple[bytes, str]:
    print('multipart body 시작')
    boundary = f"----font-boundary-{uuid4().hex}"
    chunks: list[bytes] = []

    # job_id를 일반 텍스트 form field로 추가
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="job_id"\r\n\r\n',
            job_id.encode(),
            b"\r\n",
        ]
    )

    for path in files:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{field_name}"; '
                    f'filename="{path.name}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                path.read_bytes(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    print('multipart body 끝')
    return b"".join(chunks), boundary


def _create_mxfont_job(endpoint: str, preview_paths: list[Path], field_name: str, job_id: str) -> str:
    print('_create_mxfont_job 시작')
    job_id = str(job_id)
    body, boundary = _multipart_body(preview_paths, field_name, job_id)
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "ngrok-skip-browser-warning": "true",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read())

    returned_job_id = data.get("job_id")
    if str(returned_job_id) != str(job_id):
        print(f"경고: job_id 불일치 (요청: {job_id}, 응답: {returned_job_id})")

    print("mxfont job 생성됨:", job_id)
    return job_id


def _poll_mxfont_status(base_url: str, job_id: str, interval: int = 5, max_wait: int = 60 * 20) -> None:
    elapsed = 0
    while elapsed < max_wait:
        request = urllib.request.Request(
            f"{base_url}/status/{job_id}",
            headers={"ngrok-skip-browser-warning": "true"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read())

        print(f"mxfont job {job_id} 상태:", data["status"])

        if data["status"] == "done":
            return
        if data["status"] == "error":
            raise RuntimeError(data.get("error", "unknown mxfont error"))

        time.sleep(interval)
        elapsed += interval

    raise TimeoutError(f"mxfont job {job_id} timed out after {max_wait}s")


def _fetch_mxfont_result(base_url: str, job_id: str) -> tuple[str, bytes]:
    request = urllib.request.Request(
        f"{base_url}/result/{job_id}",
        headers={"ngrok-skip-browser-warning": "true"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        content_type = response.headers.get("Content-Type", "")
        content = response.read()

    print("mxfont 결과 수신:", content_type, len(content), "bytes")
    return content_type, content

def _request_mxfont(db: Session, job_id: str, preview_paths: list[Path], output_ttf: Path) -> bool:
    print('request_mxfont 시작')

    job_id = str(job_id)
    if not settings.MXFONT_API_URL:
        return False

    base_url = settings.MXFONT_API_URL.rstrip("/")
    endpoint = base_url + "/" + settings.MXFONT_API_PATH.lstrip("/")
    field_name = settings.mxfont_api_file_field

    try:
        print('mxfont job 생성 요청 보내겠습니다.')
        job_id = _create_mxfont_job(endpoint, preview_paths, field_name, job_id)
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        if exc.code == 422 and '"file"' in message and field_name != "file":
            try:
                job_id = _create_mxfont_job(endpoint, preview_paths, "file", job_id)
            except HTTPError as retry_exc:
                retry_message = retry_exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"mxfont api failed: {retry_exc.code} {endpoint} {retry_message}"
                ) from retry_exc
        else:
            raise RuntimeError(f"mxfont api failed: {exc.code} {endpoint} {message}") from exc
    except URLError as exc:
        raise RuntimeError(f"mxfont api unavailable: {exc}") from exc

    _poll_mxfont_status(base_url, job_id)
    content_type, content = _fetch_mxfont_result(base_url, job_id)

    if "text/html" in content_type.lower() or content.lstrip().lower().startswith(b"<!doctype html"):
        raise RuntimeError("mxfont api returned HTML instead of a font file")
    if not content:
        raise RuntimeError("mxfont api returned an empty response")

    output_ttf.write_bytes(content)

    # ↓ 여기서 S3 업로드 + DB 저장
    file_url = upload_font_to_s3(int(job_id), content)

    generated_font = GeneratedFont(
        file_url=file_url,
        job_id=int(job_id),
    )
    db.add(generated_font)
    db.commit()
    db.refresh(generated_font)

    return True



def _has_imagemagick() -> bool:
    magick = shutil.which("magick")
    if magick:
        return True

    convert = shutil.which("convert")
    if not convert:
        return False

    return "system32" not in convert.lower()


def _ensure_local_mxfont_dependencies() -> None:
    missing = []
    if importlib.util.find_spec("fontforge") is None:
        missing.append("fontforge")
    if importlib.util.find_spec("psMat") is None:
        missing.append("psMat")
    if shutil.which("potrace") is None:
        missing.append("potrace")
    if not _has_imagemagick():
        missing.append("imagemagick")
    if missing:
        raise RuntimeError(
            "local mxfont dependencies are missing: "
            + ", ".join(missing)
            + ". Install them or set MXFONT_API_URL."
        )


def _run_only_handwriting_mxfont(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.scalar(select(GenerationJob).where(GenerationJob.job_id == job_id))
        if not job:
            return
        job.status = "HANDWRITING_READY"
        job.progress = 50
        db.commit()
        print(f"[JOB {job.job_id}] MXFont 시작, {settings.MXFONT_API_URL}")

        job_dir = JOB_OUTPUT_DIR / str(job.job_id)
        output_ttf = job_dir / "CEHandKRFinal.ttf"

        handwriting = db.scalar(
        select(Handwriting).where(
            Handwriting.handwriting_id == job.handwriting_id
        )
        )

        if not handwriting:
            raise Exception("Handwriting not found")

        upload_path = Path(handwriting.image_url.lstrip("/"))

        if settings.MXFONT_API_URL:
            _request_mxfont(db, job_id, upload_path, output_ttf)
    
        print('request_mxfont 완료')
        
        generated_font = GeneratedFont(
            job_id=job.job_id,
            name=f"USER HAND FONT Generated",
            file_url=_static_url(output_ttf),
        )
        db.add(generated_font)
        job.status = "COMPLETED"
        job.progress = 100
        job.finished_at = _now()
        db.commit()
        
        print(f"[JOB {job.job_id}] MXFont 완료")
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


def run_handwriting_generation_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.scalar(select(GenerationJob).where(GenerationJob.job_id == job_id))
        if not job:
            return

        if job.font_file_id is None:
            handwriting = db.scalar(select(Handwriting).where(Handwriting.handwriting_id == job.handwriting_id))
            if not handwriting:
                job.status = "FAILED"
                job.progress = 100
                job.fail_reason = "handwriting not found"
                job.finished_at = _now()
                db.commit()
                return

            job.status = "FAILED"
            job.progress = 100
            job.fail_reason = "handwriting-only generation model is not implemented"
            job.finished_at = _now()
            db.commit()
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

        ttf_path = font_file.file_path

        print(f"[GAN] {ttf_path} generation service")

        job_dir = JOB_OUTPUT_DIR / str(job.job_id)
        preview_paths = _save_preview_images(ttf_path, job_dir / "preview")
        print(f"[JOB {job.job_id}] GAN preview generation 완료, {len(preview_paths)}장 생성")

        job.status = "PREVIEW_READY"
        job.progress = 50
        db.commit()

        print(f"[JOB {job.job_id}] MXFont 시작, {settings.MXFONT_API_URL}")

        output_ttf = job_dir / "CEHandKRFinal.ttf"
        if settings.MXFONT_API_URL:
            _request_mxfont(db, job_id, preview_paths, output_ttf)

        print('request_mxfont 완료')

        generated_font = GeneratedFont(
            job_id=job.job_id,
            name=f"{font_file.font_family.name} Generated",
            file_url=_static_url(output_ttf),
        )
        db.add(generated_font)
        job.status = "COMPLETED"
        job.progress = 100
        job.finished_at = _now()
        db.commit()

        print(f"[JOB {job.job_id}] MXFont 완료")
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