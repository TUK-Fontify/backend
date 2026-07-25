from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.fonts import generated_fonts_router, router as fonts_router
from app.api.v1.endpoints.generation import router as generation_router
from app.api.v1.endpoints.handwriting import router as handwriting_router
from app.api.v1.endpoints.users_me import router as users_me_router
from app.api.v1.endpoints.recommend import router as recommend_router


api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_me_router, prefix="/users", tags=["users"])
api_router.include_router(handwriting_router, prefix="/handwriting", tags=["handwriting"])
api_router.include_router(generation_router, prefix="/generations", tags=["generations"])
api_router.include_router(fonts_router, prefix="/fonts", tags=["fonts"])
api_router.include_router(generated_fonts_router, prefix="/generated_fonts", tags=["generated_fonts"])
api_router.include_router(recommend_router, tags=["recommend"])
