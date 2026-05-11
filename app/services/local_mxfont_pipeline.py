import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unicodedata

import cv2
from fontTools.ttLib import TTFont


TARGET_SCALE = 1.55
TARGET_WIDTH_RATIO = 1.25


def _preprocess(folder: Path) -> None:
    for path in sorted(folder.glob("*.png")):
        img = cv2.imread(str(path))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(blur, 200, 255, cv2.THRESH_BINARY)
        cv2.imwrite(str(path), binary)

    for name in os.listdir(folder):
        normalized = unicodedata.normalize("NFC", name)
        if name != normalized:
            os.rename(folder / name, folder / normalized)


def _run_mxfont(
    input_dir: Path,
    work_dir: Path,
    mxfont_dir: Path,
    base_ttf: Path,
    chars_json: Path,
    generator_pth: Path,
) -> Path:
    font_dir = work_dir / "mxfont_input" / "myfont"
    font_dir.mkdir(parents=True)
    for path in input_dir.iterdir():
        if path.suffix.lower() == ".png":
            shutil.copy2(path, font_dir / path.name)

    result_dir = work_dir / "mxfont_results"
    result_dir.mkdir()

    eval_yaml = work_dir / "eval.yaml"
    eval_yaml.write_text(
        f"""
dset:
  test:
    data_dir: {font_dir.parent}
    source_font: {base_ttf}
    gen_chars_file: {chars_json}
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(mxfont_dir / "eval.py"),
            str(eval_yaml),
            "--weight",
            str(generator_pth),
            "--result_dir",
            str(result_dir),
            "--batch_size",
            "1",
            "--device",
            "cpu",
        ],
        capture_output=True,
        cwd=str(mxfont_dir),
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"mxfont eval failed: {result.stderr[-2000:]}")

    png_dir = result_dir / "myfont"
    if not png_dir.exists():
        raise RuntimeError(f"mxfont output not found: {png_dir}")
    return png_dir


def _imagemagick_command() -> list[str]:
    magick = shutil.which("magick")
    if magick:
        return [magick]

    convert = os.getenv("IMAGEMAGICK_CONVERT") or shutil.which("convert")
    if convert and "system32" not in convert.lower():
        return [convert]

    raise RuntimeError("ImageMagick is required. Install it or set IMAGEMAGICK_CONVERT.")


def _vectorize(png_dir: Path, work_dir: Path) -> Path:
    svg_dir = work_dir / "svg"
    pbm_dir = work_dir / "pbm"
    svg_dir.mkdir()
    pbm_dir.mkdir()
    imagemagick = _imagemagick_command()

    potrace = shutil.which("potrace")
    if not potrace:
        raise RuntimeError("potrace is required.")

    for png_path in sorted(png_dir.glob("*.png")):
        pbm_path = pbm_dir / f"{png_path.stem}.pbm"
        svg_path = svg_dir / f"{png_path.stem}.svg"
        subprocess.run(
            [
                *imagemagick,
                str(png_path),
                "-threshold",
                "70%",
                "-background",
                "white",
                "-alpha",
                "remove",
                str(pbm_path),
            ],
            check=True,
        )
        subprocess.run([potrace, str(pbm_path), "-s", "-o", str(svg_path)], check=True)

    return svg_dir


def _build_ttf(svg_dir: Path, base_ttf: Path, output_ttf: Path) -> None:
    import fontforge
    import psMat

    font = fontforge.open(str(base_ttf))
    font.fontname = "CEHandKRFinal-Regular"
    font.familyname = "CE Hand KR Final"
    font.fullname = "CE Hand KR Final Regular"
    font.weight = "Regular"
    font.version = "1.0"

    for svg_path in sorted(svg_dir.glob("*.svg")):
        char = unicodedata.normalize("NFC", svg_path.stem)
        if len(char) != 1:
            continue

        glyph = font[ord(char)]
        original_width = glyph.width
        glyph.clear()
        glyph.importOutlines(str(svg_path))

        for fn in (glyph.removeOverlap, glyph.correctDirection, glyph.removeOverlap):
            try:
                fn()
            except Exception:
                pass

        glyph.transform(psMat.scale(TARGET_SCALE, TARGET_SCALE))
        xmin, ymin, xmax, ymax = glyph.boundingBox()
        advance = max(int(original_width * TARGET_WIDTH_RATIO), 700)
        glyph.transform(psMat.translate((advance - (xmax - xmin)) / 2 - xmin, 350 - (ymin + ymax) / 2))
        glyph.width = advance

    font[32].width = 300
    font.ascent = 900
    font.descent = 250
    font.os2_typoascent = 900
    font.os2_typodescent = -250
    font.os2_winascent = 900
    font.os2_windescent = 250
    font.hhea_ascent = 900
    font.hhea_descent = -250
    font.hhea_linegap = 0
    font.generate(str(output_ttf))


def _patch_names(src: Path, dst: Path) -> None:
    font = TTFont(str(src))
    values = {
        1: "CE Hand KR Final",
        2: "Regular",
        4: "CE Hand KR Final Regular",
        6: "CEHandKRFinal-Regular",
    }
    for record in font["name"].names:
        if record.nameID in values:
            record.string = values[record.nameID].encode("utf-16-be")
    font.save(str(dst))


def generate(
    input_dir: Path,
    output_ttf: Path,
    mxfont_dir: Path,
    base_ttf: Path,
    chars_json: Path,
    generator_pth: Path,
) -> None:
    work_dir = Path(tempfile.mkdtemp(prefix="font_"))
    try:
        _preprocess(input_dir)
        png_dir = _run_mxfont(input_dir, work_dir, mxfont_dir, base_ttf, chars_json, generator_pth)
        svg_dir = _vectorize(png_dir, work_dir)
        raw_ttf = work_dir / "raw.ttf"
        _build_ttf(svg_dir, base_ttf, raw_ttf)
        _patch_names(raw_ttf, output_ttf)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
