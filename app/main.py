from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    return {"message": "FastAPI server is running"}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
