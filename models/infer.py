"""
glyph_gan_infer.py
------------------
기존에 모델 학습한 체크포인트만 불러서 추론하는 단독 스크립트.
백엔드에서 import 하거나 직접 실행 모두 가능.

사용법 (직접 실행):
    python infer.py \
        --ckpt   ./checkpoints/epoch_0200.pt \
        --input  ./new_font_test/MyFont/input \
        --output ./new_font_test/MyFont/output \
        --nanum  ./NanumGothic.ttf
"""

import argparse
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as T
from PIL import Image, ImageDraw, ImageFont
import requests
from urllib.parse import urlparse
from io import BytesIO # 메모리에서 URL 처리

# ──────────────────────────────────────────────
# 고정 설정
# ──────────────────────────────────────────────
KOR_CHARS = list("가나더려모부쇼야져쵸켜튜프히")  # 14자
STYLE_DIM = 512
N_CHARS = 14
CHAR_EMB = 64
IMG_SIZE = 128
ENG_SAMPLE = 16
FONT_SIZE = 110

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ──────────────────────────────────────────────
# 모델 블록 정의  (학습 코드와 완전히 동일해야 함)
# ──────────────────────────────────────────────
class ConvBlock(nn.Module):
    def __init__(self, in_c, out_c, stride=1):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_c, out_c, 4, stride, 1, bias=False),
            nn.InstanceNorm2d(out_c),
            nn.LeakyReLU(0.2, inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class UpBlock(nn.Module):
    def __init__(self, in_c, out_c):
        super().__init__()
        self.block = nn.Sequential(
            nn.Upsample(scale_factor=2, mode="nearest"),
            nn.Conv2d(in_c, out_c, 3, 1, 1, bias=False),
            nn.InstanceNorm2d(out_c),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class AdaIN(nn.Module):
    def __init__(self, feat_dim, style_dim):
        super().__init__()
        self.norm = nn.InstanceNorm2d(feat_dim, affine=False)
        self.gamma = nn.Linear(style_dim, feat_dim)
        self.beta = nn.Linear(style_dim, feat_dim)

    def forward(self, x, s):
        g = self.gamma(s).unsqueeze(-1).unsqueeze(-1)
        b = self.beta(s).unsqueeze(-1).unsqueeze(-1)
        return g * self.norm(x) + b


class ResBlockAdaIN(nn.Module):
    def __init__(self, channels, style_dim):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, 1, 1, bias=False)
        self.conv2 = nn.Conv2d(channels, channels, 3, 1, 1, bias=False)
        self.adain1 = AdaIN(channels, style_dim)
        self.adain2 = AdaIN(channels, style_dim)

    def forward(self, x, s):
        r = F.relu(self.adain1(self.conv1(x), s))
        r = self.adain2(self.conv2(r), s)
        return F.relu(x + r)


class StyleEncoder(nn.Module):
    def __init__(self, style_dim=STYLE_DIM):
        super().__init__()
        self.encoder = nn.Sequential(
            ConvBlock(1, 64, stride=2),
            ConvBlock(64, 128, stride=2),
            ConvBlock(128, 256, stride=2),
            ConvBlock(256, 512, stride=2),
            ConvBlock(512, 512, stride=2),
            nn.AdaptiveAvgPool2d(1),
        )
        self.fc = nn.Linear(512, style_dim)

    def forward(self, imgs):
        B, N, C, H, W = imgs.shape
        x = imgs.view(B * N, C, H, W)
        x = self.encoder(x).view(B, N, 512)
        x = x.mean(dim=1)
        return self.fc(x)


class ContentEncoder(nn.Module):
    def __init__(self, n_chars=N_CHARS, char_emb_dim=CHAR_EMB):
        super().__init__()
        self.img_enc = nn.Sequential(
            ConvBlock(1, 64, stride=2),
            ConvBlock(64, 128, stride=2),
            ConvBlock(128, 192, stride=2),
        )
        self.char_emb = nn.Embedding(n_chars, char_emb_dim)
        self.proj = nn.Conv2d(192 + char_emb_dim, 256, 1)

    def forward(self, ref_img, char_idx):
        feat = self.img_enc(ref_img)
        emb = self.char_emb(char_idx)
        emb = emb.unsqueeze(-1).unsqueeze(-1)
        emb = emb.expand(-1, -1, feat.shape[2], feat.shape[3])
        return self.proj(torch.cat([feat, emb], dim=1))


class Generator(nn.Module):
    def __init__(self, style_dim=STYLE_DIM):
        super().__init__()
        self.res_blocks = nn.ModuleList([
            ResBlockAdaIN(256, style_dim) for _ in range(4)
        ])
        self.up1 = UpBlock(256, 128)
        self.up2 = UpBlock(128, 64)
        self.up3 = UpBlock(64, 32)
        self.final = nn.Sequential(nn.Conv2d(32, 1, 3, 1, 1), nn.Tanh())

    def forward(self, content, style):
        x = content
        for res in self.res_blocks:
            x = res(x, style)
        return self.final(self.up3(self.up2(self.up1(x))))


# ──────────────────────────────────────────────
# GlyphGAN: 모델 + 추론을 한 클래스로 묶음
# ──────────────────────────────────────────────
class GlyphGAN:
    """
    백엔드에서 쓸 때는 이 클래스만 import 하면 됨.

    예시:
        from infer import GlyphGAN
        gan = GlyphGAN("./checkpoints/epoch_0200.pt", "./NanumGothic.ttf")
        results = gan.generate(font_input_dir="./my_font/input")
        # results: {"가": PIL.Image, "나": PIL.Image, ...}
    """

    def __init__(self, ckpt_path: str, nanum_font_path: str):
        self.device = DEVICE
        self._build_models()
        self._load_ckpt(ckpt_path)
        self._build_ref_imgs(nanum_font_path)

        # 이미지 전처리 (학습 때와 동일)
        self.tfm = T.Compose([
            T.Resize((IMG_SIZE, IMG_SIZE)),
            T.ToTensor(),
            T.Normalize([0.5], [0.5]),
        ])
        print(f"[GlyphGAN] 준비 완료 (device={self.device})")

    # ── 내부 초기화 ──────────────────────────
    def _build_models(self):
        self.style_enc = StyleEncoder().to(self.device)
        self.content_enc = ContentEncoder().to(self.device)
        self.generator = Generator().to(self.device)

    def _load_ckpt(self, ckpt_path: str):
        ckpt = torch.load(ckpt_path, map_location=self.device)
        self.style_enc.load_state_dict(ckpt["style_enc"])
        self.content_enc.load_state_dict(ckpt["content_enc"])
        self.generator.load_state_dict(ckpt["generator"])
        self.style_enc.eval()
        self.content_enc.eval()
        self.generator.eval()
        print(f"[GlyphGAN] 체크포인트 로드: {ckpt_path}  (epoch {ckpt.get('epoch', '?')})")

    def _build_ref_imgs(self, nanum_font_path: str):
        """나눔고딕 참조 이미지를 미리 렌더링 (학습 때와 동일)"""
        tfm = T.Compose([T.Resize((128, 128)), T.ToTensor(), T.Normalize([0.5], [0.5])])
        font = ImageFont.truetype(str(nanum_font_path), size=FONT_SIZE)
        imgs = []
        for ch in KOR_CHARS:
            img = Image.new("L", (IMG_SIZE, IMG_SIZE), color=255)
            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), ch, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (IMG_SIZE - w) // 2 - bbox[0]
            y = (IMG_SIZE - h) // 2 - bbox[1]
            draw.text((x, y), ch, font=font, fill=0)
            imgs.append(tfm(img))
        self.ref_imgs = torch.stack(imgs).to(self.device)  # (14, 1, 128, 128)

    # ── 핵심 추론 메서드 ─────────────────────
    def generate(self, font_input_dir: str, n_sample: int = ENG_SAMPLE) -> dict:
        """
        영어 글리프 폴더 → 한글 14자 PIL 이미지 딕셔너리 반환

        Returns:
            {"가": PIL.Image, "나": PIL.Image, ...}
        """
        eng_files = list(Path(font_input_dir).glob("*.png"))
        if not eng_files:
            raise FileNotFoundError(f"영어 글리프 png 없음: {font_input_dir}")

        sampled = random.sample(eng_files, min(n_sample, len(eng_files)))
        eng_imgs = torch.stack([
            self.tfm(Image.open(f).convert("L")) for f in sampled
        ]).unsqueeze(0).to(self.device)  # (1, N, 1, 128, 128)

        results = {}
        with torch.no_grad():
            style = self.style_enc(eng_imgs)  # (1, style_dim)

            for i, ch in enumerate(KOR_CHARS):
                ref_img = self.ref_imgs[i].unsqueeze(0)  # (1, 1, 128, 128)
                char_idx = torch.tensor([i], device=self.device)
                content = self.content_enc(ref_img, char_idx)  # (1, 256, 16, 16)
                fake = self.generator(content, style)  # (1, 1, 128, 128)

                arr = ((fake[0, 0].cpu().numpy() + 1) * 127.5).clip(0, 255).astype(np.uint8)
                results[ch] = Image.fromarray(arr)

        return results

    def generate_and_save(self, font_input_dir: str, out_dir: str, n_sample: int = ENG_SAMPLE):
        """결과를 파일로도 저장하는 편의 메서드"""
        results = self.generate(font_input_dir, n_sample)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        for ch, img in results.items():
            img.save(Path(out_dir) / f"{ch}.png")
        print(f"[GlyphGAN] {len(results)}자 저장 완료 → {out_dir}")
        return results

    def generate_from_ttf(self, ttf_path: str, output_base_dir: str, font_size: int = 100):
        parsed = urlparse(ttf_path) # URL인지 로컬 경로인지 분석
        is_url = parsed.scheme in ("http", "https") # URL이면 True, 로컬이면 False

        if is_url:
            font_name = Path(parsed.path).stem # 파일명만 추출
            response = requests.get(ttf_path) # 인터넷에서 TTF 파일 다운로드
            response.raise_for_status() # 다운로드 실패
            font_data = BytesIO(response.content)  # 다운로드한 바이트 데이터를 메모리에 올림(디스크 저장 X)
        else:
            font_name = Path(ttf_path).stem
            font_data = ttf_path  # 로컬이면 경로 그대로

        print(f"폰트를 가져왔음")

        base_dir = Path(output_base_dir)

        input_dir = (
            base_dir
            / font_name
            / "input"
        )

        output_dir = (
            base_dir
            / font_name
            / "output"
        )

        print(f"input, output 폴더 가져옴")

        self._render_eng_glyphs(font_data, input_dir, font_size)
        print(f"_render_eng_glyphs 완료")
        results = self.generate_and_save(str(input_dir), str(output_dir))
        return results

    @staticmethod
    def _render_eng_glyphs(ttf_source, out_dir: str, font_size: int = 100):
        """ttf → 영어 A-Z, a-z 글리프 png 생성"""
        ENG_POOL = list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # BytesIO든 로컬 경로든 truetype()에 그냥 넘기면 됨
        font = ImageFont.truetype(ttf_source, size=font_size)  # 경로든 BytesIO든 둘 다 OK
        for ch in ENG_POOL:
            img = Image.new("L", (IMG_SIZE, IMG_SIZE), color=255)
            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), ch, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (IMG_SIZE - w) // 2 - bbox[0]
            y = (IMG_SIZE - h) // 2 - bbox[1]
            draw.text((x, y), ch, font=font, fill=0)
            fname = f"lower_{ch}.png" if ch.islower() else f"{ch}.png"
            img.save(out_dir / fname)

        print(f"[GlyphGAN] 영어 글리프 {len(ENG_POOL)}장 렌더링 완료 → {out_dir}")

    def generate_and_save(self, font_input_dir: str, out_dir: str, n_sample: int = ENG_SAMPLE):
        """결과를 파일로도 저장하는 편의 메서드"""
        results = self.generate(font_input_dir, n_sample)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        for ch, img in results.items():
            img.save(Path(out_dir) / f"{ch}.png")
        print(f"[GlyphGAN] {len(results)}자 저장 완료 → {out_dir}")
        return results


