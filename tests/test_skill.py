import re

from cutmate import config, paths
from cutmate.cli import _parser


def _skill(name):
    return (paths.plugin_root() / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def _theme_file(name):
    return (paths.plugin_root() / "skills" / "theme" / name).read_text(encoding="utf-8")


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
        if nested is not None:
            assert first in nested.choices, (cmd, first)
            parser = nested.choices[first]
        flags = {s for a in parser._actions for s in a.option_strings}
        for flag in re.findall(r"(?<!\S)(--?[A-Za-z][\w-]*)", rest):
            assert flag in flags, (cmd, flag)
    npx = re.findall(r"npx\b[^`\n]*", text)
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


def test_edit_setup_skills_call_hyperframes():
    for name in ("edit", "setup"):
        assert re.search(r"npx\b[^`\n]*", _skill(name)), name


def test_theme_skill_frontmatter():
    assert _skill("theme").startswith("---\nname: theme\ndescription: ")


def test_theme_skill_covers_3b():
    md = _skill("theme")
    for s in ("AskUserQuestion", "\U0001f3b2", "Zaskocz mnie", "Biorę", "Losuj jeszcze raz", "$CM theme new --mode random",
              "--avoid", "$CM theme save", "--force", "Nadpisać", "$CM theme use", "$CM theme list", "cutmate:clone-style",
              "generate.md"):
        assert s in md, s
    gen = _theme_file("generate.md")
    for s in ("$CM theme font", "$CM theme check", "--clip", "contact.png", "U.seed", "html.f169 ROOT", "Tytuł ąę",
              "y 230–720", "cutmate:font", "Math.random", "not just colour"):
        assert s in gen, s


def test_theme_skill_cli_calls_known():
    check_cli_calls(_skill("theme"))
    check_cli_calls(_theme_file("generate.md"))


def test_check_cli_calls_rejects_unknown_nested():
    import pytest
    with pytest.raises(AssertionError):
        check_cli_calls("`$CM theme neww x`")
    check_cli_calls("`$CM theme new x --mode random`")


def _section(md, start, end=None):
    i = md.index(start)
    return md[i:md.index(end, i)] if end else md[i:]


def test_generate_bold_recipes():
    gen = _theme_file("generate.md")
    rec = _section(gen, "**Recipes", "**Keep in every component")
    for s in ("sharp", "pill", "outline", "brutal", "tape", "snappy", "smooth", "glitch", "typewriter", "slam",
              "title", "counter", "stamp", "notched", "8px 8px 0", "steps(4)", "U.seed", "scale 3"):
        assert s in rec, s
    assert "change the structure, not only the property values" in gen
    q = _section(gen, "## 7. Quality bar")
    for s in ("$CM theme check clean", "${CUTMATE_HOME:-$HOME/.cutmate}/checks/clean/contact.png", "side by side"):
        assert s in q, s
    intro = gen[:gen.index("## 1.")]
    assert "random and clone" in intro and "custom themes must meet the same bar by eye" in intro


def test_generate_keeps_structure():
    gen = _theme_file("generate.md")
    keep = _section(gen, "**Keep in every component", "| component |")
    for s in ("POS", "ORIGIN", "html.f169 ROOT .point", "!important", "lower-third", "chapter", "position: absolute",
              "<markup>", "place", "safe"):
        assert s in keep, s


def test_theme_skill_fix_round_1():
    md = _skill("theme")
    gen = _theme_file("generate.md")
    s3 = _section(md, "## 3.", "## 4.")
    assert s3.count("(polecane)") >= 4
    assert "lint checks contrast — fix and re-run" in s3
    assert "replaces an existing draft of that name" in s3
    s5 = _section(md, "## 5.")
    assert "current theme first" in s5 and "name = 2nd column, path = 5th" in s5
    s1 = _section(gen, "## 1.", "## 2.")
    assert "font-weight" in s1 and "Anton 400" in s1


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


def test_setup_skill_long_running_guidance():
    md = _skill("setup")
    guide = "Bash timeout 600000 or run_in_background: true; on timeout re-run — downloads resume"
    sections = {p.split("\n", 1)[0]: p for p in md.split("\n## ")}
    for title, cmd in (("5. Backend and language", "$CM models"), ("6. Transcription test", "$CM selftest"),
                       ("10. Smoke render (5 s)", "$CM smoke")):
        sec = sections[title]
        assert cmd in sec and guide in sec, title


def test_setup_skill_pauses_for_api_key():
    md = _skill("setup")
    for s in ("zrestartuj Claude Code ze zmienną ustawioną i uruchom /cutmate:setup", "Paused for an API key",
              "needs a terminal", "--json", "LUFS", "tracking"):
        assert s in md, s


def _music_examples(md):
    return re.findall(r'"music":\s*\{[^}]*\}', md)


def test_edit_skill_example_keeps_config_music_volume():
    md = _skill("edit")
    assert _music_examples(md)
    assert all('"volume": 0.45' not in m for m in _music_examples(md))
    assert "omit `volume` to use the config `music.volume`" in md


def test_edit_skill_heygen_resolve_json():
    md = _skill("edit")
    resolves = [l for l in re.findall(r"media-use resolve --type bgm[^`\n]*", md)]
    assert resolves and all("--json" in r for r in resolves)
    assert "take the local audio file path from the JSON; check it exists" in md


def test_setup_skill_finished_marker():
    md = _skill("setup")
    marker = "${CUTMATE_HOME:-$HOME/.cutmate}/smoke/rec/out/final.mp4"
    assert marker in md
    step0 = md[md.index("## 0. Re-run"):md.index("## 1. Detect")]
    assert marker in step0 and "steps 7–10" in step0 and "Którą sekcję zmienić?" in step0


def test_setup_skill_windows_path_restart():
    md = _skill("setup")
    sec = md[md.index("## 2. System dependencies"):md.index("## 3. Transcription")]
    assert "winget" in sec and "restart Claude Code and run /cutmate:setup again" in sec


def test_setup_skill_translate_labels():
    assert "the labels below are Polish; translate them to the user's language, keep the mapping" in _skill("setup")


def test_setup_skill_stale_editable_install():
    md = _skill("setup")
    step0 = md[md.index("## 0. Re-run"):md.index("## 1. Detect")]
    assert "plugin_root" in step0 and "${CLAUDE_PLUGIN_ROOT}" in step0 and "setup.sh" in step0


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


def test_clone_skill_download_rules():
    md = _skill("clone-style")
    assert md.startswith("---\nname: clone-style\ndescription: ")
    for s in ("only after", "yt-dlp --no-playlist", "--cookies", "--cookies-from-browser", "never sign in", "screenshots",
              "${CUTMATE_HOME:-$HOME/.cutmate}/clone/", "$CM sheet", "$CM theme colors", "Co widzę", "--mode clone",
              "generate.md", "never copied"):
        assert s in md, s
    check_cli_calls(md)


def test_clone_skill_fix_round_1():
    md = _skill("clone-style")
    lines = re.findall(r"yt-dlp --no-playlist[^`\n]*", md)
    assert lines
    for line in lines:
        assert "--ignore-config" in line and '-S "vcodec:h264,res:1080"' in line, line
        for bad in ("--cookies", "--cookies-from-browser", "--username", "--password", "--netrc"):
            assert bad not in line, (bad, line)
    src = _section(md, "## 1.", "## 2.")
    assert "jeden film" in src and "kilkadziesiąt MB" in src and "Nothing runs before Tak" in src
    look = _section(md, "## 2.", "## 3.")
    assert "at most 2 source videos" in look and "4 sheets" in look
    build = _section(md, "## 4.", "## 5.")
    assert "hstack" in build and "side-by-side.png" in build and "entrance row" in build


def test_setup_skill_theme_step():
    md = _skill("setup")
    theme = _section(md, "## 9b. Theme", "## 10.")
    for s in ("Zaskocz mnie", "cutmate:theme", "cutmate:clone-style", "$CM theme use", "--clip"):
        assert s in theme, s
    assert "Clean (polecane)" not in theme and "neutralny) (polecane)" not in theme
    step0 = _section(md, "## 0. Re-run", "## 1. Detect")
    assert "Napisy i kroki" in step0 and "Theme" in step0
    assert "The theme stays" not in md
    assert "$CM config set theme=clean" in theme


def test_edit_skill_theme_from_config():
    md = _skill("edit")
    for s in ("$CM theme list", "$CM theme check", "unchecked", "--theme"):
        assert s in md, s
    assert "theme-check --theme" not in md


def test_density_rule_in_skill_and_frame():
    md = _skill("edit")
    for s in ("Gęstość", "density", "4 s"):
        assert s in md, s
    frame = (paths.plugin_root() / "themes" / "clean" / "frame.md").read_text(encoding="utf-8")
    assert "≥ 50 %" in frame and "4 s" in frame


def test_theme_check_and_render_prefer_background_and_explain_the_deadline_warn():
    for name in ("theme", "edit", "setup"):
        md = " ".join(_skill(name).split())
        assert "prefer Bash run_in_background: true" in md, name
    for name in ("theme", "edit"):
        assert "WARN hyperframes check ran out of time" in _skill(name), name


def test_theme_list_parsing_is_tab_based_and_edit_checks_the_saved_theme():
    rule = "split on tabs: name = 2nd column, path = 5th"
    for name in ("theme", "edit"):
        md = " ".join(_skill(name).split())
        assert "marker\\tname\\tkind\\tchecked\\tpath" in md and rule in md, name
        assert "first 2 characters" not in md, name
    edit = " ".join(_skill("edit").split())
    assert "kind is not `draft`" in edit and "$CM theme check <theme> --saved" in edit
