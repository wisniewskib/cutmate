from cutmate import paths


def test_skill_covers_169():
    md = (paths.plugin_root() / "skills" / "edit" / "SKILL.md").read_text(encoding="utf-8")
    for s in ("cutmate formats", "$CM formats", "outline.md", "$CM preview", "chapters.txt", "captions.srt",
              "\"chapters\"", "\"face\"", "pip", "lower-third", "--side", "subagent", "1280×720"):
        assert s in md, s
