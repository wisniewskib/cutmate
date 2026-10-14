from PIL import Image

from conftest import make_clip
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
    assert sum(top.getdata()) / (1080 * 200) < 120   # darkened top band
