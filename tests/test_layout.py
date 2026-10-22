import pytest

from cutmate.errors import CutmateError
from cutmate.layout import SPLIT_DEFAULTS, layout_problems, parse_layout


def test_missing_layout_is_classic():
    assert parse_layout(None).mode == "classic"
    assert parse_layout({"mode": "classic", "ratio": 9}).mode == "classic"


def test_split_panel_defaults():
    assert parse_layout({"mode": "split-panel"}) == SPLIT_DEFAULTS


def test_split_panel_overrides():
    lay = parse_layout({"mode": "split-panel", "ratio": 0.45, "cadence": [0.5, 2], "captions": "bottom",
                        "transition": "fade", "fullscreen": {"max_per_min": 0}})
    assert (lay.ratio, lay.cadence, lay.captions, lay.transition, lay.fullscreen_max_per_min) == \
        (0.45, (0.5, 2.0), "bottom", "fade", 0)


@pytest.mark.parametrize("raw,needle", [
    ({"mode": "grid"}, "layout.mode"),
    ({"mode": "split-panel", "ratio": 0.7}, "layout.ratio"),
    ({"mode": "split-panel", "cadence": [3, 1]}, "layout.cadence"),
    ({"mode": "split-panel", "cadence": [0.2, 2]}, "layout.cadence"),
    ({"mode": "split-panel", "cadence": [1, 7]}, "layout.cadence"),
    ({"mode": "split-panel", "captions": "top"}, "layout.captions"),
    ({"mode": "split-panel", "panel": "bottom"}, "layout.panel"),
    ({"mode": "split-panel", "transition": "wipe"}, "layout.transition"),
    ({"mode": "split-panel", "fullscreen": {"max_per_min": 9}}, "layout.fullscreen"),
    ({"mode": "split-panel", "foo": 1}, "unknown key 'foo'"),
    ("split", "layout must be an object"),
])
def test_layout_problems(raw, needle):
    assert any(needle in p for p in layout_problems(raw))


def test_no_problems_for_valid_or_missing():
    assert layout_problems(None) == []
    assert layout_problems({"mode": "split-panel"}) == []


def test_parse_layout_raises_one_line():
    with pytest.raises(CutmateError) as e:
        parse_layout({"mode": "split-panel", "ratio": 2, "captions": "x"})
    assert "\n" not in str(e.value) and str(e.value).startswith("theme layout:")
