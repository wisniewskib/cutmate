"""Make pip-installed CUDA 12 libraries (nvidia-cublas-cu12, nvidia-cudnn-cu12) visible to this process."""
import ctypes
import os
import sys
from pathlib import Path

_done = False
_dirs: list[Path] = []
errors: list[str] = []  # libraries that could not be preloaded: "<file>: <reason>"


def nvidia_dirs(paths: list[str] | None = None) -> list[Path]:
    sub = "bin" if sys.platform == "win32" else "lib"
    found: list[Path] = []
    for entry in (sys.path if paths is None else paths):
        for lib in ("cublas", "cudnn"):
            d = Path(entry) / "nvidia" / lib / sub
            if d.is_dir() and d not in found:
                found.append(d)
    return found


def _preload(dirs: list[Path]) -> None:
    def files(pattern: str) -> list[Path]:
        return sorted(f for d in dirs for f in d.glob(pattern))

    pending = files("libcublasLt.so.12") + files("libcublas.so.12") + files("libcudnn*.so.9")
    reasons: dict[Path, str] = {}
    progress = True
    while pending and progress:
        progress, retry = False, []
        for f in pending:
            try:
                ctypes.CDLL(str(f), mode=ctypes.RTLD_GLOBAL)
                progress = True
            except OSError as e:
                reasons[f] = " ".join(str(e).split())[:100]
                retry.append(f)
        pending = retry
    errors.extend(f"{f.name}: {reasons[f]}" for f in pending)


def enable_cuda_libs() -> list[Path]:
    global _done, _dirs
    if _done:
        return _dirs
    _done = True
    if sys.platform == "darwin":
        _dirs = []
        return _dirs
    _dirs = nvidia_dirs()
    if not _dirs:
        return _dirs
    joined = os.pathsep.join(str(d) for d in _dirs)
    if sys.platform == "win32":
        for d in _dirs:
            os.add_dll_directory(str(d))
        os.environ["PATH"] = joined + os.pathsep + os.environ.get("PATH", "")
    else:
        # LD_LIBRARY_PATH only reaches child processes; dlopen here needs the explicit preload below
        old = os.environ.get("LD_LIBRARY_PATH")
        os.environ["LD_LIBRARY_PATH"] = joined + (os.pathsep + old if old else "")
        _preload(_dirs)
    return _dirs
