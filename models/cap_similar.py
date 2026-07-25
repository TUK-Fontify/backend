"""
font_recommender.py
-------------------
캡쳐 -> 폰트 추천 모듈

필요한 파일:
    - clip_embeddings.h5   : CLIP 임베딩 결과
    - font_index.faiss     : faiss 인덱스

필요한 라이브러리 설치: (외부 모델 사용이라서 꼭 라이브러리 설치해주기)
    pip install torch torchvision
    pip install git+https://github.com/openai/CLIP.git
    pip install faiss-cpu
    pip install h5py
    pip install Pillow
    pip install numpy
"""

import torch
import clip
import numpy as np
import h5py
import faiss
import base64
import io
import tempfile
import urllib.request
from PIL import Image


# 모델 로드 (서버 시작 시 1회만 실행)
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
model.eval()


def _resolve_s3_path(path: str) -> str:
    """emb_path/index_path가 "http(s)://..." 형태의 S3 URL이면 로컬 임시파일로 1회 다운로드해
    그 경로를 반환 (버킷/객체가 퍼블릭이거나 프리사인드 URL이라 자격증명 불필요).
    로컬 경로면 그대로 반환 (기존 동작 유지)."""
    if not path.startswith("http://") and not path.startswith("https://"):
        return path

    suffix = "." + path.split("?")[0].rsplit(".", 1)[-1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    urllib.request.urlretrieve(path, tmp.name)
    return tmp.name


class FontRecommender:
    def __init__(self, emb_path: str, index_path: str):
        # emb_path/index_path가 S3 경로면 서버 시작 시 1회만 로컬로 캐싱
        emb_path = _resolve_s3_path(emb_path)
        index_path = _resolve_s3_path(index_path)

        # 임베딩 + 폰트명 로드
        with h5py.File(emb_path, "r") as hf:
            self.embeddings = hf["embeddings"][:]
            self.font_names = [
                n.decode() for n in hf["font_names"][:]
            ]
        self.index = faiss.read_index(index_path)

    def recommend(self, image_input, top_k: int = 10):
        """
        image_input: 이미지 경로(str) 또는 PIL.Image 또는 base64 문자열
        반환:
        [
            {"rank": 1, "font": "gwendolyn/Gwendolyn-Bold", "similarity": 68.03},
            {"rank": 2, "font": "imperialscript/ImperialScript-Regular", "similarity": 67.84},
            ...
        ]
        """
        # 이미지 로드 # 받은 이미지 이름에 대한 처리
        if isinstance(image_input, str):
            if image_input.startswith("data:image"):
                # base64 이미지
                base64_data = image_input.split(",")[1]
                img = Image.open(io.BytesIO(base64.b64decode(base64_data))).convert("RGB")
            else:
                # 파일 경로
                img = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, Image.Image):
            img = image_input.convert("RGB")
        else:
            raise ValueError("image_input은 경로(str), base64(str), PIL.Image 중 하나")

        # CLIP 임베딩
        with torch.no_grad():
            tensor = preprocess(img).unsqueeze(0).to(device)
            query_vec = model.encode_image(tensor)
            query_vec = query_vec / query_vec.norm(dim=-1, keepdim=True)

        query_np = query_vec.cpu().numpy().astype(np.float32)
        scores, indices = self.index.search(query_np, top_k)

        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), 1):
            results.append({
                "rank": rank,
                "font": self.font_names[idx],
                "similarity": round(float(score) * 100, 2)
            })

        return results


# 사용 예시
if __name__ == "__main__":
    recommender = FontRecommender(
        emb_path="https://fontify-986995923828-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com/clip_embeddings.h5",
        index_path="https://fontify-986995923828-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com/font_index.faiss"
    )

    results = recommender.recommend("2.png", top_k=10) # 여기에 이미지 이름 들어감 # 유사 10개 추천
    for r in results:
        print(f"{r['rank']:2d}. {r['font']:<40s} 유사도: {r['similarity']:.2f}%")