import subprocess
from pathlib import Path

import pytest


def _expr(gaps, amp, freq=440):
    cond = "+".join(f"between(t,{a},{b})" for a, b in gaps) or "0"
    return f"if({cond},0,{amp}*sin(2*PI*{freq}*t))"


def make_clip(path, dur=3.0, size="1080x1920", gaps=((1.0, 1.5),), audio=True, amp=0.3):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={dur}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"aevalsrc='{_expr(gaps, amp)}':s=48000:d={dur}", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(dur), str(path)]
    subprocess.run(cmd, check=True)
    return path


def make_wav(path, dur=2.0, gaps=(), amp=0.3):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"aevalsrc='{_expr(gaps, amp)}':s=16000:d={dur}", "-ac", "1", str(path)], check=True)
    return path


def pytest_sessionstart(session):
    """gsap's licence text does not clearly allow redistribution, so it is not committed: fetch it once (sha-checked)."""
    from cutmate.effects import VENDOR
    from cutmate.paths import vendor_dir
    if not (vendor_dir() / VENDOR["gsap"]).is_dir():
        pytest.exit(f"{VENDOR['gsap']} is not in {vendor_dir()} — run once: .venv/bin/python tools/vendor_libs.py --only gsap (Windows: .venv\\Scripts\\python.exe)", 2)


@pytest.fixture(autouse=True)
def isolated_cutmate_home(tmp_path, monkeypatch):
    """Never read the developer's real ~/.cutmate/config.json in tests."""
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "cutmate-home"))


@pytest.fixture
def clip(tmp_path):
    return make_clip(tmp_path / "rec" / "take1.mp4")


def make_pre3b_theme(name: str = "old") -> Path:
    """A user theme copied from the frozen pre-3b clean (tests/fixtures/pre3b_clean + the bundled Inter files): no
    `--font-display`, no `cutmate:font` blocks, no theme.json `direction`, fonts/OFL.txt."""
    import shutil
    from cutmate import config
    from cutmate.paths import plugin_root
    dst = config.home() / "themes" / name
    shutil.copytree(Path(__file__).parent / "fixtures" / "pre3b_clean", dst)
    fonts = plugin_root() / "themes" / "clean" / "fonts"
    (dst / "fonts").mkdir()
    for p in fonts.glob("Inter-*.ttf"):
        shutil.copyfile(p, dst / "fonts" / p.name)
    shutil.copyfile(fonts / "OFL-inter.txt", dst / "fonts" / "OFL.txt")
    frame = dst / "frame.md"
    frame.write_text(frame.read_text(encoding="utf-8").replace("name: clean", f"name: {name}", 1), encoding="utf-8")
    return dst
