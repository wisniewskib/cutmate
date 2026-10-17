import re

from cutmate import paths
from cutmate.cli import _parser


def test_skill_frontmatter_and_commands():
    text = (paths.plugin_root() / "skills" / "edit" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: edit\ndescription: ")
    sub = next(a for a in _parser()._actions if a.dest == "cmd")
    known = set(sub.choices)
    used = set(re.findall(r"\$CM (\w[\w-]*)", text))
    assert used and used <= known, used - known
    for step in ("takes.md", "edl.json", "plan.json", "factcheck.md", "EDIT_NOTES.md", "frame.md"):
        assert step in text


def test_skill_flags_and_pinned_hyperframes():
    text = (paths.plugin_root() / "skills" / "edit" / "SKILL.md").read_text(encoding="utf-8")
    sub = next(a for a in _parser()._actions if a.dest == "cmd")
    calls = re.findall(r"\$CM (\w[\w-]*)([^`\n]*)", text)
    assert calls
    for cmd, rest in calls:
        known = {s for a in sub.choices[cmd]._actions for s in a.option_strings}
        for flag in re.findall(r"(?<!\S)(--?[A-Za-z][\w-]*)", rest):
            assert flag in known, (cmd, flag)
    npx = re.findall(r"npx\b[^`\n]*", text)
    assert npx
    for call in npx:
        if "hyperframes" in call:
            assert "hyperframes@0.8.157" in call, call


def test_skill_covers_169():
    md = (paths.plugin_root() / "skills" / "edit" / "SKILL.md").read_text(encoding="utf-8")
    for s in ("cutmate formats", "$CM formats", "outline.md", "$CM preview", "chapters.txt", "captions.srt",
              "\"chapters\"", "\"face\"", "pip", "lower-third", "--side", "subagent", "1280×720"):
        assert s in md, s


def test_skill_covers_effects():
    md = (paths.plugin_root() / "skills" / "edit" / "SKILL.md").read_text(encoding="utf-8")
    for s in ("requests.md", "$CM requests", "$CM track", "$CM save-effect", "\"custom\"", "\"follow\"", "\"bg\"",
              "\"side\"", "U.clock", "U.three", "U.trackAt", "U.seed", "energy-ball", "out/custom/",
              "zrozumiałem tak", "polecenia"):
        assert s in md, s


def test_skill_covers_2d():
    md = (paths.plugin_root() / "skills" / "edit" / "SKILL.md").read_text(encoding="utf-8")
    for s in ("\"place\": \"gesture\"", "\"speaker\": \"gesture\"", "stat-card", "iso-machine", "ui-mock", "flow",
              "index.json", "niespodzianka", "bez niespodzianek", "explainer"):
        assert s in md, s
    assert "build does NOT check explainer numbers" in md and "the build warns about numbers no" not in md
    for s in ("replies?", "U.ready(", "U.fonts(", "track --force"):
        assert s in md, s


def test_skill_puts_effects_on_every_gesture():
    md = (paths.plugin_root() / "skills" / "edit" / "SKILL.md").read_text(encoding="utf-8")
    for s in ("**Every gesture gets an effect.**", "open / presenting palm", "clear index-finger point",
              "every 0.25 s", "never cover the face", "hand-sparks", "anchor it on the GESTURE", "no hand-shape data"):
        assert s in md, s
