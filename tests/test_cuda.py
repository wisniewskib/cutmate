import ctypes
import os
import sys

import pytest

from cutmate import cuda


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(cuda, "_done", False)
    monkeypatch.setattr(cuda, "errors", [])
    monkeypatch.setenv("LD_LIBRARY_PATH", "/old")


def _wheel(root, sub="lib"):
    cublas, cudnn = root / "nvidia" / "cublas" / sub, root / "nvidia" / "cudnn" / sub
    cublas.mkdir(parents=True)
    cudnn.mkdir(parents=True)
    return cublas, cudnn


def test_nvidia_dirs_finds_wheels(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    b.mkdir()
    cublas, cudnn = _wheel(a)
    assert cuda.nvidia_dirs([str(a), str(b)]) == [cublas, cudnn]


def _fake_cdll(monkeypatch, fail=lambda name, loaded: False):
    loaded, calls = [], []

    def cdll(path, mode=0):
        name = os.path.basename(path)
        calls.append((name, mode))
        if fail(name, loaded):
            raise OSError("undefined symbol")
        loaded.append(name)

    monkeypatch.setattr(cuda.ctypes, "CDLL", cdll)
    return loaded, calls


def _linux(monkeypatch, tmp_path, files, sub="lib"):
    monkeypatch.setattr(cuda.sys, "platform", "linux")
    cublas, cudnn = _wheel(tmp_path, sub)
    for f in files:
        (cublas if "cublas" in f else cudnn).joinpath(f).touch()
    monkeypatch.setattr(cuda.sys, "path", [str(tmp_path)])
    return cublas, cudnn


def test_enable_preloads_in_order(monkeypatch, tmp_path):
    files = ["libcublasLt.so.12", "libcublas.so.12", "libcublas.so.13", "libcudnn.so.9",
             "libcudnn_graph.so.9", "libcudnn_ops.so.9"]
    cublas, _ = _linux(monkeypatch, tmp_path, files)
    loaded, calls = _fake_cdll(monkeypatch, lambda n, l: n == "libcudnn_graph.so.9" and "libcudnn_ops.so.9" not in l)
    cuda.enable_cuda_libs()
    assert loaded[:2] == ["libcublasLt.so.12", "libcublas.so.12"]
    assert {"libcudnn.so.9", "libcudnn_graph.so.9", "libcudnn_ops.so.9"} <= set(loaded)
    assert "libcublas.so.13" not in [c[0] for c in calls]
    assert all(m == ctypes.RTLD_GLOBAL for _, m in calls)
    assert os.environ["LD_LIBRARY_PATH"].startswith(str(cublas))
    assert cuda.errors == []


def test_enable_records_unloadable(monkeypatch, tmp_path):
    _linux(monkeypatch, tmp_path, ["libcudnn_bad.so.9"])
    _fake_cdll(monkeypatch, lambda n, l: True)
    cuda.enable_cuda_libs()
    assert len(cuda.errors) == 1 and "libcudnn_bad.so.9" in cuda.errors[0]


def test_enable_idempotent(monkeypatch, tmp_path):
    _linux(monkeypatch, tmp_path, ["libcublas.so.12"])
    _, calls = _fake_cdll(monkeypatch)
    cuda.enable_cuda_libs()
    n = len(calls)
    cuda.enable_cuda_libs()
    assert n == 1 and len(calls) == n


def test_enable_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(cuda.sys, "platform", "win32")
    cublas, cudnn = _wheel(tmp_path, "bin")
    monkeypatch.setattr(cuda.sys, "path", [str(tmp_path)])
    monkeypatch.setenv("PATH", "/orig")
    added = []
    monkeypatch.setattr(cuda.os, "add_dll_directory", lambda d: added.append(d), raising=False)
    cuda.enable_cuda_libs()
    assert added == [str(cublas), str(cudnn)]
    assert os.environ["PATH"].startswith(str(cublas) + os.pathsep + str(cudnn))


def test_enable_noop_macos(monkeypatch, tmp_path):
    monkeypatch.setattr(cuda.sys, "platform", "darwin")
    _, calls = _fake_cdll(monkeypatch)
    assert cuda.enable_cuda_libs() == [] and calls == []
