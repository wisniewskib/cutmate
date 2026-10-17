#!/usr/bin/env bash
# cutmate environment report: prints one JSON object, installs nothing.
# Uses only `command -v` plus uname df awk sed grep head tr cat. Portable to bash 3.2.

esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
jstr() { if [ -n "$1" ]; then printf '"%s"' "$(esc "$1")"; else printf 'null'; fi; }
jnum() { if [ -n "$1" ]; then printf '%s' "$1"; else printf 'null'; fi; }
jbool() { if [ "$1" = 1 ]; then printf 'true'; else printf 'false'; fi; }

# --- os / arch / distro / package manager
uname_s=$(uname -s 2>/dev/null)
arch=$(uname -m 2>/dev/null)
os=linux
distro=
pkg=
case "$uname_s" in
  Darwin) os=macos ;;
  *)
    if [ -r /etc/os-release ]; then
      distro=$(grep '^ID=' /etc/os-release | head -1 | sed 's/^ID=//; s/"//g' | tr 'A-Z' 'a-z')
    fi
    ;;
esac
if [ "$os" = macos ]; then
  command -v brew >/dev/null 2>&1 && pkg=brew
else
  if command -v apt-get >/dev/null 2>&1; then pkg=apt
  elif command -v dnf >/dev/null 2>&1; then pkg=dnf
  elif command -v pacman >/dev/null 2>&1; then pkg=pacman
  fi
fi

# --- gpu
gpu_kind=none; gpu_name=; gpu_vram=; gpu_driver=
if command -v nvidia-smi >/dev/null 2>&1; then
  # a broken driver prints its failure text on stdout and exits non-zero: require exit 0 and a numeric VRAM
  if line=$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>/dev/null) \
     && line=$(printf '%s\n' "$line" | head -1) \
     && vram=$(printf '%s' "$line" | awk -F', *' '{print $2}' | tr -d ' ') \
     && printf '%s' "$vram" | grep -Eq '^[0-9]+$'; then
    gpu_kind=nvidia
    gpu_name=$(printf '%s' "$line" | awk -F', *' '{print $1}')
    gpu_vram=$vram
    gpu_driver=$(printf '%s' "$line" | awk -F', *' '{print $3}' | tr -d ' ')
  fi
fi
if [ "$gpu_kind" = none ] && [ "$os" = macos ] && [ "$arch" = arm64 ]; then
  gpu_kind=apple
fi

# --- disk (free GB of $HOME)
disk=$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print int($4/1048576)}')
[ -n "$disk" ] || disk=0

# --- tools
ffmpeg_v=
if command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg_v=$(ffmpeg -version 2>/dev/null | head -1 | sed -n 's/^ffmpeg version \([^ ]*\).*/\1/p')
  [ -n "$ffmpeg_v" ] || ffmpeg_v=unknown
fi

py_bin=; py_ver=; py_venv=0
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  command -v "$c" >/dev/null 2>&1 || continue
  v=$("$c" --version 2>&1 | head -1 | sed -n 's/^Python \([0-9][0-9.]*\).*/\1/p')
  [ -n "$v" ] || continue
  maj=${v%%.*}; rest=${v#*.}; min=${rest%%.*}
  if [ "$maj" -gt 3 ] || { [ "$maj" -eq 3 ] && [ "$min" -ge 10 ]; }; then
    py_bin=$(command -v "$c"); py_ver=$v
    "$c" -c "import ensurepip, venv" >/dev/null 2>&1 && py_venv=1
    break
  fi
done

node_v=; node_major=0
if command -v node >/dev/null 2>&1; then
  node_v=$(node --version 2>/dev/null | head -1 | sed 's/^v//')
  node_major=${node_v%%.*}
  case "$node_major" in ''|*[!0-9]*) node_major=0 ;; esac
fi
npx=0; command -v npx >/dev/null 2>&1 && npx=1
heygen_v=
if command -v heygen >/dev/null 2>&1; then
  heygen_v=$(heygen --version 2>/dev/null | head -1 | sed -n 's/^[^0-9]*\([0-9][0-9.]*\).*/\1/p')
  [ -n "$heygen_v" ] || heygen_v=unknown
fi

# --- cutmate home
home=${CUTMATE_HOME:-$HOME/.cutmate}
cm_venv=0; [ -f "$home/venv/bin/python" ] && cm_venv=1
cm_cfg=0; [ -f "$home/config.json" ] && cm_cfg=1

# --- missing + install commands
missing=
[ -n "$ffmpeg_v" ] || missing="$missing ffmpeg"
[ -n "$py_bin" ] || missing="$missing python"
if [ -n "$py_bin" ] && [ "$py_venv" = 0 ]; then missing="$missing python-venv"; fi
if [ -z "$node_v" ] || [ "$node_major" -lt 22 ]; then missing="$missing node"; fi

install_cmd() {
  case "$pkg:$1" in
    apt:ffmpeg) echo 'sudo apt-get install -y ffmpeg' ;;
    apt:python) echo 'sudo apt-get install -y python3 python3-venv' ;;
    apt:python-venv) echo 'sudo apt-get install -y python3-venv' ;;
    apt:node) echo 'sudo snap install node --classic --channel=22/stable' ;;
    dnf:ffmpeg) echo 'sudo dnf install -y ffmpeg-free' ;;
    dnf:python) echo 'sudo dnf install -y python3' ;;
    dnf:node) echo 'sudo dnf install -y nodejs22' ;;
    pacman:ffmpeg) echo 'sudo pacman -S --needed ffmpeg' ;;
    pacman:python) echo 'sudo pacman -S --needed python' ;;
    pacman:node) echo 'sudo pacman -S --needed nodejs npm' ;;
    brew:ffmpeg) echo 'brew install ffmpeg' ;;
    brew:python) echo 'brew install python@3.12' ;;
    brew:node) echo 'brew install node' ;;
  esac
}

missing_json=; install_json=
for m in $missing; do
  missing_json="$missing_json${missing_json:+, }\"$m\""
  cmd=$(install_cmd "$m")
  if [ -n "$cmd" ]; then
    install_json="$install_json${install_json:+, }\"$(esc "$cmd")\""
  fi
done

# --- output
printf '{"os": %s, "distro": %s, "arch": %s, "pkg": %s, ' "$(jstr "$os")" "$(jstr "$distro")" "$(jstr "$arch")" "$(jstr "$pkg")"
printf '"gpu": {"kind": %s, "name": %s, "vram_mb": %s, "driver": %s}, ' "$(jstr "$gpu_kind")" "$(jstr "$gpu_name")" "$(jnum "$gpu_vram")" "$(jstr "$gpu_driver")"
printf '"disk_free_gb": %s, ' "$disk"
printf '"tools": {"ffmpeg": %s, "python": %s, "python_bin": %s, "python_venv": %s, "node": %s, "npx": %s, "heygen": %s}, ' \
  "$(jstr "$ffmpeg_v")" "$(jstr "$py_ver")" "$(jstr "$py_bin")" "$(jbool "$py_venv")" "$(jstr "$node_v")" "$(jbool "$npx")" "$(jstr "$heygen_v")"
printf '"cutmate": {"home": %s, "venv": %s, "config": %s}, ' "$(jstr "$home")" "$(jbool "$cm_venv")" "$(jbool "$cm_cfg")"
printf '"missing": [%s], "install": [%s]}\n' "$missing_json" "$install_json"
exit 0
