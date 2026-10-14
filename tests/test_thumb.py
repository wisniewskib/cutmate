import pytest
from PIL import Image

from conftest import make_clip
from cutmate.errors import CutmateError
from cutmate.thumb import thumbnail, wrap


def test_wrap_respects_width():
    from PIL import ImageFont

    from cutmate import paths
    f = ImageFont.truetype(str(paths.theme_dir("clean") / "fonts" / "Inter-Black.ttf"), 120)
    lines = wrap("SAME KONKRETY BEZ ŚCIEMY", f, 960)
    assert len(lines) >= 2 and all(f.getlength(line) <= 960 for line in lines)


def test_thumbnail_files(tmp_path):
    out = tmp_path / "out"
    make_clip(out / "aroll.mp4", dur=3.0, size="1080x1920", gaps=())
    r = thumbnail(out, 1.0, "Same konkrety", hook="Czy Caveman dalej działa?")
    png = Image.open(r["png"])
    assert png.size == (1080, 1920)
    assert r["jpg"].stat().st_size < 2_000_000
    top = png.crop((0, 0, 1080, 200)).convert("L")
    assert sum(top.get_flattened_data()) / (1080 * 200) < 120   # darkened top band


def test_thumbnail_title_too_long(tmp_path):
    out = tmp_path / "out"
    make_clip(out / "aroll.mp4", dur=3.0, size="1080x1920", gaps=())
    # This title is too long to fit in 3 lines even at minimum size
    with pytest.raises(CutmateError, match="title too long"):
        thumbnail(out, 1.0, "This is a very long title that will not fit in the thumbnail at all even with the minimum font size")


def test_thumbnail_hook_capped(tmp_path):
    out = tmp_path / "out"
    make_clip(out / "aroll.mp4", dur=3.0, size="1080x1920", gaps=())
    # Hook with many words should be capped at 2 lines
    r = thumbnail(out, 1.0, "Test", hook="This is a very long hook question that should be capped at two lines with ellipsis on the second")
    png = Image.open(r["png"])
    # Just verify it renders without error
    assert png.size == (1080, 1920)


def test_thumbnail_accent_color(tmp_path):
    from cutmate import paths
    out = tmp_path / "out"
    make_clip(out / "aroll.mp4", dur=3.0, size="1080x1920", gaps=())
    # Single word title should be entirely in accent color
    r = thumbnail(out, 1.0, "Word", hook="")
    png = Image.open(r["png"])
    # Crop to title area and check for accent color pixels
    title_area = png.crop((200, 300, 880, 600))
    title_rgb = title_area.convert("RGB")
    pixels = list(title_rgb.get_flattened_data())
    accent_hex = "#7dd3fc"
    accent_rgb = tuple(int(accent_hex[i:i+2], 16) for i in (1, 3, 5))
    # Check for pixels close to accent color (tolerance ~40 per channel)
    accent_pixels = [p for p in pixels if all(abs(p[i] - accent_rgb[i]) < 40 for i in range(3))]
    assert len(accent_pixels) > 100, "Expected accent color pixels in title area"


def test_thumbnail_multiline_accent(tmp_path):
    from cutmate import paths
    out = tmp_path / "out"
    make_clip(out / "aroll.mp4", dur=3.0, size="1080x1920", gaps=())
    # Two-line title: last word should be in accent
    r = thumbnail(out, 1.0, "Same konkrety", hook="")
    png = Image.open(r["png"])
    # Crop to title area
    title_area = png.crop((150, 300, 930, 700))
    title_rgb = title_area.convert("RGB")
    pixels = list(title_rgb.get_flattened_data())
    accent_hex = "#7dd3fc"
    accent_rgb = tuple(int(accent_hex[i:i+2], 16) for i in (1, 3, 5))
    # Check for accent color pixels (the word KONKRETY should be in accent)
    accent_pixels = [p for p in pixels if all(abs(p[i] - accent_rgb[i]) < 40 for i in range(3))]
    assert len(accent_pixels) > 100, "Expected accent color pixels in last word"


def test_thumbnail_uses_aroll_not_final(tmp_path):
    out = tmp_path / "out"
    make_clip(out / "aroll.mp4", dur=3.0, size="1080x1920", gaps=())
    import subprocess
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0xff0000:s=1080x1920:d=3:r=30",
                    "-pix_fmt", "yuv420p", str(out / "final.mp4")], check=True)
    r = thumbnail(out, 1.0, "X")
    px = Image.open(r["png"]).convert("RGB").getpixel((540, 1700))
    assert not (px[0] > 200 and px[1] < 60 and px[2] < 60)   # not final.mp4's red
