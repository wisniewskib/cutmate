import numpy as np
import pytest

from cutmate import media
from cutmate.errors import MediaError
from conftest import make_clip, make_wav


def test_duration_and_audio(clip):
    assert abs(media.duration(clip) - 3.0) < 0.1
    assert media.has_audio(clip)


def test_has_audio_false(tmp_path):
    silent = make_clip(tmp_path / "noaudio.mp4", audio=False)
    assert not media.has_audio(silent)


def test_extract_wav_and_silences(clip, tmp_path):
    wav = media.extract_wav(clip, tmp_path / "a.wav")
    sil = media.silences(wav)
    assert len(sil) == 1
    a, b = sil[0]
    assert abs(a - 1.0) < 0.06 and abs(b - 1.5) < 0.06


def test_trailing_silence_closed_at_end(tmp_path):
    wav = make_wav(tmp_path / "t.wav", dur=2.0, gaps=((1.5, 2.0),))
    sil = media.silences(wav)
    assert sil[-1][1] == pytest.approx(2.0, abs=0.05)


def test_lufs_and_loudnorm(clip):
    assert -20 < media.integrated_lufs(clip) < -8
    m = media.loudnorm_measure(clip)
    assert {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"} <= m.keys()
    assert "measured_I=" in media.loudnorm_filter(m)


def test_lufs_of_silence_is_floor(tmp_path):
    wav = make_wav(tmp_path / "s.wav", amp=0.0)
    assert media.integrated_lufs(wav) == -70.0


def test_read_pcm(tmp_path):
    wav = make_wav(tmp_path / "p.wav", dur=1.0)
    x = media.read_pcm(wav, 16000)
    assert x.dtype == np.float32 and abs(len(x) - 16000) < 200
    assert 0.15 < float(np.sqrt(np.mean(x ** 2))) < 0.3


def test_probe_and_frame(clip, tmp_path):
    info = media.probe_video(clip)
    assert (info["width"], info["height"], info["fps"]) == (1080, 1920, "30/1")
    assert info["vcodec"] == "h264" and info["acodec"] == "aac"
    png = media.extract_frame(clip, 1.0, tmp_path / "f.png")
    assert png.exists() and png.stat().st_size > 1000


def test_extract_wav_bad_file(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(MediaError, match="bad.mp4"):
        media.extract_wav(bad, tmp_path / "x.wav")
