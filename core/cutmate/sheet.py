"""Contact sheets: frames every `step` seconds tiled into PNGs with time labels. Claude reads them as images
to see faces, gestures, pointing, looking away — what the transcript can't tell."""
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .errors import MediaError
from .media import duration, require_ffmpeg, run


def contact_sheet(src: Path, out_png: Path, start: float = 0.0, end: float | None = None, step: float = 0.5,
                  cols: int = 6, thumb_w: int = 240, per_sheet: int = 48) -> list[Path]:
    require_ffmpeg()
    src, out_png = Path(src), Path(out_png)
    total = duration(src)
    end = total if end is None else min(end, total)
    if end - start < step / 2:
        raise MediaError(f"empty range {start:.2f}-{end:.2f}s in {src.name} ({total:.2f}s long)")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        r = run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", src,
                 "-vf", f"fps=1/{step},scale={thumb_w}:-2", "-start_number", "0", Path(td) / "f%05d.png"])
        frames = sorted(Path(td).glob("f*.png"))
        if r.returncode or not frames:
            raise MediaError(f"cannot extract frames from {src}: {r.stderr.strip()[-300:]}")
        paths = []
        for n in range(0, len(frames), per_sheet):
            imgs = [Image.open(f).convert("RGB") for f in frames[n:n + per_sheet]]
            tw, th = imgs[0].size
            rows = -(-len(imgs) // cols)
            sheet = Image.new("RGB", (min(cols, len(imgs)) * tw, rows * th), "black")
            draw = ImageDraw.Draw(sheet)
            font = ImageFont.load_default(size=max(12, tw // 12))
            for i, im in enumerate(imgs):
                x, y = (i % cols) * tw, (i // cols) * th
                sheet.paste(im, (x, y))
                label = f"{start + (n + i) * step:.2f}s"
                box = draw.textbbox((x + 4, y + 2), label, font=font)
                draw.rectangle((box[0] - 3, box[1] - 2, box[2] + 3, box[3] + 2), fill="black")
                draw.text((x + 4, y + 2), label, fill="yellow", font=font)
            p = out_png if len(frames) <= per_sheet else out_png.with_name(
                f"{out_png.stem}_{n // per_sheet + 1:02d}{out_png.suffix}")
            sheet.save(p)
            paths.append(p)
    return paths
