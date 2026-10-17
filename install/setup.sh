#!/usr/bin/env bash
# cutmate setup: builds ${CUTMATE_HOME:-~/.cutmate}/venv with the plugin installed editable.
# Usage: setup.sh [--gpu nvidia|apple|none] [--local] [--dry-run]
set -euo pipefail

usage() { echo "usage: setup.sh [--gpu nvidia|apple|none] [--local] [--dry-run]" >&2; exit 2; }

gpu=none; local_=0; dry=0
while [ $# -gt 0 ]; do
  case "$1" in
    --gpu)
      [ $# -ge 2 ] || usage
      case "$2" in nvidia|apple|none) gpu=$2 ;; *) usage ;; esac
      shift 2 ;;
    --local) local_=1; shift ;;
    --dry-run) dry=1; shift ;;
    *) usage ;;
  esac
done

ROOT=$(cd "$(dirname "$0")/.." && pwd)
HOME_DIR=${CUTMATE_HOME:-$HOME/.cutmate}
VENV=$HOME_DIR/venv
PY=$VENV/bin/python

find_python() {
  local c v maj rest min
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    command -v "$c" >/dev/null 2>&1 || continue
    v=$("$c" --version 2>&1 | head -1 | sed -n 's/^Python \([0-9][0-9.]*\).*/\1/p')
    [ -n "$v" ] || continue
    maj=${v%%.*}; rest=${v#*.}; min=${rest%%.*}
    if [ "$maj" -gt 3 ] || { [ "$maj" -eq 3 ] && [ "$min" -ge 10 ]; }; then
      command -v "$c"; return 0
    fi
  done
  return 1
}

PYBIN=$(find_python) || {
  echo "Python ≥ 3.10 not found — install it first (/cutmate:setup → dependencies)" >&2
  exit 1
}

run() {
  echo "+ $*"
  if [ "$dry" = 0 ]; then "$@"; fi
}

extras=align,track
if [ "$local_" = 1 ]; then
  if [ "$gpu" = apple ]; then extras=$extras,mlx; else extras=$extras,faster; fi
fi

if [ ! -f "$PY" ]; then
  [ "$dry" = 1 ] || mkdir -p "$HOME_DIR"
  run "$PYBIN" -m venv "$VENV"
fi
run "$PY" -m pip install --upgrade pip
if [ "$gpu" != apple ]; then
  run "$PY" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
fi
run "$PY" -m pip install -e "$ROOT[$extras]"
if [ "$gpu" = nvidia ] && [ "$local_" = 1 ]; then
  run "$PY" -m pip install nvidia-cublas-cu12 'nvidia-cudnn-cu12==9.*'
fi

echo "venv: $VENV"
echo "cutmate: $VENV/bin/cutmate"
