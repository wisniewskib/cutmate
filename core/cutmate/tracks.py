"""Where the speaker's face, hands and pointing are over time (out/work/tracks.json), so effects can follow them.

Samples are [t, x, y, conf] with x, y as fractions of the frame; t is A-roll seconds."""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from statistics import median

import numpy as np
import requests

from .config import home
from .errors import CutmateError
from .media import probe_video, require_ffmpeg

TRACKS = ("face", "hand_left", "hand_right", "point_left", "point_right")


def pointing_target(wrist: tuple, tip: tuple) -> tuple[float, float]:
    """Where a pointing hand aims: index tip pushed 2x further along wrist -> tip, clamped to the frame."""
    return tuple(min(0.98, max(0.02, tip[i] + 2.0 * (tip[i] - wrist[i]))) for i in (0, 1))


def is_extended(wrist: tuple, shoulder: tuple, torso: float) -> bool:
    """Arm stretched out: wrist-shoulder distance > 0.6 x torso length, and not just hanging down
    (a relaxed arm is long too, but its wrist sits more than 0.75 torso below the shoulder).
    All points in the same isotropic units (x scaled by the frame aspect)."""
    long_ = float(np.hypot(wrist[0] - shoulder[0], wrist[1] - shoulder[1])) > 0.6 * torso
    return bool(long_ and wrist[1] - shoulder[1] < 0.75 * torso)


def pointing(lm: dict, wrist: int, tip: int, shoulder: int, aspect: float, vis: float = 0.5) -> tuple | None:
    """(x, y, conf) of where one arm points; conf 1.0 = arm extended. lm = {index: (x, y, visibility)} as frame
    fractions; aspect = width / height (distances are measured in pixels, not fractions). Torso = shoulder midpoint ->
    hip midpoint, or 1.3 x shoulder width when the hips are out of frame (close-ups). None when the arm is not visible."""
    if any(lm[i][2] < vis for i in (wrist, tip, shoulder, 11, 12)):
        return None
    P = lambda i: (lm[i][0] * aspect, lm[i][1])  # noqa: E731
    sl, sr = P(11), P(12)
    if lm[23][2] >= vis and lm[24][2] >= vis:
        hl, hr = P(23), P(24)
        torso = float(np.hypot((sl[0] + sr[0] - hl[0] - hr[0]) / 2, (sl[1] + sr[1] - hl[1] - hr[1]) / 2))
    else:
        torso = 1.3 * float(np.hypot(sl[0] - sr[0], sl[1] - sr[1]))
    x, y = pointing_target(lm[wrist][:2], lm[tip][:2])
    return (x, y, 1.0 if is_extended(P(wrist), P(shoulder), torso) else 0.0)


def gesture_at(tracks: dict, t: float, window: float = 0.5) -> dict | None:
    """The extended pointing sample nearest t (within +-window); ties go to the one farther from centre.
    `side` is the screen side the viewer sees (x < 0.5 -> left), not the speaker's anatomical side."""
    best = None
    for hand in ("point_left", "point_right"):
        for s in tracks.get(hand, []):
            d = abs(s[0] - t)
            if s[3] >= 0.5 and d <= window + 1e-9:
                key = (round(d, 6), -abs(s[1] - 0.5))
                if best is None or key < best[0]:
                    best = (key, s, hand)
    if best is None:
        return None
    _, s, hand = best
    return {"x": s[1], "y": s[2], "side": "left" if s[1] < 0.5 else "right", "hand": hand}


def smooth(samples: list[list[float]], k: int = 5) -> list[list[float]]:
    h = k // 2
    out = []
    for i, (t, _, _, c) in enumerate(samples):
        win = samples[max(0, i - h): i + h + 1]
        out.append([t, median(p[1] for p in win), median(p[2] for p in win), c])
    return out


def fill_gaps(samples: list[list[float]], max_gap: float = 0.5, step: float = 1 / 15) -> list[list[float]]:
    out = []
    for a, b in zip(samples, samples[1:]):
        out.append(a)
        gap = b[0] - a[0]
        if step * 1.5 < gap <= max_gap + 1e-9:
            n = round(gap / step)
            for j in range(1, n):
                f = j / n
                out.append([round(a[0] + gap * f, 4), a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, 0.0])
    if samples:
        out.append(samples[-1])
    return out


def _in(samples, a, b):
    return [p for p in samples if a <= p[0] <= b]


def pick_hand(tracks: dict, a: float, b: float) -> str:
    left = len(_in(tracks.get("hand_left", []), a, b))
    right = len(_in(tracks.get("hand_right", []), a, b))
    return "hand_left" if left > right else "hand_right"


def face_median(tracks: dict, a: float, b: float) -> list[float] | None:
    s = _in(tracks.get("face", []), a, b)
    if not s:
        return None
    return [round(median(p[1] for p in s), 3), round(median(p[2] for p in s), 3)]


