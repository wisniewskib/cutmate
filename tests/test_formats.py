import json

import pytest

from cutmate.errors import CutmateError
from cutmate.formats import aspect, format_of


def test_aspect():
    assert aspect(1920, 1080) == "16:9"
    assert aspect(1080, 1920) == "9:16"
    assert aspect(1080, 1080) == "9:16"


def test_format_of_default_and_edl(tmp_path):
    assert format_of(tmp_path) == "9:16"
    (tmp_path / "edl.json").write_text(json.dumps({"format": "16:9", "segments": []}), encoding="utf-8")
    assert format_of(tmp_path) == "16:9"


def test_format_of_bad(tmp_path):
    (tmp_path / "edl.json").write_text(json.dumps({"format": "4:3"}), encoding="utf-8")
    with pytest.raises(CutmateError, match="4:3"):
        format_of(tmp_path)
    (tmp_path / "edl.json").write_text("{oops", encoding="utf-8")
    with pytest.raises(CutmateError, match="edl.json"):
        format_of(tmp_path)
