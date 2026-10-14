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
