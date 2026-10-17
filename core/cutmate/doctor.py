"""`cutmate doctor` (JSON health report, never raises) and `cutmate models` (model downloads)."""
import importlib.util
import os
import shutil
import subprocess
import sys

from . import align, paths, tracks
from .backends.local import LocalBackend
from .config import ConfigError, home
from .config import load as load_config
from .errors import CutmateError

KEY_ENVS = ("GROQ_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY")
WHISPER_REPOS = {"faster": "Systran/faster-whisper-large-v3", "mlx": "mlx-community/whisper-large-v3-mlx"}


def _has(*modules: str) -> bool:
    try:
        return all(importlib.util.find_spec(m) is not None for m in modules)
    except (ImportError, ValueError):
        return False


def _hf_cached(repo: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
        return isinstance(try_to_load_from_cache(repo, "config.json"), str)
    except Exception:
        return False


def _snapshot(repo: str) -> str:
    from huggingface_hub import snapshot_download
    return snapshot_download(repo)


def _node() -> str | None:
    exe = shutil.which("node")
    if not exe:
        return None
    try:
        return subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _cuda() -> dict:
    out = {"libs": [], "devices": 0, "errors": []}
    try:
        from . import cuda
        out["libs"] = [str(p) for p in cuda.enable_cuda_libs()]
        out["errors"] = list(cuda.errors)
    except Exception:
        pass
    try:
        import ctranslate2
        out["devices"] = int(ctranslate2.get_cuda_device_count())
    except Exception:
        out["devices"] = 0
    return out


def _model_file(url: str) -> bool:
    return (home() / "models" / url.rsplit("/", 1)[1]).exists()


def _guard(fn, default):
    try:
        return fn()
    except Exception:
        return default


def doctor() -> dict:
    from . import music
    engine = _guard(lambda: LocalBackend.auto().engine, "faster")
    whisper_repo = WHISPER_REPOS.get(engine, WHISPER_REPOS["faster"])
    try:
        load_config()
        cfg = "ok"
    except ConfigError as e:
        cfg = " ".join(str(e).split())
    except Exception as e:
        cfg = f"cannot read config ({e.__class__.__name__})"
    return {
        "python": ".".join(str(x) for x in sys.version_info[:3]),
        "venv": sys.prefix,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "node": _guard(_node, None),
        "packages": {
            "faster_whisper": _has("faster_whisper"),
            "mlx_whisper": _has("mlx_whisper"),
            "align": _has("torch", "transformers"),
            "track": _has("mediapipe"),
        },
        "cuda": _cuda(),
        "models": {
            "whisper": _hf_cached(whisper_repo),
            "align_pl": _hf_cached(align.MODELS["pl"]),
            "align_en": _hf_cached(align.MODELS["en"]),
            "pose": _guard(lambda: _model_file(tracks.MODEL_URL), False),
            "hand": _guard(lambda: _model_file(tracks.HAND_MODEL_URL), False),
        },
        "keys": {k: bool(os.environ.get(k)) for k in KEY_ENVS},
        "carve": bool(_guard(music._carve_script, None)),
        "config": cfg,
        "plugin_root": str(paths.plugin_root()),
    }


def download_models(language: str, backend: str) -> list[str]:
    repos = [align.MODELS[language]]
    if backend == "local":
        repos.append(WHISPER_REPOS[LocalBackend.auto().engine])
    try:
        import huggingface_hub  # noqa: F401
    except ImportError:
        raise CutmateError("Python packages missing — run install/setup.sh (/cutmate:setup)") from None
    done: list[str] = []
    for repo in repos:
        try:
            path = _snapshot(repo)
        except Exception as e:
            reason = " ".join(str(e).split())[:100] or e.__class__.__name__
            raise CutmateError(f"cannot download {repo}: {reason} — check the connection and rerun `cutmate models`") from None
        print(f"ok {repo} {path}")
        done.append(repo)
    for kind in ("pose", "hand"):
        print(f"ok {kind} {tracks.model_path(kind)}")
        done.append(kind)
    return done
