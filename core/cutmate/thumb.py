"""Thumbnail: a frame with a strong expression + hook question + big title (the short's promise)."""
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .errors import CutmateError
from .media import extract_frame
from .paths import theme_dir

W, H = 1080, 1920


def wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if font.getlength(cand) <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _cover(im: Image.Image) -> Image.Image:
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def thumbnail(out_dir: Path, at: float, title: str, hook: str = "", theme: str = "clean") -> dict:
    out = Path(out_dir)
    src = out / "final.mp4" if (out / "final.mp4").exists() else out / "aroll.mp4"
    if not src.exists():
        raise CutmateError(f"{src} not found — run `cutmate cut` first")
    th = theme_dir(theme)
    meta = json.loads((th / "theme.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        frame = Image.open(extract_frame(src, at, Path(td) / "f.png")).convert("RGB")
    img = _cover(frame).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    for y in range(900):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(200 * (1 - y / 900))))
    img = Image.alpha_composite(img, shade)
    draw = ImageDraw.Draw(img)
    y = 260
    if hook:
        hf_ = ImageFont.truetype(str(th / "fonts" / meta["fonts"]["bold"]), 64)
        for line in wrap(hook, hf_, 920):
            draw.text(((W - hf_.getlength(line)) / 2, y), line, font=hf_, fill="white")
            y += 80
        y += 30
    words = title.upper()
    size = 170
    while True:
        tf = ImageFont.truetype(str(th / "fonts" / meta["fonts"]["black"]), size)
        lines = wrap(words, tf, 960)
        if len(lines) <= 3 or size <= 90:
            break
        size -= 10
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    ty = y
    for line in lines:
        sd.text(((W - tf.getlength(line)) / 2 + 6, ty + 6), line, font=tf, fill=(0, 0, 0, 200))
        ty += int(size * 1.05)
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(4)))
    draw = ImageDraw.Draw(img)
    ty = y
    for i, line in enumerate(lines):
        x = (W - tf.getlength(line)) / 2
        if i == len(lines) - 1 and " " in line:
            head, last = line.rsplit(" ", 1)
            draw.text((x, ty), head + " ", font=tf, fill="white")
            draw.text((x + tf.getlength(head + " "), ty), last, font=tf, fill=meta["accent"])
        else:
            draw.text((x, ty), line, font=tf, fill=meta["accent"] if len(lines) == 1 else "white")
        ty += int(size * 1.05)
    png, jpg = out / "thumbnail.png", out / "thumbnail.jpg"
    img.convert("RGB").save(png)
    q = 92
    while True:
        img.convert("RGB").save(jpg, quality=q)
        if jpg.stat().st_size <= 2_000_000 or q <= 60:
            break
        q -= 8
    return {"png": png, "jpg": jpg}
