"""Thumbnail: a frame with a strong expression + hook question + big title (the short's promise)."""
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .errors import CutmateError
from .formats import format_of
from .media import extract_frame, duration
from .paths import theme_dir

PORTRAIT = (1080, 1920)
LANDSCAPE = (1280, 720)


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


def _cover(im: Image.Image, W: int, H: int) -> Image.Image:
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def _theme_meta(th: Path) -> dict:
    f = th / "theme.json"
    try:
        meta = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CutmateError(f"{f}: cannot read theme ({e})") from None
    try:
        _ = meta["accent"]
        _ = meta["fonts"]["bold"]
        _ = meta["fonts"]["black"]
    except KeyError as e:
        raise CutmateError(f"{f}: theme.json missing required key {e}") from None
    return meta


def _load_font(th: Path, meta: dict, key: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        font_file = meta["fonts"][key]
        return ImageFont.truetype(str(th / "fonts" / font_file), size)
    except (KeyError, OSError) as e:
        raise CutmateError(f"cannot load font {key}: {e}") from None


def thumbnail(out_dir: Path, at: float, title: str, hook: str = "", theme: str = "clean", side: str = "right") -> dict:
    out = Path(out_dir)
    src = out / "aroll.mp4"  # never final.mp4: it has burned-in captions and graphics
    if not src.exists():
        raise CutmateError(f"{src} not found — run `cutmate cut` first")

    dur = duration(src)
    at = max(0.0, min(at, dur - 0.05))

    th = theme_dir(theme)
    meta = _theme_meta(th)

    with tempfile.TemporaryDirectory() as td:
        frame = Image.open(extract_frame(src, at, Path(td) / "f.png")).convert("RGB")
    if format_of(out) == "16:9":
        return _thumb_169(out, frame, title, hook, th, meta, side)
    W, H = PORTRAIT
    img = _cover(frame, W, H).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    for y in range(900):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(200 * (1 - y / 900))))
    img = Image.alpha_composite(img, shade)
    draw = ImageDraw.Draw(img)
    y = 260

    if hook:
        hf_ = _load_font(th, meta, "bold", 64)
        hook_lines = wrap(hook, hf_, 920)
        if len(hook_lines) > 2:
            hook_lines = hook_lines[:2]
            hook_lines[-1] = (hook_lines[-1][:20] + "…") if len(hook_lines[-1]) > 20 else hook_lines[-1] + "…"
        for line in hook_lines:
            draw.text(((W - hf_.getlength(line)) / 2, y), line, font=hf_, fill="white")
            y += 80
        y += 30

    words = title.upper()
    size = 170
    tf = None
    while True:
        tf = _load_font(th, meta, "black", size)
        lines = wrap(words, tf, 960)
        if len(lines) <= 3:
            break
        if size <= 90:
            raise CutmateError("title too long for the thumbnail — shorten it")
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
        if i == len(lines) - 1:
            head, _, last = line.rpartition(" ")
            if head:
                draw.text((x, ty), head + " ", font=tf, fill="white")
            draw.text((x + tf.getlength(head + " " if head else ""), ty), last, font=tf, fill=meta["accent"])
        else:
            draw.text((x, ty), line, font=tf, fill="white")
        ty += int(size * 1.05)

    return _save(out, img)


def _save(out: Path, img: Image.Image) -> dict:
    png, jpg = out / "thumbnail.png", out / "thumbnail.jpg"
    img.convert("RGB").save(png)
    q = 92
    while True:
        img.convert("RGB").save(jpg, quality=q)
        if jpg.stat().st_size <= 2_000_000 or q <= 60:
            break
        q -= 8
    return {"png": png, "jpg": jpg}


def _thumb_169(out: Path, frame: Image.Image, title: str, hook: str, th: Path, meta: dict, side: str) -> dict:
    W, H = LANDSCAPE
    if side not in ("left", "right"):
        raise CutmateError(f"side must be left or right, got {side!r}")
    img = _cover(frame, W, H).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    for x in range(760):
        a = int(210 * (1 - x / 760))
        xx = x if side == "left" else W - 1 - x
        d.line([(xx, 0), (xx, H)], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img, shade)
    box_w, x0 = 560, (60 if side == "left" else W - 60 - 560)
    size = 110
    while True:
        tf = _load_font(th, meta, "black", size)
        lines = wrap(title.upper(), tf, box_w)
        if len(lines) <= 3:
            break
        if size <= 60:
            raise CutmateError("title too long for the thumbnail — shorten it")
        size -= 8
    hf_ = _load_font(th, meta, "bold", 40)
    hook_lines = wrap(hook, hf_, box_w)[:2] if hook else []
    block = len(hook_lines) * 52 + (20 if hook_lines else 0) + len(lines) * int(size * 1.05)
    y = (H - block) // 2
    draw = ImageDraw.Draw(img)
    for line in hook_lines:
        draw.text((x0, y), line, font=hf_, fill="white")
        y += 52
    y += 20 if hook_lines else 0
    for i, line in enumerate(lines):
        if i == len(lines) - 1:
            head, _, last = line.rpartition(" ")
            if head:
                draw.text((x0, y), head + " ", font=tf, fill="white")
            draw.text((x0 + tf.getlength(head + " " if head else ""), y), last, font=tf, fill=meta["accent"])
        else:
            draw.text((x0, y), line, font=tf, fill="white")
        y += int(size * 1.05)
    return _save(out, img)
