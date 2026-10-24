# Biblioteki, modele i licencje

Ta strona wymienia wszystko, czego używa cutmate: co to jest, w jakiej wersji, na jakiej licencji i po co cutmate tego potrzebuje. Sam cutmate jest na licencji [MIT](../LICENSE). Każdy komponent zewnętrzny zachowuje własną licencję.

Wersje to te przypięte w `pyproject.toml`, `assets/vendor/MANIFEST.json`, `core/cutmate/hf.py` oraz identyfikatory modeli w kodzie. Licencje pakietów Pythona są podane tak, jak deklarują je metadane każdego pakietu.

## Biblioteki JavaScript (dołączone, offline)

Te pliki są ładowane do kompozycji HyperFrames. Każdy plik jest przypięty sumą sha256 w [`assets/vendor/MANIFEST.json`](../assets/vendor/MANIFEST.json), a teksty licencji są w [`assets/vendor/LICENSES/`](../assets/vendor/LICENSES/). Build kopiuje tylko biblioteki, których projekt używa, i nie ładuje ich z CDN. Sieć bywa potrzebna tylko przy pierwszym uruchomieniu narzędzi (`npx hyperframes`, `@hyperframes/core` dla muzyki, GSAP przez `cutmate vendor`); potem rendery działają offline.

