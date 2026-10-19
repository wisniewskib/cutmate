"""Contract test for a theme pack: every component renders in a real HyperFrames build.

Builds a synthetic video in the given format (test-pattern A-roll, synthetic words, 48 s) with one graphic per
component type of that format (9:16: + a video split, the four stock explainers in split panels and a burst; 16:9: + a video pip, a chapter plate, a third
segment with the stock energy-ball effect on a synthetic hand track, a bg and a side, and a fourth (punched-in)
segment with a bg and a side drawn by a small DOM effect and a showcase-3d), runs `hyperframes check`, snapshots each
graphic (custom effects also at their middle, as the edit skill asks) and tiles a contact sheet.
"""
import json
import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from .build import build, checkpoint
from .errors import CutmateError
from .hf import check, hf
from .media import run
from .plan import load_plan

WORDS_PER_SEG = 20

GRAPHICS_916 = [
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
    # stock explainers in the split panel, and a one-shot burst at a fixed point
    {"type": "split", "from": "S3:słowo1", "to": "S3:słowo6", "effect": "stat-card",
     "params": {"value": 75, "suffix": "%", "label": "mniej tokenów w każdej odpowiedzi", "note": "dane przykładowe"}},
    {"type": "split", "from": "S3:słowo11", "to": "S3:słowo16", "effect": "flow",
     "params": {"title": "Jak to działa", "nodes": ["Nagranie", "Transkrypcja", "Plan", "Gotowy film"]}},
    {"type": "custom", "name": "burst", "from": "S3:słowo18", "to": "S3:słowo19", "params": {"x": 760, "y": 1240}},
    {"type": "split", "from": "S4:słowo1", "to": "S4:słowo6", "effect": "ui-mock",
     "params": {"kind": "chat", "title": "Asystent", "lines": [
         {"who": "user", "text": "Wytnij pauzy z nagrania"}, {"who": "ai", "text": "Gotowe: usunąłem 14 pauz, film jest krótszy o 38 s."}]}},
    {"type": "split", "from": "S4:słowo11", "to": "S4:słowo16", "effect": "iso-machine",
     "params": {"title": "Od nagrania do filmu", "token": "cube", "counter": {"to": 12, "label": "klipów"}, "parts": [
         {"label": "Wejście", "shape": "funnel"}, {"label": "Cięcie", "shape": "cylinder"},
         {"label": "Podgląd", "shape": "screen"}, {"label": "Napęd", "shape": "gear"}]}},
]
GRAPHICS_169 = [
    {"type": "title", "at": "S1:słowo1", "until": "S1:słowo3", "kicker": "Kicker", "text": "Tytuł ąę"},
    {"type": "counter", "at": "S1:słowo6", "until": "S1:słowo8", "to": 75, "prefix": "-", "suffix": "%", "label": "TOKENÓW", "hit": True},
    {"type": "list", "head": "Lista", "items": [
        {"text": "Pierwszy", "at": "S1:słowo9"}, {"text": "Drugi punkt", "at": "S1:10%"},
        {"text": "Trzeci punkt", "at": "S1:słowo11"}, {"text": "Czwarty bardzo długi punkt", "at": "S1:słowo12"}],
     "until": "S1:słowo14"},
    {"type": "chip", "at": "S1:słowo16", "until": "S1:słowo18", "text": "Caveman"},
    {"type": "custom", "name": "hand-sparks", "from": "S2:słowo1", "to": "S2:słowo2",
     "params": {"mode": "sparks", "link": True, "x": 1300, "y": 600}},
    {"type": "lower-third", "at": "S2:słowo3", "until": "S2:słowo4", "name": "Anna Nowak", "role": "AI · wideo"},
    {"type": "stamp", "at": "S2:słowo6", "until": "S2:słowo7", "text": "NIE."},
    {"type": "bars", "at": "S2:słowo8", "until": "S2:słowo9", "head": "Koszt", "illustrative": True,
     "rows": [{"label": "Przed", "value": 100}, {"label": "Po", "value": 60}, {"label": "Optymalnie", "value": 25}]},
    {"type": "point", "at": "S2:10%", "until": "S2:słowo11", "image": "broll/page.png", "corner": "tr"},
    {"type": "pip", "from": "S2:słowo12", "to": "S2:słowo14", "media": "broll/page.png"},
    {"type": "pip", "from": "S2:słowo16", "to": "S2:słowo18", "media": "broll/clip.mp4", "corner": "bl", "fit": "contain"},
    {"type": "custom", "name": "energy-ball", "from": "S3:słowo1", "to": "S3:słowo6", "follow": "hand"},
    {"type": "bg", "from": "S3:słowo8", "to": "S3:słowo11", "media": "broll/page.png"},
    {"type": "side", "from": "S3:słowo13", "to": "S3:słowo17", "media": "broll/page.png", "speaker": "right"},
    {"type": "bg", "from": "S4:słowo1", "to": "S4:słowo2", "effect": "tc-fx"},              # ~1 s: bg removal is slow
    {"type": "side", "from": "S4:słowo6", "to": "S4:słowo9", "effect": "tc-fx", "speaker": "left"},
    {"type": "custom", "name": "showcase-3d", "from": "S4:słowo12", "to": "S4:słowo18", "params": {"shape": "torus-knot"}},
]
# a DOM effect for the bg / side "effect" path: a full-size gradient and a dot that starts half outside the left edge
# (in the side panel it must be clipped at the panel's edge)
TC_FX = """<style>ROOT .tc { position: absolute; inset: 0; background: linear-gradient(135deg, #0f172a, #1d4ed8 60%, #7dd3fc); }
ROOT .tc-dot { position: absolute; left: -120px; top: 40%; width: 240px; height: 240px; border-radius: 50%; background: #f472b6; }</style>
<markup><div class="tc"><div class="tc-dot"></div></div></markup>
<script>
const dot = root.querySelector(".tc-dot");
tl.fromTo(dot, { x: 0 }, { x: P.w, duration: Math.max(0.3, P.end - P.at), ease: "none" }, P.at);
</script>
"""
CHAPTERS_169 = [{"at": "S1:0%", "title": "Intro"}, {"at": "S2:0%", "title": "Drugi rozdział ąę"}]
SEG = 12.0
LOOK = ("title", "counter", "list", "chip", "stamp", "bars")  # snapshotted at their entrance as well


