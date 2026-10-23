import argparse
import sys
from pathlib import Path

from . import config
from .backends import get_backend
from .errors import CutmateError
from .formats import FORMATS


def _positive_float(v: str) -> float:
    try:
        x = float(v)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid number: {v!r}") from None
    if not x > 0:
        raise argparse.ArgumentTypeError(f"must be > 0: {v}")
    return x


def _min_one_int(v: str) -> int:
    try:
        x = int(v)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: {v!r}") from None
    if x < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1: {v}")
    return x


def _float_list(v: str) -> list[float]:
    try:
        return [float(x) for x in v.split(",") if x.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected comma-separated seconds, got {v!r}") from None


def _utf8_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="cutmate", description="cutmate video pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("transcribe", help="transcribe every clip in a recording folder")
    t.add_argument("rec")
    t.add_argument("--prompt")
    t.add_argument("--backend", choices=config.BACKENDS)
    t.add_argument("--language", choices=config.LANGUAGES)
    t.add_argument("--force", action="store_true")
    fm = sub.add_parser("formats", help="aspect of every clip in a recording folder (rotation-aware)")
    fm.add_argument("rec")
    s = sub.add_parser("sheet", help="contact sheet of frames")
    s.add_argument("src")
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--start", type=float, default=0.0)
    s.add_argument("--end", type=float)
    s.add_argument("--step", type=_positive_float, default=0.5)
    s.add_argument("--cols", type=_min_one_int, default=6)
    c = sub.add_parser("cut", help="cut the A-roll from an EDL")
    c.add_argument("edl")
    a = sub.add_parser("align", help="word timings for the A-roll")
    a.add_argument("edl")
    a.add_argument("--language", choices=config.LANGUAGES)
    tc = sub.add_parser("theme-check", help="render every component of a theme and check it")
    tc.add_argument("--theme")
    tc.add_argument("--language", choices=config.LANGUAGES)
    tc.add_argument("--format", choices=["9:16", "16:9", "all"], default="all")
    b = sub.add_parser("build", help="plan.json → HyperFrames project (out/composition)")
    b.add_argument("out")
    b.add_argument("--theme")
    b.add_argument("--language", choices=config.LANGUAGES)
    pv = sub.add_parser("preview", help="fast 480p preview (cut + chapter plates) and chapters.txt")
    pv.add_argument("out")
    pv.add_argument("--theme")
    pv.add_argument("--language", choices=config.LANGUAGES)
    rd = sub.add_parser("render", help="check + render + finalize the built project")
    rd.add_argument("out")
    f = sub.add_parser("finalize", help="loudness fix + spec check of a render")
    f.add_argument("src")
    f.add_argument("dst")
    f.add_argument("--format", choices=list(FORMATS), default="9:16")
    f.add_argument("--check", type=_float_list, default=[])
    q = sub.add_parser("qa", help="QA of a finished video")
    q.add_argument("out")
    q.add_argument("--no-asr", action="store_true")
    q.add_argument("--backend", choices=config.BACKENDS)
    q.add_argument("--language", choices=config.LANGUAGES)
    p = sub.add_parser("probe", help="re-transcribe one short window (hidden retakes)")
    p.add_argument("wav")
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--end", type=float, required=True)
    p.add_argument("--prompt")
    p.add_argument("--backend", choices=config.BACKENDS)
    p.add_argument("--language", choices=config.LANGUAGES)
    tk = sub.add_parser("track", help="where the face and hands are over time (out/work/tracks.json)")
    tk.add_argument("out")
    tk.add_argument("--force", action="store_true")
    r = sub.add_parser("rms", help="RMS scan in short bins (speech blobs)")
    r.add_argument("wav")
    r.add_argument("--start", type=float, required=True)
    r.add_argument("--end", type=float, required=True)
    r.add_argument("--bin", type=_positive_float, default=0.05)
    sh2 = sub.add_parser("shot", help="screenshot a web page for b-roll")
    sh2.add_argument("url")
    sh2.add_argument("-o", "--out", required=True)
    sh2.add_argument("--width", type=_min_one_int, default=1000)
    sh2.add_argument("--height", type=_min_one_int, default=700)
    sh2.add_argument("--light", action="store_true")
    th2 = sub.add_parser("thumb", help="thumbnail from a frame + title")
    th2.add_argument("out")
    th2.add_argument("--at", type=float, required=True)
    th2.add_argument("--title", required=True)
    th2.add_argument("--hook", default="")
    th2.add_argument("--theme")
    th2.add_argument("--side", choices=["left", "right"], default="right")
    se = sub.add_parser("save-effect", help="keep a custom effect from out/custom in the user theme")
    se.add_argument("out")
    se.add_argument("name")
    se.add_argument("--theme")
    se.add_argument("--description", default="")
    se.add_argument("--force", action="store_true")
    th = sub.add_parser("theme", help="theme drafts: new, list, use, save, colors")
    ts = th.add_subparsers(dest="theme_cmd", required=True)
    tn = ts.add_parser("new", help="start a draft theme (copy of a base theme)")
    tn.add_argument("name", nargs="?")
    tn.add_argument("--from", dest="base", default="clean")
    tn.add_argument("--mode", choices=["custom", "random", "clone"], default="custom")
    tn.add_argument("--seed", type=int)
    tn.add_argument("--avoid", action="append", default=[], metavar="THEME")
    ts.add_parser("list", help="bundled, saved and draft themes")
    tu = ts.add_parser("use", help="make a saved theme the default")
    tu.add_argument("name")
    tsv = ts.add_parser("save", help="move a checked draft into your themes")
    tsv.add_argument("name")
    tsv.add_argument("--force", action="store_true")
    tck = ts.add_parser("check", help="lint a theme, render it in both formats and stamp it (the gate before save)")
    tck.add_argument("name")
    tck.add_argument("--clip", type=Path, help="use this video as the A-roll instead of the test pattern")
    tck.add_argument("--language", choices=["pl", "en"], default="pl")
    tck.add_argument("--saved", action="store_true", help="check the saved theme even if a draft has the same name")
    tfo = ts.add_parser("font", help="download an OFL Google Font into a draft (text, display or num = digit font)")
    tfo.add_argument("name")
    tfo.add_argument("family")
    tfo.add_argument("--role", choices=["text", "display", "num"], required=True)
    tdg = ts.add_parser("digits", help="render the theme's numbers in its display / digit font (check 5 vs S, 0 vs O)")
    tdg.add_argument("name")
    tcl = ts.add_parser("colors", help="dominant colours of images")
    tcl.add_argument("images", nargs="+", type=Path)
    tcl.add_argument("--n", type=_min_one_int, default=8)
    rq = sub.add_parser("requests", help="match out/requests.md (\"zrozumiałem tak\") against the plan")
    rq.add_argument("out")
    cf = sub.add_parser("config", help="show or change the cutmate config")
    cs = cf.add_subparsers(dest="config_cmd", required=True)
    cs.add_parser("show", help="print the effective config as JSON")
    cst = cs.add_parser("set", help="set KEY=VALUE pairs (e.g. language=en music.volume=0.3)")
    cst.add_argument("pairs", nargs="+", metavar="PAIR")
    st = sub.add_parser("selftest", help="transcription test with word timestamps on your own clip")
    st.add_argument("--clip", type=Path)
    st.add_argument("--backend", choices=config.BACKENDS)
    st.add_argument("--language", choices=config.LANGUAGES)
    sm = sub.add_parser("smoke", help="5 s smoke render (title + captions, optional music bed)")
    sm.add_argument("--clip", type=Path)
    sm.add_argument("--music", type=Path)
    sm.add_argument("--format", choices=list(FORMATS), default="9:16")
    sm.add_argument("--workdir", type=Path)
    sub.add_parser("vendor", help="fetch the libraries cutmate may not bundle (gsap) into the cutmate home, sha-checked")
    sub.add_parser("doctor", help="health report (JSON): packages, models, GPU, keys, config")
    md = sub.add_parser("models", help="download the local models (alignment, whisper, face/hand tracking)")
    md.add_argument("--language", choices=config.LANGUAGES)
    md.add_argument("--backend", choices=config.BACKENDS)
    return ap


def _config_cmd(args) -> int:
    import json
    from dataclasses import asdict
    if args.config_cmd == "show":
        print(json.dumps(asdict(config.load()), indent=2, ensure_ascii=False))
    else:
        cfg = config.set_values(args.pairs)
        print(f"saved {config.home() / 'config.json'}")
        print(json.dumps(asdict(cfg), indent=2, ensure_ascii=False))
    return 0


def _theme_cmd(args) -> int:
    import json
    from . import themes
    if args.theme_cmd == "new":
        r = themes.new_theme(args.name, args.base, args.mode, args.seed, args.avoid)
        print(json.dumps(r, ensure_ascii=False))
        if r["exists"]:
            print(f"WARN theme {r['name']} exists — saving will need --force")
    elif args.theme_cmd == "list":
        cur = config.load().theme
        for t in themes.list_themes():
            chk = "-" if t["checked"] is None else ("checked" if t["checked"] else "unchecked")
            mark = "*" if t["name"] == cur and t["kind"] != "draft" else "-"
            print("\t".join((mark, t["name"], t["kind"], chk, t["path"])))
    elif args.theme_cmd == "use":
        themes.use_theme(args.name)
        print(f"theme: {args.name}")
    elif args.theme_cmd == "save":
        print(themes.save_theme(args.name, args.force))
    elif args.theme_cmd == "check":
        r = themes.check_theme(args.name, args.clip, args.language, args.saved)
        print(f"check passed ({r['kind']}) — contact: {r['contact']}")
        for fmt, p in r["sheets"].items():
            print(f"sheet {fmt}: {p}")
    elif args.theme_cmd == "font":
        from . import fonts
        d = themes.draft_dir(args.name)
        if not (d / "theme.json").exists():
            raise CutmateError(f"no draft theme {args.name!r} — fonts go into a draft (cutmate theme new)")
        r = fonts.set_font(d, args.family, args.role)
        print(f"{r['family']} ({r['role']}): " + ", ".join(r["files"]))
    elif args.theme_cmd == "digits":
        print(themes.digit_sheet(args.name))
    elif args.theme_cmd == "colors":
        for hex_, share in themes.palette_of(args.images, args.n):
            print(f"{hex_}  {round(share * 100)}%")
    return 0


def _dispatch(args) -> int:
    if args.cmd == "config":
        return _config_cmd(args)
    if args.cmd == "theme":
        return _theme_cmd(args)
    if args.cmd == "doctor":
        import json
        from .doctor import doctor
        print(json.dumps(doctor(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "vendor":
        from .vendor import fetch
        print("\n".join(fetch(config.home() / "vendor")))
        return 0
    cfg = config.load()
    language = getattr(args, "language", None) or cfg.language
    if args.cmd == "models":
        from .doctor import download_models
        download_models(language, args.backend or cfg.transcription)
    elif args.cmd == "transcribe":
        from .transcribe import run_transcribe
        run_transcribe(Path(args.rec), get_backend(args.backend or cfg.transcription), language, args.prompt, args.force)
    elif args.cmd == "formats":
        from .formats import aspect
        from .media import probe_video
        from .transcribe import find_clips
        clips = find_clips(Path(args.rec))
        if not clips:
            raise CutmateError(f"no video files in {args.rec}")
        seen = set()
        for c in clips:
            i = probe_video(c)
            a = aspect(i["width"], i["height"])
            seen.add(a)
            print(f"{c.name}: {i['width']}x{i['height']} {a}")
        print("format: " + (seen.pop() if len(seen) == 1 else "mixed"))
    elif args.cmd == "sheet":
        from .sheet import contact_sheet
        for p in contact_sheet(Path(args.src), Path(args.out), args.start, args.end, args.step, args.cols):
            print(p)
    elif args.cmd == "cut":
        from .cut import cut_aroll
        cut_aroll(Path(args.edl))
    elif args.cmd == "align":
        from .align import run_align
        edl_path = Path(args.edl)
        # Check that required files exist before attempting alignment
        out_dir = edl_path.parent
        edl_timed = out_dir / "work" / "edl_timed.json"
        aroll = out_dir / "aroll.mp4"
        if not edl_path.exists():
            raise CutmateError(f"EDL file not found: {edl_path}; run `cutmate cut` first")
        if not edl_timed.exists():
            raise CutmateError(f"EDL timed file not found: {edl_timed}; run `cutmate cut` first")
        if not aroll.exists():
            raise CutmateError(f"A-roll file not found: {aroll}; run `cutmate cut` first")
        try:
            run_align(edl_path, language)
        except ImportError:
            raise CutmateError("alignment models not installed. Run /cutmate:setup.")
    elif args.cmd == "theme-check":
        from .layout import theme_layout
        from .paths import theme_dir
        from .theme_check import theme_check
        theme = args.theme or cfg.theme
        for fmt in ["9:16", "16:9"] if args.format == "all" else [args.format]:
            r = theme_check(theme, language=language, fmt=fmt,
                            layout=theme_layout(theme_dir(theme)) if fmt == "9:16" else None)
            print(f"check passed ({fmt}) — contact sheet: {r['sheet']}")
    elif args.cmd == "build":
        from .build import build
        r = build(Path(args.out), theme=args.theme or cfg.theme, language=language,
                  factcheck=bool(cfg.steps.get("factcheck")), music=cfg.music, captions=cfg.captions)
        for w in r["warnings"]:
            print(w)
        print(f"layout: {r['layout']}")
        for line in r["panel"]:
            print(f"panel: {line}")
        print(f"project: {r['project']}")
        print("checkpoints: " + ",".join(f"{t:.2f}" for t in r["checkpoints"]))
    elif args.cmd == "preview":
        from .preview import preview
        r = preview(Path(args.out), args.theme or cfg.theme, language)
        print(f"preview: {r['preview']}")
        if r["chapters"]:
            print(r["chapters"].read_text(encoding="utf-8"), end="")
    elif args.cmd == "render":
        from .render import render
        return 0 if render(Path(args.out))["ok"] else 1
    elif args.cmd == "finalize":
        from .finalize import finalize
        return 0 if finalize(Path(args.src), Path(args.dst), args.format, check=args.check)["ok"] else 1
    elif args.cmd == "qa":
        from .qa import run_qa
        backend = None if args.no_asr else get_backend(args.backend or cfg.transcription)
        run_qa(Path(args.out), backend, language, asr=not args.no_asr)
    elif args.cmd == "probe":
        from .backends import transcribe_window
        t = transcribe_window(get_backend(args.backend or cfg.transcription), Path(args.wav), args.start, args.end,
                              language, args.prompt)
        print(" ".join(f"{w.word}@{w.start:.2f}-{w.end:.2f}" for w in t.words))
    elif args.cmd == "selftest":
        from .selftest import selftest
        r = selftest(get_backend(args.backend or cfg.transcription), language, args.clip)
        comp = f" · compute: {r['compute']}" if r["compute"] else ""
        print(f"backend: {r['backend']} · device: {r['device']}{comp}")
        print(f"words: {len(r['words'])} in {r['seconds']:.1f} s for {r['audio']:.1f} s of audio")
        print("first: " + " ".join(f"{w.word}@{w.start:.2f}-{w.end:.2f}" for w in r["words"][:8]))
    elif args.cmd == "smoke":
        from .smoke import smoke
        backend = get_backend(cfg.transcription) if args.clip else None
        r = smoke(args.workdir or config.home() / "smoke", cfg, args.clip, args.format, args.music, backend)
        print(f"final: {r['final']}")
        print(f"frame: {r['frame']}")
        return 0 if r["ok"] else 1
    elif args.cmd == "track":
        from .tracks import load_tracks, track
        p = track(Path(args.out), force=args.force)
        d = load_tracks(Path(args.out))
        print(p)
        print("samples: " + ", ".join(f"{n} {len(s)}" for n, s in d["tracks"].items()))
    elif args.cmd == "rms":
        from .takes import blobs, rms_bins
        bins = rms_bins(Path(args.wav), args.start, args.end, args.bin)
        for t, db in bins:
            print(f"{t:7.2f} {db:6.1f} " + "#" * max(0, int((db + 60) / 3)))
        print("blobs: " + " ".join(f"[{a:.2f}-{b:.2f}]" for a, b in blobs(bins)))
    elif args.cmd == "shot":
        from .shot import screenshot
        print(screenshot(args.url, Path(args.out), args.width, args.height, dark=not args.light))
    elif args.cmd == "thumb":
        from .thumb import thumbnail
        r = thumbnail(Path(args.out), args.at, args.title, args.hook, args.theme or cfg.theme, side=args.side)
        print(r["png"])
        print(r["jpg"])
    elif args.cmd == "save-effect":
        from .effects import save_effect
        print(save_effect(Path(args.out), args.name, args.theme or cfg.theme, args.description, args.force))
    elif args.cmd == "requests":
        from .asks import check_requests
        lines = check_requests(Path(args.out))
        for ln in lines:
            print(ln)
        body = [ln.removeprefix("SURPRISE ") for ln in lines]      # surprises count like any other request
        print(f"requests: {sum(ln.startswith('OK') for ln in body)} ok, "
              f"{sum(ln.startswith('MISSING') for ln in body)} missing, {sum(ln.startswith('BAD') for ln in body)} bad")
    return 0


def main(argv: list[str] | None = None) -> int:
    _utf8_stdio()
    args = _parser().parse_args(argv)
    try:
        return _dispatch(args)
    except (CutmateError, OSError) as e:
        print(f"cutmate: {' '.join(str(e).split())}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
