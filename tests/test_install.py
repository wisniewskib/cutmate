import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOP = {"os", "distro", "arch", "pkg", "gpu", "disk_free_gb", "tools", "cutmate", "missing", "install"}
GPU = {"kind", "name", "vram_mb", "driver"}
TOOLS = {"ffmpeg", "python", "python_bin", "python_venv", "node", "npx", "heygen"}
UTILS = ["uname", "df", "awk", "sed", "grep", "head", "tr", "cat"]


def fake_bin(tmp_path, tools):
    b = tmp_path / "bin"
    b.mkdir()
    for u in UTILS:
        (b / u).symlink_to(shutil.which(u))
    for name, body in tools.items():
        p = b / name
        p.write_text("#!/bin/sh\n" + body + "\n")
        p.chmod(0o755)
    return b


def run_sh(tmp_path, tools, cutmate_home=None):
    b = fake_bin(tmp_path, tools)
    env = {"PATH": str(b), "HOME": str(tmp_path), "CUTMATE_HOME": str(cutmate_home or tmp_path / ".cutmate")}
    out = subprocess.run([shutil.which("bash"), str(ROOT / "install/detect.sh")], env=env,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


FFMPEG = 'echo "ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023"'


def py(ver, venv_ok):
    return ('case "$1" in --version) echo "Python %s";; *) exit %d;; esac' % (ver, 0 if venv_ok else 1))


def test_detect_sh_json_real():
    out = subprocess.run([shutil.which("bash"), str(ROOT / "install/detect.sh")],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    assert set(d) == TOP
    assert set(d["gpu"]) == GPU
    assert set(d["tools"]) == TOOLS
    assert d["os"] == "linux"


def test_detect_sh_reports_missing(tmp_path):
    d = run_sh(tmp_path, {"ffmpeg": FFMPEG, "python3": py("3.9.7", True),
                          "node": 'echo v18.19.0', "apt-get": ""})
    assert d["missing"] == ["python", "node"]
    assert d["install"] == ["sudo apt-get install -y python3 python3-venv",
                            "sudo snap install node --classic --channel=22/stable"]
    assert d["pkg"] == "apt"
    assert d["gpu"]["kind"] == "none"
    assert d["tools"]["ffmpeg"] == "6.1.1-3ubuntu5"


def test_detect_sh_no_venv(tmp_path):
    d = run_sh(tmp_path, {"ffmpeg": FFMPEG, "python3": py("3.12.3", False),
                          "node": 'echo v22.11.0', "apt-get": ""})
    assert d["missing"] == ["python-venv"]
    assert d["install"] == ["sudo apt-get install -y python3-venv"]
    assert d["tools"]["python_venv"] is False


def test_detect_sh_nvidia(tmp_path):
    d = run_sh(tmp_path, {"nvidia-smi": 'echo "NVIDIA GeForce GTX 1660 SUPER, 6144, 595.99.02"'})
    assert d["gpu"] == {"kind": "nvidia", "name": "NVIDIA GeForce GTX 1660 SUPER",
                        "vram_mb": 6144, "driver": "595.99.02"}


def test_detect_sh_cutmate_home(tmp_path):
    home = tmp_path / "cm"
    home.mkdir()
    (home / "config.json").write_text("{}")
    d = run_sh(tmp_path, {}, cutmate_home=home)
    assert d["cutmate"] == {"home": str(home), "venv": False, "config": True}


def test_detect_ps1_parity():
    text = (ROOT / "install/detect.ps1").read_text(encoding="utf-8")
    for k in TOP | GPU | TOOLS:
        assert k in text, k
    assert "winget install -e --id OpenJS.NodeJS.LTS" in text


@pytest.mark.skipif(not shutil.which("pwsh"), reason="pwsh not installed")
def test_detect_ps1_runs():
    out = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-File", str(ROOT / "install/detect.ps1")],
                         capture_output=True, text=True, check=True).stdout
    assert set(json.loads(out)) == TOP