def _hand_track(a: float, b: float) -> list[list[float]]:
    """A hand sweeping left→right across [a, b] with a small bob, sampled every 1/15 s ([t, x, y, conf])."""
    n = round((b - a) * 15)
    return [[round(a + i / 15, 4), round(0.2 + 0.6 * i / n, 4), round(0.62 + 0.04 * math.sin(i / 4), 4), 0.9]
            for i in range(n + 1)]


def _synthetic_rec(root: Path, fmt: str = "9:16", clip: Path | None = None) -> Path:
    rec = root / f"theme-check-{fmt.replace(':', 'x')}"
    out = rec / "out"
    (out / "work").mkdir(parents=True, exist_ok=True)
    (rec / "broll").mkdir(exist_ok=True)
    aroll_size = "1920x1080" if fmt == "16:9" else "1080x1920"
    nseg = 4
    (out / "edl.json").write_text(json.dumps({"format": fmt, "segments": []}), encoding="utf-8")
    for dst, size, d in ((out / "aroll.mp4", aroll_size, round(nseg * SEG)), (rec / "broll" / "clip.mp4", "1280x720", 3)):
        if clip is not None and dst.name == "aroll.mp4":     # the user's own footage, filling the frame, looped
            w, h = size.split("x")
            src = ["-stream_loop", "-1", "-i", str(clip)]
            vf = ["-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30", "-map", "0:v:0", "-map", "1:a:0"]
            cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", *src, "-f", "lavfi", "-i", f"sine=frequency=220:duration={d}",
                   *vf, "-t", str(d), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dst)]
        else:
            cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={d}",
                   "-f", "lavfi", "-i", f"sine=frequency=220:duration={d}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-shortest", str(dst)]
        r = run(cmd)
        if r.returncode:
            raise CutmateError("ffmpeg failed creating theme-check media: " + " ".join(r.stderr.split())[-300:])
    img = Image.new("RGB", (1600, 1000), "#1e293b")
    ImageDraw.Draw(img).rectangle((80, 80, 1520, 920), outline="#7dd3fc", width=12)
    img.save(rec / "broll" / "page.png")
    words, timed = [], []
    for s in range(nseg):
        sid = f"S{s + 1}"
        timed.append({"id": sid, "start": s * SEG, "end": (s + 1) * SEG, "text": ""})
        for i in range(WORDS_PER_SEG):
            t = s * SEG + 0.2 + i * 0.58
            words.append({"seg": sid, "word": f"słowo{i}" if i % 5 else f"{i}%", "start": round(t, 2), "end": round(t + 0.4, 2)})
    (out / "work" / "aligned_words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    (out / "work" / "edl_timed.json").write_text(json.dumps(timed), encoding="utf-8")
    plan = {"captions": {"key": ["SŁOWO3"]}, "graphics": GRAPHICS_169 if fmt == "16:9" else GRAPHICS_916}
    if fmt == "16:9":
        plan["chapters"] = CHAPTERS_169
        plan["face"] = {"S1": [0.5, 0.35], "S2": [0.45, 0.35], "S3": [0.5, 0.35], "S4": [0.5, 0.35]}
        (out / "custom").mkdir(exist_ok=True)
        (out / "custom" / "tc-fx.html").write_text(TC_FX, encoding="utf-8")
        tracks = {"tracks": {"hand_right": _hand_track(2 * SEG + 0.6, 2 * SEG + 4.2)}}
        (out / "work" / "tracks.json").write_text(json.dumps(tracks), encoding="utf-8")
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return out


def snapshot_times(graphics: list, checkpoints: list[float]) -> tuple[list[float], list[tuple[float, str, str]]]:
    """Snapshot times and their (t, type, kind) labels: the entrance of every LOOK component, the middle of each custom
    effect, every graphic settled, plus the build checkpoints. The first claim on a time wins; a LOOK label that clashes
    is nudged by 0.05 s instead (the contact sheet needs a tile of every LOOK type), any other clash shares the tile."""
    named: dict[float, tuple[str, str]] = {}

    def claim(t: float, label: tuple[str, str]) -> None:
        if label[0] in LOOK:
            while t in named and named[t] != label:
                t = round(t + 0.05, 2)
        named.setdefault(t, label)
    for g in graphics:
        if g.type in LOOK:
            claim(round(g.start + 0.1, 2), (g.type, "entrance"))
    for g in graphics:
        if g.type == "custom":
            claim(round((g.start + g.end) / 2, 2), (g.type, "mid"))
    for g in graphics:
        claim(checkpoint(g), (g.type, "settled"))
    cps = sorted(set(checkpoints) | set(named))
    return cps, [(t, *named.get(t, ("other", "settled"))) for t in cps]


def theme_check(theme: str = "clean", workdir: Path | None = None, language: str = "pl", fmt: str = "9:16",
                clip: Path | None = None) -> dict:
    """Build the synthetic video, run `hyperframes check`, snapshot it and tile the sheet.

    Snapshots: every graphic settled (build.checkpoint), the middle of each custom effect, and the entrance
    (start + 0.1 s) of every LOOK component. `labels` = [(t, type, "entrance" | "settled" | "mid")], aligned with
    `snapshots`."""
    root = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="cutmate-theme-"))
    out = _synthetic_rec(root, fmt, clip)
    r = build(out, theme=theme, language=language, captions={"16:9": "both"})
    proj = r["project"]
    chk = check(proj, run, hf)
    if chk.returncode:
        raise CutmateError(f"theme {theme!r} fails hyperframes check: " + " ".join((chk.stdout + chk.stderr).split())[-600:])
    snaps = proj / "snapshots"
    for old in snaps.glob("frame-*.png"):
        old.unlink()
    cps, labels = snapshot_times(load_plan(out).graphics, r["checkpoints"])
    at = ",".join(f"{t:.2f}" for t in cps)
    snap = run(hf("snapshot", "--at", at, "--no-end", "--describe", "false", "-o", "snapshots"), cwd=proj)
    shots = sorted(snaps.glob("frame-*.png"))
    if snap.returncode or len(shots) != len(cps):
        raise CutmateError("snapshot failed: " + " ".join((snap.stdout + snap.stderr).split())[-400:])
    tw, th = (480, 270) if fmt == "16:9" else (270, 480)
    tiles = []
    for p in shots:
        with Image.open(p) as im:
            tiles.append(im.convert("RGB").resize((tw, th)))
    sheet = Image.new("RGB", (tw * min(5, len(tiles)), th * ((len(tiles) + 4) // 5)), "black")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 5) * tw, (i // 5) * th))
    sheet_path = out / f"theme-check-{Path(theme).name}-{fmt.replace(':', 'x')}.png"
    sheet.save(sheet_path)
    return {"project": proj, "sheet": sheet_path, "snapshots": shots, "times": cps, "labels": labels}