| Biblioteka | Wersja | Licencja | W repo | Po co |
|---|---|---|---|---|
| [GSAP](https://gsap.com) + DrawSVG, MorphSVG, MotionPath, SplitText | 3.14.2 | GSAP Standard "no charge" license | **Nie** (pobierany przez `cutmate vendor`) | Oś czasu, na której animuje się każdy komponent motywu (jedna zatrzymana, przewijalna oś czasu) |
| [three.js](https://threejs.org) + RoomEnvironment, TextGeometry, FontLoader, GLTFLoader, EffectComposer / RenderPass / UnrealBloomPass / OutputPass / ShaderPass / SavePass / MaskPass, shadery Copy / LuminosityHighPass / Output, BufferGeometryUtils, kroje Droid Sans Bold i Helvetiker Bold | 0.181.2 | MIT | Tak | Efekty 3D: exploded-view, globe, burst-out, showcase-3d, energy-ball; poświata bloom; tekst 3D (Droid Sans Bold ma polskie znaki) |
| [postprocessing](https://github.com/pmndrs/postprocessing) | 6.39.5 | Zlib | Tak | Przebiegi post-processingu od pmndrs, ładowane tylko wtedy, gdy efekt importuje `postprocessing` (albo wywołuje `U.post`) |
| [anime.js](https://animejs.com) | 4.5.0 | MIT | Tak | `kinetic-word` (setki kształtów wlatujących w litery) i własne efekty (`U.anime`) |
| [lottie-web](https://github.com/airbnb/lottie-web) | 5.12.2 | MIT | Tak | Animacje Lottie we własnych efektach (`U.lottie`) |
| [KaTeX](https://katex.org) + fonty | 0.19.0 | MIT | Tak | Wzory matematyczne w efektach (`U.tex`) |
| [Rough.js](https://roughjs.com) | 4.6.6 | MIT | Tak | Styl rysowany odręcznie dla `flow` (`style: "rough"`) i `U.rough` |
| [D3](https://d3js.org) | 7.9.0 | ISC | Tak | Dostępne dla własnych efektów (dane, skale, kształty); ładowane tylko wtedy, gdy efekt go używa |

### GSAP

Standardowa licencja GSAP ([gsap.com/standard-license](https://gsap.com/standard-license)) pozwala używać GSAP za darmo, ale nie pozwala jednoznacznie rozpowszechniać jego plików w cudzym repozytorium. Dlatego cutmate **nie zawiera GSAP**. `MANIFEST.json` oznacza go jako `"redistribute": false` i trzyma tylko sumy kontrolne plików i tekst licencji.

`cutmate vendor` (uruchamiane automatycznie przez `install/setup.sh` i `install/setup.ps1`) pobiera pięć plików z `https://cdn.jsdelivr.net/npm/gsap@3.14.2/` do `~/.cutmate/vendor/gsap@3.14.2/`. Sprawdza każdy z jego sumą sha256 i nie zapisuje niczego, co nie przejdzie kontroli. `cutmate doctor` → `vendor` pokazuje, czy GSAP jest na miejscu. `.gitignore` wyklucza `assets/vendor/gsap@*/`, więc lokalna kopia opiekuna projektu nigdy nie trafia do commita.

## Renderowanie

| Narzędzie | Wersja | Licencja | Po co |
|---|---|---|---|
| [HyperFrames](https://github.com/heygen-com/hyperframes) (CLI z npm, uruchamiane przez `npx`) | 0.8.157 (przypięta) | Apache-2.0 | Renderuje kompozycję HTML do MP4 w headless Chrome; do tego `check`, `snapshot`, `remove-background` (wycięcie mówiącego z tła dla efektów `bg`) i `media-use` (podkłady muzyczne i obrazy) |
| Plugin HyperFrames do Claude Code | Z jego marketplace'u | Apache-2.0 | Skrypt carve z jego skilla audio ścisza podkład muzyczny pod głosem |
| [Node.js](https://nodejs.org) | ≥ 22 | MIT | Uruchamia HyperFrames |
| [ffmpeg](https://ffmpeg.org) | Instalacja systemowa | LGPL / GPL (zależnie od wersji) | Dekodowanie, cięcie, głośność (`loudnorm`), klatki, arkusze klatek, podgląd |
| Google Chrome / Chromium / Edge | Instalacja systemowa | Licencja producenta | Tylko zrzuty stron przez `cutmate shot` |

cutmate wywołuje ffmpeg, Node.js i Chrome jako zewnętrzne programy. Nie dołącza ich ani nie linkuje.

## Pakiety Pythona

Instalowane do `~/.cutmate/venv` przez `install/setup.sh` / `install/setup.ps1`.

| Pakiet | Ograniczenie wersji | Licencja | Dodatek | Po co |
|---|---|---|---|---|
| numpy | ≥ 1.24 | BSD-3-Clause (plus dołączone licencje permisywne) | core | Tablice audio: skany RMS, QA, wyrównanie |
| Pillow | ≥ 10.1 | MIT-CMU | core | Arkusze klatek, miniatury, plansze podglądu, wyciąganie kolorów |
| requests | ≥ 2.31 | Apache-2.0 | core | Backendy API (Groq, OpenAI, ElevenLabs) |
| fontTools | ≥ 4.47 | MIT | core | Kontrole fontów: pokrycie polskich znaków, arkusze cyfr |
| faster-whisper (+ CTranslate2) | ≥ 1.2, < 2 | MIT | `faster` | Lokalny Whisper large-v3 na GPU NVIDIA albo CPU, ze znacznikami czasu słów |
| mlx-whisper | ≥ 0.4.3 | MIT | `mlx` | Lokalny Whisper large-v3 na Apple Silicon |
| torch | ≥ 2.2 | W stylu BSD (zobacz metadane pakietu) | `align` | Uruchamia model wyrównujący wav2vec2 (wersja CPU na Windowsie / Linuksie) |
| transformers (+ huggingface_hub) | ≥ 4.40 | Apache-2.0 | `align` | Ładuje wav2vec2 i pobiera modele z Hugging Face Hub |
| mediapipe | ≥ 0.10.20 | Apache-2.0 | `track` | Śledzenie twarzy, dłoni, czubków palców i wskazywania |
| nvidia-cublas-cu12, nvidia-cudnn-cu12 9.x | Z pip | Licencja oprogramowania NVIDIA | NVIDIA + `--local` | Biblioteki uruchomieniowe CUDA 12 dla faster-whisper, więc systemowy CUDA Toolkit nie jest potrzebny |
| pytest, responses | ≥ 8, ≥ 0.25 | MIT, Apache-2.0 | `dev` | Testy |

## Modele

| Model | Źródło | Licencja | Do czego | Rozmiar |
|---|---|---|---|---|
| Whisper large-v3, [`Systran/faster-whisper-large-v3`](https://huggingface.co/Systran/faster-whisper-large-v3) | OpenAI, przekonwertowany do CTranslate2 | MIT | Lokalna transkrypcja (NVIDIA / CPU) | ≈ 3 GB |
| Whisper large-v3, [`mlx-community/whisper-large-v3-mlx`](https://huggingface.co/mlx-community/whisper-large-v3-mlx) | OpenAI, przekonwertowany do MLX | MIT | Lokalna transkrypcja (Apple Silicon) | ≈ 3 GB |
| [`jonatasgrosman/wav2vec2-large-xlsr-53-polish`](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-polish) | Hugging Face | Apache-2.0 | Wyrównanie słów po polsku (napisy) | ≈ 1 GB |
| [`jonatasgrosman/wav2vec2-large-xlsr-53-english`](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-english) | Hugging Face | Apache-2.0 | Wyrównanie słów po angielsku (napisy) | ≈ 1 GB |
| MediaPipe Pose Landmarker Lite (`pose_landmarker_lite.task`, float16) | Google (storage.googleapis.com), ze sprawdzeniem sha256 | Apache-2.0 | Pozycja twarzy, wskazywanie | Dziesiątki MB |
| MediaPipe Hand Landmarker (`hand_landmarker.task`, float16) | Google, ze sprawdzeniem sha256 | Apache-2.0 | Dłonie, czubki palców, wykrywanie otwartej dłoni | Dziesiątki MB |

Pobiera je `cutmate models`. Modele Hugging Face trafiają do cache Hugging Face, a modele MediaPipe do `~/.cutmate/models/`.

### Modele transkrypcji przez API

| Backend | Model | Warunki |
|---|---|---|
| Groq | `whisper-large-v3` | Regulamin Groq; twój klucz, twoje konto |
| OpenAI | `whisper-1` | Regulamin OpenAI |
| ElevenLabs | `scribe_v2` | Regulamin ElevenLabs |

Przy backendzie przez API cutmate wysyła dźwięk klipu (przekodowany do mono 16 kHz MP3) do danego dostawcy. Przy `local` dźwięk nigdy nie opuszcza twojego komputera.

## Dołączone zasoby

| Zasób | Źródło | Licencja |
|---|---|---|
| Inter (Medium, ExtraBold, Black), font motywu `clean` | [rsms/inter](https://github.com/rsms/inter) v4.1 | SIL Open Font License 1.1 ([`themes/clean/fonts/OFL-inter.txt`](../themes/clean/fonts/OFL-inter.txt)) |
| Efekty dźwiękowe: `whoosh`, `pop`, `click`, `impact`, `swell`, `ping` | Paczki interface, impact i sci-fi od [Kenney.nl](https://kenney.nl) | CC0 1.0 ([`assets/sfx/LICENSES.md`](../assets/sfx/LICENSES.md)) |
| Kropki lądów i etykiety krajów na globusie (`globe/land.json`, `countries.json`) | [Natural Earth](https://www.naturalearthdata.com) 1:110m Admin 0, v5.1.2 | Domena publiczna ([`SOURCE.txt`](../themes/clean/components/custom/globe/SOURCE.txt)) |
| Grafika bannera w README | Wygenerowana dla tego projektu | MIT, razem z repo |

Fonty, które dodajesz do własnych motywów, pochodzą wyłącznie z Google Fonts na licencji OFL. `cutmate theme font` odrzuca wszystko inne i zapisuje `OFL-<family>.txt` obok plików fontu.

## Opcjonalne narzędzia, które instalujesz sam

| Narzędzie | Używane przez | Uwagi |
|---|---|---|
| [HeyGen CLI](https://developers.heygen.com/cli) ≥ 0.3.0 | Podkłady muzyczne (`music.source=heygen`), obrazy AI | Instalujesz je i logujesz się sam (`heygen auth login --oauth`) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | `/cutmate:clone-style` z linkiem | Pobiera jeden publiczny film do analizy stylu, tylko po twojej zgodzie; nigdy z ciasteczkami ani logowaniem |
