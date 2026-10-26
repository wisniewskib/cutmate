# Instalacja

Po tym przewodniku będziesz mieć plugin cutmate w Claude Code, środowisko Pythona w `~/.cutmate/venv` z pobranymi modelami i 5-sekundowy render testowy, który potwierdza, że wszystko działa.

Wersja w skrócie: zainstaluj plugin, a potem uruchom `/cutmate:setup`. Kreator zrobi resztę i zapyta, zanim cokolwiek zainstaluje. Ta strona wyjaśnia, co robi na każdym systemie, żebyś mógł zainstalować rzeczy samodzielnie albo naprawić je, gdy coś się nie uda.

## 1. Instalacja pluginu

Wystarczy jeden marketplace. W Claude Code (w aplikacji desktopowej `/plugin` otwiera okno pluginów) dodaj marketplace i zainstaluj cutmate:

```text
/plugin marketplace add wisniewskib/cutmate
/plugin install cutmate@cutmate
```

Marketplace cutmate zawiera też plugin HyperFrames (`hyperframes@cutmate`, przypięty do wersji, z którą cutmate jest testowany), więc instaluje się on automatycznie jako zależność. Jeśli się nie zainstalował, doinstaluj go: `/plugin install hyperframes@cutmate`. cutmate potrzebuje jego skilla audio, żeby przyciszać muzykę pod głosem („carve”). Bez niego podkład muzyczny po prostu gra na stałym poziomie.

### Z lokalnego klona (rozwój albo brak marketplace'u)

```bash
git clone https://github.com/wisniewskib/cutmate.git
claude --plugin-dir ./cutmate
```

## 2. Zależności systemowe

| Narzędzie | Do czego | Minimum |
|---|---|---|
| Python | CLI `cutmate` (we własnym venv) | 3.10, z `venv` / `ensurepip` |
| Node.js + `npx` | HyperFrames (`npx --yes hyperframes@0.8.157 …`) | 22 |
| ffmpeg | Cięcie, głośność, klatki | Dowolna świeża wersja |
| Chrome / Chromium / Edge | Tylko zrzuty stron przez `cutmate shot` | Dowolna |

Kreator uruchamia detektor, który niczego nie instaluje i wypisuje JSON: system, menedżer pakietów, GPU, znalezione narzędzia, wolne miejsce na dysku oraz to, czego brakuje, razem z poleceniem instalacji. Możesz go uruchomić sam:

**Linux / macOS / Windows Git Bash**

```bash
bash install/detect.sh
```

**Windows PowerShell**

```powershell
powershell -ExecutionPolicy Bypass -File install\detect.ps1
```

Oto polecenia instalacji, które podpowiada detektor:

| System | ffmpeg | Python | Node.js 22+ |
|---|---|---|---|
| Ubuntu / Debian (apt) | `sudo apt-get install -y ffmpeg` | `sudo apt-get install -y python3 python3-venv` | `sudo snap install node --classic --channel=22/stable` |
| Fedora (dnf) | `sudo dnf install -y ffmpeg-free` | `sudo dnf install -y python3` | `sudo dnf install -y nodejs22` |
| Arch (pacman) | `sudo pacman -S --needed ffmpeg` | `sudo pacman -S --needed python` | `sudo pacman -S --needed nodejs npm` |
| macOS (Homebrew) | `brew install ffmpeg` | `brew install python@3.12` | `brew install node` |
| Windows (winget) | `winget install -e --id Gyan.FFmpeg` | `winget install -e --id Python.Python.3.12` | `winget install -e --id OpenJS.NodeJS.LTS` |

> **Claude nigdy nie uruchamia `sudo` i nigdy nie wpisuje hasła.** Gdy polecenie wymaga `sudo`, uruchamiasz je sam: na czacie Claude Code z `!` na początku (na przykład `! sudo apt-get install -y ffmpeg`) albo we własnym terminalu. Polecenia `brew` i `winget` Claude uruchamia dopiero po twojej zgodzie.

> **Windows:** po instalacji przez `winget` zrestartuj Claude Code, żeby jego powłoka zobaczyła nowy `PATH`, a potem uruchom `/cutmate:setup` ponownie. Kreator wznowi pracę tam, gdzie skończył.

## 3. Środowisko Pythona

