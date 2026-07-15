# app/utils/s3.py (또는 프로젝트 구조에 맞는 위치)
import boto3
from app.core.config import settings

_s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


def upload_font_to_s3(job_id: int, file_bytes: bytes) -> str:
    key = f"generated_fonts/{job_id}/generated.ttf"

    _s3_client.put_object(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Body=file_bytes,
        ContentType="font/ttf",
    )

    file_url = (
        f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    )
    return file_url