"""Contract test for a theme pack: every component renders in a real HyperFrames build.

Builds a synthetic 24 s short (test-pattern A-roll, synthetic words) with one graphic per component type
(+ a video split), runs `hyperframes check`, snapshots each graphic and tiles a contact sheet.
"""
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from .build import build
from .errors import CutmateError
from .hf import hf
from .media import run

WORDS_PER_SEG = 20


def _synthetic_rec(root: Path) -> Path:
    rec = root / "theme-check"
    out = rec / "out"
    (out / "work").mkdir(parents=True, exist_ok=True)
    (rec / "broll").mkdir(exist_ok=True)
    for dst, size, d in ((out / "aroll.mp4", "1080x1920", 24), (rec / "broll" / "clip.mp4", "1280x720", 3)):
        r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={d}",
                 "-f", "lavfi", "-i", f"sine=frequency=220:duration={d}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest", str(dst)])
        if r.returncode:
            raise CutmateError("ffmpeg failed creating theme-check media: " + " ".join(r.stderr.split())[-300:])
    img = Image.new("RGB", (1600, 1000), "#1e293b")
    ImageDraw.Draw(img).rectangle((80, 80, 1520, 920), outline="#7dd3fc", width=12)
    img.save(rec / "broll" / "page.png")
    words, timed = [], []
    for s in range(2):
        sid = f"S{s + 1}"
        timed.append({"id": sid, "start": s * 12.0, "end": (s + 1) * 12.0, "text": ""})
        for i in range(WORDS_PER_SEG):
            t = s * 12.0 + 0.2 + i * 0.58
            words.append({"seg": sid, "word": f"słowo{i}" if i % 5 else f"{i}%", "start": round(t, 2), "end": round(t + 0.4, 2)})
    (out / "work" / "aligned_words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    (out / "work" / "edl_timed.json").write_text(json.dumps(timed), encoding="utf-8")
    plan = {"captions": {"key": ["SŁOWO3"]}, "graphics": [
        {"type": "title", "at": "S1:słowo1", "until": "S1:słowo3", "kicker": "Kicker", "text": "Tytuł ąę"},
        {"type": "counter", "at": "S1:słowo6", "until": "S1:słowo8", "to": 75, "prefix": "-", "suffix": "%", "label": "TOKENÓW", "hit": True},
        {"type": "list", "head": "Lista", "items": [
            {"text": "Pierwszy", "at": "S1:słowo9"}, {"text": "Drugi punkt", "at": "S1:10%"},
            {"text": "Trzeci punkt", "at": "S1:słowo11"}, {"text": "Czwarty bardzo długi punkt", "at": "S1:słowo12"}],
         "until": "S1:słowo14"},
        {"type": "chip", "at": "S1:słowo16", "until": "S1:słowo18", "text": "Caveman"},
        {"type": "stamp", "at": "S2:słowo1", "until": "S2:słowo2", "text": "NIE."},
        {"type": "bars", "at": "S2:słowo3", "until": "S2:słowo6", "head": "Koszt", "illustrative": True,
         "rows": [{"label": "Przed", "value": 100}, {"label": "Po", "value": 60}, {"label": "Optymalnie", "value": 25}]},
        {"type": "point", "at": "S2:słowo7", "until": "S2:słowo8", "image": "broll/page.png", "corner": "tr"},
        {"type": "split", "from": "S2:słowo11", "to": "S2:słowo13", "media": "broll/page.png"},
        {"type": "split", "from": "S2:słowo16", "to": "S2:słowo18", "media": "broll/clip.mp4"},
    ]}
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return out


def theme_check(theme: str = "clean", workdir: Path | None = None, language: str = "pl") -> dict:
    root = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="cutmate-theme-"))
    out = _synthetic_rec(root)
    r = build(out, theme=theme, language=language)
    proj = r["project"]
    chk = run(hf("check"), cwd=proj)
    if chk.returncode:
        raise CutmateError(f"theme {theme!r} fails hyperframes check: " + " ".join((chk.stdout + chk.stderr).split())[-600:])
    snaps = proj / "snapshots"
    for old in snaps.glob("frame-*.png"):
        old.unlink()
    cps = list(r["checkpoints"])
    first, last = (0.2 + i * 0.58 for i in (9, 12))  # list: snapshot once all 4 items are in
    i = min(range(len(cps)), key=lambda k: abs(cps[k] - (first + 0.4)))
    cps[i] = round(last + 0.4, 2)
    at = ",".join(f"{t:.2f}" for t in sorted(cps))
    snap = run(hf("snapshot", "--at", at, "--no-end", "--describe", "false", "-o", "snapshots"), cwd=proj)
    shots = sorted(snaps.glob("frame-*.png"))
    if snap.returncode or len(shots) != len(cps):
        raise CutmateError("snapshot failed: " + " ".join((snap.stdout + snap.stderr).split())[-400:])
    tiles = [Image.open(p).convert("RGB").resize((270, 480)) for p in shots]
    sheet = Image.new("RGB", (270 * min(5, len(tiles)), 480 * ((len(tiles) + 4) // 5)), "black")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 5) * 270, (i // 5) * 480))
    sheet_path = out / f"theme-check-{theme}.png"
    sheet.save(sheet_path)
    return {"project": proj, "sheet": sheet_path, "snapshots": shots}