Skrypt instalacyjny tworzy `${CUTMATE_HOME:-~/.cutmate}/venv`, instaluje w nim cutmate w trybie edytowalnym, a potem pobiera GSAP (zobacz [libraries.md](libraries.md#gsap)). Ustaw `CUTMATE_HOME`, jeśli katalog domowy cutmate ma być gdzie indziej.

**Linux / macOS / Windows Git Bash**

```bash
bash install/setup.sh --gpu nvidia --local     # GPU NVIDIA, lokalny Whisper
bash install/setup.sh --gpu apple --local      # Apple Silicon, lokalny Whisper (mlx-whisper)
bash install/setup.sh --gpu none               # komputer bez GPU, z backendem przez API
```

**Windows PowerShell**

```powershell
powershell -ExecutionPolicy Bypass -File install\setup.ps1 -Gpu nvidia -Local
powershell -ExecutionPolicy Bypass -File install\setup.ps1 -Gpu none
```

| Flaga (`setup.sh` / `setup.ps1`) | Działanie |
|---|---|
| `--gpu nvidia\|apple\|none` / `-Gpu nvidia\|none` | Pod jakie GPU instalować. `apple` przyjmuje tylko `setup.sh`. |
| `--local` / `-Local` | Instaluje też lokalnego Whispera: `faster-whisper` (NVIDIA / CPU) albo `mlx-whisper` (Apple). Przy NVIDIA instaluje też z pip biblioteki CUDA 12 `nvidia-cublas-cu12` i `nvidia-cudnn-cu12==9.*`. |
| `--dry-run` / `-DryRun` | Wypisuje polecenia bez ich uruchamiania |

Każda instalacja dostaje dodatki `align` (PyTorch + transformers) i `track` (MediaPipe). Poza Apple PyTorch pochodzi z indeksu paczek dla CPU, bo wyrównanie spokojnie działa na procesorze. Venv zajmuje około 3–4 GB.

Na koniec skrypt wypisuje, gdzie jest CLI:

| System | Ścieżka CLI |
|---|---|
| Linux / macOS | `~/.cutmate/venv/bin/cutmate` |
| Windows | `~/.cutmate/venv/Scripts/cutmate.exe` (`%USERPROFILE%\.cutmate\venv\Scripts\cutmate.exe`) |

Skille same znajdują CLI. Żeby uruchomić je ręcznie:

```bash
# Linux / macOS
~/.cutmate/venv/bin/cutmate doctor
# Windows Git Bash
~/.cutmate/venv/Scripts/cutmate.exe doctor
```

```powershell
# Windows PowerShell
& "$HOME\.cutmate\venv\Scripts\cutmate.exe" doctor
```

W dalszej części dokumentacji polecenie zapisujemy po prostu jako `cutmate`.

## 4. Backend transkrypcji, GPU i modele

| Backend | Działa na | Model | Wymaga |
|---|---|---|---|
| `local` | GPU NVIDIA (CUDA), Apple Silicon albo CPU | Whisper large-v3 (`faster-whisper`; na Apple `mlx-whisper`) | `--local` przy instalacji, około 3 GB do pobrania |
| `groq` | API Groq | `whisper-large-v3` | `GROQ_API_KEY` |
| `openai` | API OpenAI | `whisper-1` | `OPENAI_API_KEY` |
| `elevenlabs` | API ElevenLabs | `scribe_v2` | `ELEVENLABS_API_KEY` |

Kreator poleca `local`, gdy znajdzie GPU NVIDIA albo Apple, a `groq`, gdy nie znajdzie żadnego GPU, bo large-v3 na procesorze jest wolny.

```bash
cutmate config set transcription=local language=en
cutmate models --language en       # model wyrównania + modele śledzenia twarzy/dłoni (+ Whisper przy local)
cutmate selftest --clip ~/Videos/take1.mp4
```

`selftest` transkrybuje pierwsze 30 s twojego klipu i wypisuje na przykład `backend: local · device: cuda · compute: float16`.

### NVIDIA / CUDA

- Potrzebujesz tylko działającego sterownika NVIDIA (`nvidia-smi` musi się uruchamiać). **Nie** potrzebujesz systemowego CUDA Toolkit: cuBLAS i cuDNN przychodzą z pip, a cutmate ładuje je sam.
- cutmate najpierw próbuje `float16`. Jeśli to się nie uda, na przykład gdy karcie z 6 GB zabraknie pamięci, ponawia z `int8_float16`, a dopiero potem przechodzi na CPU z linią `WARN`.
- Jeśli `selftest` pokazuje `device: cpu` na komputerze z NVIDIA, zajrzyj do `cutmate doctor` → `cuda.errors`, a potem uruchom ponownie `setup.sh --gpu nvidia --local`.

### Apple Silicon

`setup.sh --gpu apple --local` instaluje `mlx-whisper`, a cutmate wybiera go automatycznie (model `mlx-community/whisper-large-v3-mlx`).

## 5. Klucze API: tylko zmienne środowiskowe

cutmate czyta klucze API **wyłącznie** ze zmiennych środowiskowych. Nigdy nie zapisuje ich w `config.json`: `cutmate config set` odrzuca każdy klucz konfiguracji, którego nie zna, i nigdy nie wyświetla tego, co wpisałeś. Nigdy nie wklejaj klucza na czat.

| Backend | Zmienna | Gdzie zdobyć klucz |
|---|---|---|
| Groq | `GROQ_API_KEY` | https://console.groq.com/keys |
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| ElevenLabs | `ELEVENLABS_API_KEY` | https://elevenlabs.io/app/settings/api-keys |

Ustaw zmienną sam, a potem **zrestartuj Claude Code**, żeby ją odziedziczył.

**Linux / macOS** (dodaj linię do `~/.bashrc`, `~/.zshrc` albo profilu swojej powłoki):

```bash
export GROQ_API_KEY=your-key-here
```

**Windows** (we własnym oknie PowerShell albo cmd; działa dla nowo uruchomionych procesów):

```powershell
setx GROQ_API_KEY "your-key-here"
```

Sprawdź, czy klucz jest widoczny, bez wypisywania go: `cutmate doctor` → `"keys": {"GROQ_API_KEY": true, …}`.

## 6. Muzyka (opcjonalnie) i logowanie do HeyGen

| Źródło | Konfiguracja |
|---|---|
| `none` | Nic do zrobienia |
| `folder` | `cutmate config set music.source=folder music.folder=~/Music/beds`. W folderze musi być co najmniej jeden plik `.mp3 .m4a .wav .ogg .flac .aac`. |
| `heygen` | Katalog utworów lo-fi przez `media-use` z HyperFrames. Wymaga [HeyGen CLI](https://developers.heygen.com/cli) w wersji 0.3.0 lub nowszej, a **logujesz się sam**. |

Żeby korzystać z HeyGen, zainstaluj CLI według oficjalnej instrukcji, a potem zaloguj się z czatu albo z własnego terminala:

```text
! heygen auth login --oauth
```

Potem sprawdź, czy jesteś zalogowany, i przełącz źródło:

```bash
npx --yes hyperframes@0.8.157 media-use resolve --doctor
cutmate config set music.source=heygen
```

Claude nigdy nie loguje się w twoim imieniu. Jeśli nie jesteś zalogowany, montaż po prostu idzie dalej bez muzyki. Głośność i przyciszanie (carve) opisuje [configuration.md](configuration.md#muzyka).

## 7. Render testowy

```bash
cutmate smoke --clip ~/Videos/take1.mp4                  # render 5 s: tytuł + napisy
cutmate smoke --clip ~/Videos/take1.mp4 --music bed.mp3  # z podkładem muzycznym
```

Wypisuje `final:` (plik MP4) i `frame:` (PNG z 1,5 s). Udany przebieg kończy się linią finalize w stylu `final.mp4: 1080x1920 30/1 h264 + aac, 5.00s, -14.0 LUFS — OK`. `/cutmate:setup` traktuje istnienie `~/.cutmate/smoke/rec/out/final.mp4` jako znak, że konfiguracja jest zakończona.

## Rozwiązywanie problemów z `cutmate doctor`

`cutmate doctor` wypisuje raport stanu w JSON i nigdy nie kończy się błędem. Czytaj go pole po polu:

| Pole | Prawidłowa wartość | Jeśli nie |
|---|---|---|
| `python`, `venv` | 3.10+, venv cutmate | Uruchom ponownie `setup.sh` / `setup.ps1` |
| `ffmpeg` | `true` | Zainstaluj ffmpeg (tabela wyżej) i zrestartuj Claude Code |
| `node` | `v22…` lub nowszy | Zainstaluj Node.js 22+ |
| `packages.faster_whisper` / `mlx_whisper` | `true` dla `local` | `setup.sh … --local` |
| `packages.align` / `packages.track` | `true` | Ponownie `setup.sh` |
| `cuda.devices`, `cuda.errors` | ≥ 1 urządzenie, brak błędów (NVIDIA) | Zaktualizuj sterownik, `setup.sh --gpu nvidia --local` |
| `models.whisper`, `align_pl` / `align_en`, `pose`, `hand` | `true` | `cutmate models --language <pl\|en>` (pobieranie się wznawia) |
| `keys` | `true` dla twojego backendu API | Ustaw zmienną i zrestartuj Claude Code |
| `carve` | `true` | `/plugin install hyperframes@cutmate` |
| `config` | `ok` | Uruchom `/cutmate:setup` (nadpisze uszkodzoną konfigurację) |
| `vendor` | `ok` | `cutmate vendor` (pobiera GSAP i sprawdza sumy sha) |
| `plugin_root` | Twój aktualny folder pluginu | Plugin został przeniesiony albo zaktualizowany: uruchom ponownie `/cutmate:setup` |

### Częste problemy

| Objaw | Rozwiązanie |
|---|---|
| `cutmate: npx not found (Node.js ≥ 22 needed)` | Zainstaluj Node.js 22+, zrestartuj Claude Code |
| `vendored library … not found` podczas builda | `cutmate vendor` |
| `alignment models not installed. Run /cutmate:setup.` | `cutmate models --language <l>` |
| `selftest` pokazuje `device: cpu` na NVIDIA | `cutmate doctor` → `cuda.errors`; `setup.sh --gpu nvidia --local` |
| `WARN hyperframes check ran out of time` | Zajęty komputer, a nie błąd: render idzie dalej |
| `Chrome not found` z `cutmate shot` | Zainstaluj Google Chrome albo sam wrzuć zrzut ekranu do `broll/` |
| Przekroczony czas pobierania (`cutmate models`, pierwszy `selftest`) | Uruchom to samo polecenie ponownie: pobieranie się wznawia |
| Windows: narzędzie zainstalowane przez winget nadal jest „missing” | Zrestartuj Claude Code, a potem uruchom ponownie `/cutmate:setup` |

Dalej nie działa? Otwórz issue z wynikiem `cutmate doctor`. Nie ma w nim kluczy API, tylko `true` / `false` dla każdej zmiennej z kluczem.
