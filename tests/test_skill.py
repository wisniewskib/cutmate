import re

from cutmate import config, paths
from cutmate.cli import _parser


def _skill(name):
    return (paths.plugin_root() / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def check_cli_calls(text):
    sub = next(a for a in _parser()._actions if a.dest == "cmd")
    known = set(sub.choices)
    used = set(re.findall(r"\$CM (\w[\w-]*)", text))
    assert used and used <= known, used - known
    calls = re.findall(r"\$CM (\w[\w-]*)([^`\n]*)", text)
    assert calls
    for cmd, rest in calls:
        parser = sub.choices[cmd]
        nested = next((a for a in parser._actions if a.choices and not a.option_strings), None)
        first = rest.split()[0] if rest.split() else ""
        if nested is not None and first in nested.choices:
            parser = nested.choices[first]
        flags = {s for a in parser._actions for s in a.option_strings}
        for flag in re.findall(r"(?<!\S)(--?[A-Za-z][\w-]*)", rest):
            assert flag in flags, (cmd, flag)
    npx = re.findall(r"npx\b[^`\n]*", text)
    assert npx
    for call in npx:
        if "hyperframes" in call:
            assert "hyperframes@0.8.157" in call, call


def test_skill_frontmatter_and_commands():
    text = _skill("edit")
    assert text.startswith("---\nname: edit\ndescription: ")
    for step in ("takes.md", "edl.json", "plan.json", "factcheck.md", "EDIT_NOTES.md", "frame.md"):
        assert step in text


def test_skill_cli_calls_known():
    for name in ("edit", "setup"):
        check_cli_calls(_skill(name))


def test_setup_skill_frontmatter():
    assert _skill("setup").startswith("---\nname: setup\ndescription: ")


def test_setup_skill_covers_3a():
    md = _skill("setup")
    for s in ("detect.sh", "detect.ps1", "setup.sh", "setup.ps1", "AskUserQuestion", "GROQ_API_KEY", "OPENAI_API_KEY",
              "ELEVENLABS_API_KEY", "Never ask for an API key", "heygen auth login --oauth", "media-use resolve --doctor",
              "Którą sekcję zmienić?", "0.45", "$CM selftest", "$CM smoke", "$CM models", "$CM doctor", "device: cuda",
              "sudo", "CUTMATE_HOME"):
        assert s in md, s


def test_setup_skill_config_keys_valid():
    md = _skill("setup")
    sets = re.findall(r"\$CM config set ([^`\n]*)", md)
    assert sets
    keys = {k for rest in sets for k in re.findall(r"([\w.:]+)=", rest)}
    assert keys and keys <= set(config.SETTABLE), keys - set(config.SETTABLE)


def test_edit_skill_uses_setup_venv():
    md = _skill("edit")
    assert "${CUTMATE_HOME:-$HOME/.cutmate}/venv/bin/cutmate" in md
    assert "$CM config show" in md
    assert "cat ~/.cutmate/config.json" not in md


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
