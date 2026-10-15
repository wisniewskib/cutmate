"""Long-form checkpoint before the slow HyperFrames render: a 480p preview of the cut (A-roll + chapter plates)
and chapters.txt. Plates are drawn with Pillow and laid over with ffmpeg (no drawtext: font paths on Windows)."""
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from .build import CHAPTER_LABEL
from .chapters import chapters_txt
from .errors import CutmateError, MediaError
from .media import run
from .paths import theme_dir
from .plan import PLATE, load_plan
from .thumb import _load_font, _theme_meta, wrap

SIZES = {"16:9": (854, 480), "9:16": (480, 854)}


def plate_image(label: str, title: str, size: tuple[int, int], theme: str) -> Image.Image:
    W, H = size
    th = theme_dir(theme)
    meta = _theme_meta(th)
    img = Image.new("RGB", (W, H), "#0b0b0f")
    d = ImageDraw.Draw(img)
    lf = _load_font(th, meta, "bold", max(12, W // 40))
    tf = _load_font(th, meta, "black", max(20, W // 16))
    lines = wrap(title, tf, int(W * 0.8))
    lh = int(tf.size * 1.1)
    y = (H - (lf.size + 20 + lh * len(lines))) // 2
    d.text(((W - lf.getlength(label)) / 2, y), label, font=lf, fill=meta["accent"])
    y += lf.size + 20
    for line in lines:
        d.text(((W - tf.getlength(line)) / 2, y), line, font=tf, fill="white")
        y += lh
    return img


def preview(out_dir: Path, theme: str = "clean", language: str = "pl") -> dict:
    out = Path(out_dir).resolve()
    src = out / "aroll.mp4"
    if not src.exists():
        raise CutmateError(f"{src} not found — run `cutmate cut` first")
    plan = load_plan(out)
    W, H = SIZES[plan.format]
    ch = out / "chapters.txt"
    if plan.chapters:
        ch.write_text(chapters_txt(plan.chapters, plan.end), encoding="utf-8")
    else:
        ch.unlink(missing_ok=True)
    word = CHAPTER_LABEL.get(language, CHAPTER_LABEL["en"])
    dst = out / "preview.mp4"
    with tempfile.TemporaryDirectory() as td:
        plates = []
        for c in plan.chapters[1:]:
            p = Path(td) / f"ch{c['num']}.png"
            plate_image(f"{word} {c['num']:02d}", c["title"], (W, H), theme).save(p)
            plates.append((p, c["start"], min(c["start"] + PLATE, plan.end)))
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src]
        for p, _, _ in plates:
            cmd += ["-i", p]
        chain = [f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[v0]"]
        for k, (_, a, b) in enumerate(plates, 1):
            chain.append(f"[v{k - 1}][{k}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[v{k}]")
        cmd += ["-filter_complex", ";".join(chain), "-map", f"[v{len(plates)}]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", dst]
        r = run(cmd)
    if r.returncode or not dst.exists():
        raise MediaError(f"preview failed: {' '.join(r.stderr.split())[-400:]}")
    return {"preview": dst, "chapters": ch if plan.chapters else None}
