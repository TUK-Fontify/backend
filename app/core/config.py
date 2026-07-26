from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = "Font Backend"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "font"
    DATABASE_URL: str | None = None
    DEV_BYPASS_AUTH: bool = False
    DEV_USER_ID: str = "dev-user-001"
    MXFONT_API_URL: str | None = None
    MXFONT_API_PATH: str = "/generate"
    MXFONT_API_FILE_FIELD: str = "files"
    MXFONT_API_FILES_FIELD: str | None = None

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "ap-northeast-2"
    AWS_S3_BUCKET: str

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8-sig")

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def mxfont_api_file_field(self) -> str:
        return self.MXFONT_API_FILES_FIELD or self.MXFONT_API_FILE_FIELD


settings = Settings()
