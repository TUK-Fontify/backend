import io

from fastapi import APIRouter, File, UploadFile
from PIL import Image

from models.cap_similar import FontRecommender

router = APIRouter()

recommender = FontRecommender(
    emb_path="https://fontify-986995923828-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com/clip_embeddings.h5",
    index_path="https://fontify-986995923828-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com/font_index.faiss",
)


@router.post("/recommend")
async def recommend_font(image: UploadFile = File(...)):
    content = await image.read()
    img = Image.open(io.BytesIO(content)).convert("RGB")

    results = recommender.recommend(img, top_k=10)

    return results