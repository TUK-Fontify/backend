from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig")

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
