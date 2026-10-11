import argparse
import sys
from pathlib import Path

from . import config
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
    return ap


def _dispatch(args) -> int:
    cfg = config.load()
    language = getattr(args, "language", None) or cfg.language
    if args.cmd == "transcribe":
        from .backends import get_backend
        from .transcribe import run_transcribe
        run_transcribe(Path(args.rec), get_backend(args.backend or cfg.transcription), language, args.prompt, args.force)
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
    elif args.cmd == "finalize":
        from .finalize import finalize
        return 0 if finalize(Path(args.src), Path(args.dst), args.format, check=args.check)["ok"] else 1
    elif args.cmd == "qa":
        from .backends import get_backend
        from .qa import run_qa
        backend = None if args.no_asr else get_backend(args.backend or cfg.transcription)
        run_qa(Path(args.out), backend, language, asr=not args.no_asr)
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
