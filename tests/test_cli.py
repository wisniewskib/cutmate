import pytest
import json
import os
import subprocess
import sys

from cutmate.cli import main
from conftest import make_clip


def test_cut_and_finalize_via_cli(tmp_path):
    rec = tmp_path / "rec"
    make_clip(rec / "take1.mp4")
    (rec / "out").mkdir()
    edl = rec / "out" / "edl.json"
    edl.write_text(json.dumps({"format": "9:16", "segments": [
        {"id": "S1", "file": "take1.mp4", "in": 0.0, "out": 1.0, "text": "raz"}]}), encoding="utf-8")
    assert main(["cut", str(edl)]) == 0
    assert main(["finalize", str(rec / "out" / "aroll.mp4"), str(rec / "out" / "final.mp4"), "--check", "0.5"]) == 0
    assert (rec / "out" / "check_0_50.png").exists()


def test_sheet_via_cli(clip, tmp_path):
    assert main(["sheet", str(clip), "-o", str(tmp_path / "s.png")]) == 0
    assert (tmp_path / "s.png").exists()


def test_user_error_is_one_line(tmp_path, capsys):
    assert main(["transcribe", str(tmp_path), "--backend", "groq"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("cutmate: no video files") and "Traceback" not in err


def test_cli_survives_cp1252(tmp_path):
    d = tmp_path / "pusty ąęłż"
    d.mkdir()
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    r = subprocess.run([sys.executable, "-m", "cutmate.cli", "transcribe", str(d), "--backend", "groq"],
                       capture_output=True, env=env)
    assert r.returncode == 2
    assert b"Traceback" not in r.stderr and b"no video files" in r.stderr


def test_align_checks_required_files(tmp_path, capsys):
    """Test that align validates EDL, edl_timed.json, and aroll.mp4 exist with specific error messages."""
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    edl = out_dir / "edl.json"
    edl_nonexistent = out_dir / "nonexistent.json"

    # Test 0: missing EDL file itself
    assert main(["align", str(edl_nonexistent)]) == 2
    err = capsys.readouterr().err
    assert "EDL file not found" in err
    assert str(edl_nonexistent) in err

    # Create EDL for remaining tests
    edl.write_text(json.dumps({"format": "9:16", "segments": [
        {"id": "S1", "file": "take1.mp4", "in": 0.0, "out": 1.0, "text": "raz"}]}), encoding="utf-8")

    # Test 1: missing work/edl_timed.json
    assert main(["align", str(edl)]) == 2
    err = capsys.readouterr().err
    assert "EDL timed file not found" in err
    assert "run `cutmate cut` first" in err
    assert str(out_dir / "work" / "edl_timed.json") in err

    # Test 2: missing aroll.mp4
    (out_dir / "work").mkdir(parents=True)
    edl_timed = out_dir / "work" / "edl_timed.json"
    edl_timed.write_text(json.dumps([{"id": "S1", "in": 0.0, "out": 1.0, "text": "raz"}]), encoding="utf-8")

    assert main(["align", str(edl)]) == 2
    err = capsys.readouterr().err
    assert "A-roll file not found" in err
    assert "run `cutmate cut` first" in err
    assert str(out_dir / "aroll.mp4") in err


def test_align_missing_edl_error(tmp_path, capsys):
    """Test that align reports missing EDL file."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    edl = out_dir / "edl.json"

    assert main(["align", str(edl)]) == 2
    err = capsys.readouterr().err
    assert "EDL file not found" in err
    assert "cutmate: " in err


def test_qa_no_asr_missing_video(tmp_path, capsys):
    """Test that qa --no-asr with missing final.mp4 reports error and backend=None doesn't crash."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    assert main(["qa", str(out_dir), "--no-asr"]) == 2
    err = capsys.readouterr().err
    assert "cutmate:" in err
    assert "cutmate finalize" in err


def test_align_import_error_handling(tmp_path, capsys, monkeypatch):
    """Test that align converts ImportError to CutmateError when alignment models are missing."""
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)

    # Create dummy edl.json
    edl = out_dir / "edl.json"
    edl.write_text(json.dumps({"format": "9:16", "segments": [
        {"id": "S1", "file": "take1.mp4", "in": 0.0, "out": 1.0, "text": "raz"}]}), encoding="utf-8")

    # Create dummy work/edl_timed.json and aroll.mp4
    (out_dir / "work").mkdir(parents=True)
    edl_timed = out_dir / "work" / "edl_timed.json"
    edl_timed.write_text(json.dumps([{"id": "S1", "in": 0.0, "out": 1.0, "text": "raz"}]), encoding="utf-8")
    aroll = out_dir / "aroll.mp4"
    aroll.write_text("dummy", encoding="utf-8")

    # Monkeypatch run_align to raise ImportError
    import cutmate.align
    def mock_run_align(edl_path, language):
        raise ImportError("No module named 'torch'")

    monkeypatch.setattr("cutmate.align.run_align", mock_run_align)

    # align should convert ImportError to CutmateError
    assert main(["align", str(edl)]) == 2
    err = capsys.readouterr().err
    assert "alignment models not installed" in err
    assert "Traceback" not in err


def test_nonexistent_folder_is_one_line(tmp_path, capsys):
    assert main(["transcribe", str(tmp_path / "nope"), "--backend", "groq"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("cutmate: not a folder") and "Traceback" not in err


def test_oserror_is_one_line(tmp_path, capsys, monkeypatch):
    def boom(*a, **k):
        raise PermissionError("denied\n  on\tthing")
    monkeypatch.setattr("cutmate.cut.cut_aroll", boom)
    assert main(["cut", str(tmp_path / "edl.json")]) == 2
    err = capsys.readouterr().err
    assert err == "cutmate: denied on thing\n"


@pytest.mark.parametrize("argv", [
    ["finalize", "a.mp4", "b.mp4", "--check", "abc"],
    ["finalize", "a.mp4", "b.mp4", "--format", "4:3"],
    ["sheet", "a.mp4", "-o", "s.png", "--step", "0"],
    ["sheet", "a.mp4", "-o", "s.png", "--cols", "0"],
])
def test_bad_args_are_argparse_errors(argv, capsys):
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 2
    assert "Traceback" not in capsys.readouterr().err


def test_formats_cli_landscape(tmp_path, capsys):
    import subprocess
    from conftest import make_clip
    from cutmate.cli import main
    rec = tmp_path / "rec"
    src = make_clip(tmp_path / "src.mp4", dur=1.0, size="320x180")
    rec.mkdir()
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-display_rotation", "-90", "-i", str(src),
                    "-c", "copy", str(rec / "IMG_1.MOV")], check=True)
    make_clip(rec / "IMG_2.mp4", dur=1.0, size="320x180")
    assert main(["formats", str(rec)]) == 0
    out = capsys.readouterr().out
    assert "IMG_1.MOV: 180x320 9:16" in out and "IMG_2.mp4: 320x180 16:9" in out and "format: mixed" in out


def test_formats_cli_single(tmp_path, capsys):
    from conftest import make_clip
    from cutmate.cli import main
    make_clip(tmp_path / "rec" / "a.mp4", dur=1.0, size="320x180")
    assert main(["formats", str(tmp_path / "rec")]) == 0
    assert capsys.readouterr().out.strip().endswith("format: 16:9")
