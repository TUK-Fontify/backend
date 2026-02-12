from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    return {"message": "FastAPI server is running"}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