def load_tracks(out_dir: Path) -> dict | None:
    p = Path(out_dir) / "work" / "tracks.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        raise CutmateError(f"{p}: broken file — run `cutmate track --force`") from None
    if not (isinstance(data, dict) and isinstance(data.get("tracks"), dict)
            and all(isinstance(v, list) for v in data["tracks"].values())):
        raise CutmateError(f"{p}: broken file (needs {{\"tracks\": {{name: [samples]}}}}) — run `cutmate track --force`")
    return data


def tracks_fresh(out_dir: Path) -> bool:
    """tracks.json exists and is not older than aroll.mp4 (a re-cut makes old tracks point at the wrong frames)."""
    out = Path(out_dir)
    p, a = out / "work" / "tracks.json", out / "aroll.mp4"
    return p.exists() and (not a.exists() or p.stat().st_mtime >= a.stat().st_mtime)


def save_tracks(out_dir: Path, data: dict) -> Path:
    p = Path(out_dir) / "work" / "tracks.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(p)
    return p


MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/"
             "float16/1/pose_landmarker_lite.task")
MODEL_SHA256 = "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a"


def model_path() -> Path:
    p = home() / "models" / "pose_landmarker_lite.task"
    if p.exists():
        return p
    r = requests.get(MODEL_URL, timeout=120)
    r.raise_for_status()
    if hashlib.sha256(r.content).hexdigest() != MODEL_SHA256:
        raise CutmateError(f"downloaded pose model failed the SHA-256 check ({MODEL_URL}) — try again later")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(r.content)
    tmp.replace(p)
    return p


class PoseDetector:
    """MediaPipe Pose Landmarker (lite): nose = face, wrist+index midpoint = hand (speaker's anatomical sides)."""

    VIS = 0.5

    def __init__(self):
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode
        except ImportError:
            raise CutmateError("mediapipe not installed. Run /cutmate:setup.") from None
        self._mp = mp
        opts = PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(model_path())),
                                     running_mode=RunningMode.VIDEO, num_poses=1)
        self._lm = PoseLandmarker.create_from_options(opts)

    def close(self) -> None:
        self._lm.close()

    def __call__(self, rgb: np.ndarray, t: float) -> dict:
        img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        res = self._lm.detect_for_video(img, int(round(t * 1000)))
        if not res.pose_landmarks:
            return {n: None for n in TRACKS}
        L = res.pose_landmarks[0]

        def pt(*ids):
            if any(getattr(L[i], "visibility", 1.0) < self.VIS for i in ids):
                return None
            return (sum(L[i].x for i in ids) / len(ids), sum(L[i].y for i in ids) / len(ids),
                    min(getattr(L[i], "visibility", 1.0) for i in ids))

        lm = {i: (L[i].x, L[i].y, getattr(L[i], "visibility", 1.0)) for i in (11, 12, 15, 16, 19, 20, 23, 24)}
        aspect = rgb.shape[1] / rgb.shape[0]
        point = lambda w, tip, sh: pointing(lm, w, tip, sh, aspect, self.VIS)  # noqa: E731
        return {"face": pt(0), "hand_left": pt(15, 19), "hand_right": pt(16, 20),
                "point_left": point(15, 19, 11), "point_right": point(16, 20, 12)}


def analyze(video: Path, detector, every: int = 2, width: int = 640) -> dict:
    require_ffmpeg()
    info = probe_video(video)
    W, H = int(info["width"]), int(info["height"])
    w = width
    h = int(round(H * w / W / 2) * 2)
    err = tempfile.TemporaryFile()                     # a file, not a pipe: a chatty ffmpeg cannot block the read
    proc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-vf", f"fps=30,scale={w}:{h}",
                             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=err)
    raw = {n: [] for n in TRACKS}
    size, i = w * h * 3, 0
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            if i % every == 0:
                t = i / 30
                rgb = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
                for name, v in detector(rgb, t).items():
                    if v is not None and name in raw:
                        raw[name].append([round(t, 4), float(v[0]), float(v[1]), float(v[2])])
            i += 1
    finally:
        proc.stdout.close()
        proc.wait()
        err.seek(0)
        msg = " ".join(err.read().decode("utf-8", "replace").split())[-300:]
        err.close()
    if proc.returncode or i == 0:
        raise CutmateError(f"cannot read frames from {video} (ffmpeg exit {proc.returncode}): {msg or 'no frames'}")
    step = every / 30
    return {"fps": round(30 / every), "w": W, "h": H,
            "tracks": {n: fill_gaps(smooth(s), 0.5, step) for n, s in raw.items()}}


def _complete(p: Path) -> bool:
    """tracks.json has every track this version writes (a file from before the pointing tracks does not)."""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    return isinstance(data, dict) and isinstance(data.get("tracks"), dict) and all(n in data["tracks"] for n in TRACKS)


def track(out_dir: Path, detector=None, force: bool = False) -> Path:
    out = Path(out_dir)
    src = out / "aroll.mp4"
    if not src.exists():
        raise CutmateError(f"{src} not found — run `cutmate cut` first")
    p = out / "work" / "tracks.json"
    if not force and p.exists() and p.stat().st_mtime >= src.stat().st_mtime and _complete(p):
        return p
    own = detector is None
    det = detector or PoseDetector()
    try:
        return save_tracks(out, analyze(src, det))
    finally:
        if own:
            det.close()
