import pytest
from PIL import Image

from cutmate.errors import MediaError
from cutmate.sheet import contact_sheet


def test_single_sheet(clip, tmp_path):
    paths = contact_sheet(clip, tmp_path / "sheet.png", step=0.5)
    assert paths == [tmp_path / "sheet.png"]
    im = Image.open(paths[0])
    assert im.width == 6 * 240  # 6–7 frames in 3 s at 0.5 s, 6 columns


def test_splits_into_several_sheets(clip, tmp_path):
    paths = contact_sheet(clip, tmp_path / "s.png", step=0.5, per_sheet=4)
    assert [p.name for p in paths] == ["s_01.png", "s_02.png"]


def test_range(clip, tmp_path):
    paths = contact_sheet(clip, tmp_path / "r.png", start=1.0, end=2.0, step=0.25, cols=2)
    im = Image.open(paths[0])
    assert im.width == 2 * 240 and im.height >= 2 * 135


def test_empty_range(clip, tmp_path):
    with pytest.raises(MediaError, match="empty range"):
        contact_sheet(clip, tmp_path / "x.png", start=5.0)
