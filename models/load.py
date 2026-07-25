import torch
import clip

# 모델 로드 (서버 시작 시 1회만 실행)
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
model.eval()