# ──────────────────────────────────────────────
# 직접 실행할 때 (python infer.py --ckpt ...)
# ──────────────────────────────────────────────
# if __name__ == "__main__":
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--ckpt",   required=True, help="체크포인트 .pt 경로")
#     parser.add_argument("--ttf",    help="입력 폰트 .ttf 경로 (--input 대신 사용 가능)")
#     parser.add_argument("--input",  help="영어 글리프 png 폴더 (--ttf 대신 사용 가능)")
#     parser.add_argument("--output", required=True, help="결과 저장 폴더")
#     parser.add_argument("--nanum",  default="./NanumGothic.ttf", help="나눔고딕 .ttf 경로")
#     args = parser.parse_args()
#
#     if not args.ttf and not args.input:
#         parser.error("--ttf 또는 --input 중 하나는 반드시 필요합니다")
#
#     gan = GlyphGAN(args.ckpt, args.nanum)
#
#     if args.ttf:
#         gan.generate_from_ttf(args.ttf, args.output)
#     else:
#         gan.generate_and_save(args.input, args.output)

if __name__ == "__main__":
    import tkinter as tk
    from tkinter import filedialog

    # ── 체크포인트 경로 (고정)
    BASE_DIR = Path(__file__).parent  # infer.py가 있는 폴더 기준으로 고정
    CKPT_PATH = str(BASE_DIR / "checkpoints/epoch_0200.pt")
    NANUM_PATH = str(BASE_DIR / "NanumGothic.ttf")

    # # ── TTF 파일 선택 다이얼로그
    # root = tk.Tk()
    # root.withdraw()  # 메인 창 숨기기
    # ttf_path = filedialog.askopenfilename(
    #     title="변환할 폰트 TTF 파일 선택",
    #     filetypes=[("폰트 파일", "*.ttf *.otf"), ("모든 파일", "*.*")]
    # )
    #
    # if not ttf_path:
    #     print("파일 선택 취소")
    #     exit()

    # 테스트할 TTF URL 직접 입력
    ttf_url = "https://fontify-986995923828-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com/english_only_google_fonts/abeezee/ABeeZee-Italic.ttf"

    # ── 결과 저장 폴더 = ttf 파일명과 같은 이름으로 자동 생성
    font_name = Path(ttf_url).stem
    out_dir = f"./output_{font_name}"

    print(f"선택된 폰트: {ttf_url}")
    print(f"결과 저장 위치: {out_dir}")

    gan = GlyphGAN(CKPT_PATH, NANUM_PATH)
    gan.generate_from_ttf(ttf_url)