from conftest import make_wav
from cutmate.cli import main
from cutmate.takes import blobs, rms_bins


def test_rms_bins_and_blobs(tmp_path):
    wav = make_wav(tmp_path / "a.wav", dur=2.0, gaps=((0.5, 1.0),))
    bins = rms_bins(wav, 0.0, 2.0, 0.05)
    assert len(bins) == 40 and bins[0][0] == 0.0
    quiet = [db for t, db in bins if 0.55 <= t < 0.95]
    loud = [db for t, db in bins if t < 0.45]
    assert max(quiet) < -60 and min(loud) > -20
    b = blobs(bins)
    assert len(b) == 2
    assert abs(b[0][1] - 0.5) < 0.06 and abs(b[1][0] - 1.0) < 0.06


def test_rms_cli(tmp_path, capsys):
    wav = make_wav(tmp_path / "a.wav", dur=1.0)
    assert main(["rms", str(wav), "--start", "0", "--end", "1", "--bin", "0.1"]) == 0
    out = capsys.readouterr().out
    assert out.count("\n") >= 11 and "blobs:" in out


def test_probe_cli_uses_backend(tmp_path, capsys, monkeypatch):
    from cutmate import cli
    from cutmate.transcript import Transcript, Word

    class Fake:
        name = "fake"

        def transcribe(self, wav, language, prompt=None):
            return Transcript(language, [Word("na", 0.1, 0.3), Word("na", 0.4, 0.6)], "fake")

    monkeypatch.setattr(cli, "get_backend", lambda name: Fake())
    wav = make_wav(tmp_path / "a.wav", dur=3.0)
    assert main(["probe", str(wav), "--start", "1.0", "--end", "2.0", "--backend", "groq"]) == 0
    assert "na@1.10-1.30 na@1.40-1.60" in capsys.readouterr().out
