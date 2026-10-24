# Dokumentacja CLI

Narzędzie wiersza poleceń `cutmate` to silnik, na którym działają skille. Normalnie nie musisz go wpisywać, bo Claude uruchamia je za ciebie. Przydaje się jednak do skryptów, debugowania i budowania własnych skilli.

**Gdzie jest:** `~/.cutmate/venv/bin/cutmate` (Linux / macOS) albo `~/.cutmate/venv/Scripts/cutmate.exe` (Windows); zobacz [installation.md](installation.md#3-środowisko-pythona). Skille znajdują je tą linią, która działa w bash, zsh i w Git Bash z Claude Code na Windowsie:

```bash
CM="$(ls "${CUTMATE_HOME:-$HOME/.cutmate}/venv/bin/cutmate" "${CUTMATE_HOME:-$HOME/.cutmate}/venv/Scripts/cutmate.exe" 2>/dev/null | head -1)"; [ -n "$CM" ] || CM="$(command -v cutmate)"
"$CM" doctor
```

**Konwencje**

- `<rec>` to folder z nagraniami; `<out>` to jego folder `out/` (na przykład `~/Videos/short/out`).
- Polecenia, które przyjmują `--language` albo `--backend`, bez nich biorą wartość z konfiguracji (`cutmate config show`). Polecenia, które przyjmują `--theme`, bez niej biorą `theme` z konfiguracji.
- Błędy wypisują jedną linię `cutmate: <przyczyna i sposób naprawy>` na stderr i kończą się kodem **2**. `render`, `finalize` i `smoke` kończą się kodem **1**, gdy wynik nie przejdzie kontroli specyfikacji.
- Wyjście jest w UTF-8 na każdym systemie. Ścieżki ze spacjami bierz w cudzysłów.

## Podsumowanie

| Polecenie | Do czego służy |
|---|---|
| [`transcribe`](#transcribe) | Transkrybuje każdy klip w folderze z nagraniami |
| [`formats`](#formats) | Proporcje każdego klipu (z uwzględnieniem obrotu) |
| [`sheet`](#sheet) | Arkusz klatek (contact sheet) |
| [`probe`](#probe) | Ponowna transkrypcja jednego krótkiego okna (ukryte powtórki) |
| [`rms`](#rms) | Skan głośności w krótkich przedziałach (plamy mowy) |
| [`cut`](#cut) | Wycina A-roll według EDL |
| [`align`](#align) | Czasy słów dla A-rollu |
| [`track`](#track) | Pozycje twarzy i dłoni w czasie |
| [`build`](#build) | `plan.json` → projekt HyperFrames |
| [`preview`](#preview) | Szybki podgląd 480p + `chapters.txt` (punkt kontrolny długich filmów) |
| [`render`](#render) | Sprawdza, renderuje i finalizuje zbudowany projekt |
| [`finalize`](#finalize) | Korekta głośności i kontrola specyfikacji renderu |
| [`qa`](#qa) | QA gotowego filmu |
| [`requests`](#requests) | Dopasowuje `requests.md` do planu |
| [`shot`](#shot) | Zrzut strony internetowej na b-roll |
| [`thumb`](#thumb) | Miniatura z klatki + tytułu |
| [`save-effect`](#save-effect) | Zachowuje własny efekt w motywie |
| [`theme …`](#theme) | Szkice motywów: new, list, use, save, check, font, digits, colors |
| [`theme-check`](#theme-check) | Renderuje każdy komponent motywu (bez lintu / oznaczenia z `theme check`) |
| [`config show` / `config set`](#config) | Pokazuje albo zmienia konfigurację |
| [`doctor`](#doctor) | Raport stanu (JSON) |
| [`models`](#models) | Pobiera modele lokalne |
| [`vendor`](#vendor) | Pobiera GSAP (ze sprawdzeniem sum sha) |
| [`selftest`](#selftest) | Test transkrypcji na twoim klipie |
| [`smoke`](#smoke) | 5-sekundowy render testowy |

## Nagrania i ujęcia

### transcribe

```bash
cutmate transcribe <rec> [--prompt "Claude, Caveman, GitHub"] [--backend local|groq|openai|elevenlabs] [--language pl|en] [--force]
```

Transkrybuje każdy plik wideo w `<rec>` ze znacznikami czasu słów. Wyniki trafiają do `<rec>/out/work/<clip file name>/`: `transcript.json`, `silences.json` i `<stem>.wav`. Linie zaczynające się od `SUSPECT long word` oznaczają okna, w których prawdopodobnie kryje się zająknięcie albo powtórka.

| Flaga | Znaczenie |
|---|---|
| `--prompt` | Nazwy własne i wskazówki pisowni dla modelu |
| `--backend` | Nadpisuje backend z konfiguracji |
| `--language` | Nadpisuje język z konfiguracji |
| `--force` | Ponownie transkrybuje klipy, które już mają transkrypcję |

### formats

```bash
cutmate formats <rec>
```

Wypisuje `<clip>: <width>x<height> <9:16|16:9>` dla każdego klipu (z uwzględnieniem obrotu), a potem `format: 9:16`, `format: 16:9` albo `format: mixed`.

### sheet

```bash
cutmate sheet <video> -o <png> [--start 0] [--end <s>] [--step 0.5] [--cols 6]
```

Zapisuje arkusz klatek z etykietami czasu i wypisuje ścieżkę (lub ścieżki). Ponad 48 klatek jest dzielone na `name_01.png`, `name_02.png`, …

| Flaga | Domyślnie | Znaczenie |
|---|---|---|
| `-o`, `--out` | wymagana | Wyjściowy PNG |
| `--start` / `--end` | 0 / koniec filmu | Zakres czasu w sekundach |
| `--step` | 0.5 | Sekundy między klatkami (> 0) |
| `--cols` | 6 | Liczba kolumn (≥ 1) |

### probe

```bash
cutmate probe <wav> --start <s> --end <s> [--prompt "Um, uh, er, hmm."] [--backend …] [--language …]
```

Ponownie transkrybuje jedno krótkie okno (około 1 s) pliku WAV klipu i wypisuje `word@start-end` dla każdego słowa, z czasami liczonymi od początku pliku WAV. Użyj go, żeby wyłapać falstarty, które Whisper skleił w jedno długie słowo.

### rms

```bash
cutmate rms <wav> --start <s> --end <s> [--bin 0.05]
```

Wypisuje poziom RMS (dB) w każdym przedziale z paskiem, a potem `blobs: [a-b] …`, czyli plamy mowy. Dwie plamy w jednym „słowie” albo krótki skok po słowie wskazują na powtórkę, zająknięcie albo mlaśnięcie.

## Cięcie, wyrównanie, śledzenie

### cut

```bash
cutmate cut <out>/edl.json
```

Wycina `out/aroll.mp4` według EDL. Fragmenty są kodowane po kolei (bezpiecznie dla pamięci nawet przy 4K), cięcia są dociągane do siatki klatek, głośność każdego fragmentu jest wyrównywana do mediany głośności fragmentów, a na każdym cięciu pojawiają się krótkie przejścia audio. Zapisuje też `out/work/edl_timed.json`.

### align

```bash
cutmate align <out>/edl.json [--language pl|en]
```

Wymusza wyrównanie tekstu z EDL do `aroll.mp4` przy użyciu wav2vec2 i zapisuje `out/work/aligned_words.json`. Słowa oznaczone `(estimated)` oznaczają, że tekst fragmentu nie zgadza się z jego dźwiękiem. Najpierw uruchom `cut`.

### track

```bash
cutmate track <out> [--force]
```

Śledzi w czasie twarz, dłonie, czubki palców i wskazywanie przy użyciu MediaPipe i zapisuje `out/work/tracks.json`. Wypisuje ścieżkę i liczbę próbek dla każdego śladu. Praca jest pomijana, gdy `tracks.json` jest nowszy niż `aroll.mp4`; `--force` robi ją od nowa (potrzebne raz dla projektów śledzonych, zanim pojawiły się ślady czubków palców).

## Build i render

### build

```bash
cutmate build <out> [--theme <name>] [--language pl|en]
```

Zamienia `plan.json` (plus `edl.json`, wyrównane słowa i ślady) w projekt HyperFrames w `out/composition/`. Gdy to ma zastosowanie, zapisuje też `captions.srt` i `chapters.txt`. Wypisuje ostrzeżenia (`WARN density`, `WARN wow …`, `WARN panel gap` …), `layout: classic|split-panel`, po jednej linii `panel:` na element panelu, `project: <path>` i `checkpoints: t1,t2,…` (czasy, w których warto zrobić zrzuty). Błędne kotwice kończą się błędem z listą słów danego fragmentu.

### preview

```bash
cutmate preview <out> [--theme <name>] [--language pl|en]
```

Zapisuje szybki podgląd 480p `out/preview.mp4` (cięcie plus plansze rozdziałów) i `out/chapters.txt`, a potem wypisuje rozdziały. To punkt kontrolny długich filmów przed powolnym pełnym renderem.

### render

```bash
cutmate render <out>
```

Uruchamia `hyperframes check`, potem `hyperframes render` (postęp widać w terminalu i w `out/work/render.log`), a potem `finalize`. Zapisuje `out/final.mp4` i klatki `check_*.png` w punktach kontrolnych z builda. Short 9:16 zajmuje około 1–2 minut; 16:9 około 45–60 minut na każde 15 minut filmu.

### finalize

```bash
cutmate finalize <src.mp4> <dst.mp4> [--format 9:16|16:9] [--check 1.5,4.0]
```

Sprowadza cały miks do −14 LUFS i sprawdza specyfikację: 1080×1920 albo 1920×1080, 30 kl./s, H.264 + AAC. Wypisuje `<file>: WxH fps codecs, duration, LUFS — OK` albo `SPEC MISMATCH` i zapisuje klatkę `check_<t>.png` dla każdego czasu z `--check`.

### qa

```bash
cutmate qa <out> [--no-asr] [--backend …] [--language …]
```

Ponownie transkrybuje pocięty A-roll i oznacza powtórzone słowa oraz końcowe „…” (przeoczone falstarty). Porównuje też miks z głosem: `LOUD` oznacza efekty dźwiękowe albo muzykę głośniejsze od głosu o ponad 3 dB, a `QUIET` fragment cichszy od mediany głosu o ponad 4 dB. `--no-asr` uruchamia tylko kontrolę miksu.

## Prośby, b-roll, miniatury, efekty

### requests

```bash
cutmate requests <out>
```

Dopasowuje każdą linię z `out/requests.md` do planu i dla każdej prośby wypisuje `OK`, `MISSING`, `BAD` albo `NOTE` (niespodzianki mają przedrostek `SURPRISE`), a potem `requests: N ok, M missing, K bad`. Wymaga `work/aligned_words.json`, `work/edl_timed.json` i `plan.json`. Format linii opisuje [usage.md](usage.md#prośby-na-czacie-albo-powiedziane-w-nagraniu).

### shot

```bash
cutmate shot "<url>" -o <png> [--width 1000] [--height 700] [--light]
```

Robi zrzut strony internetowej (albo lokalnego pliku HTML) przez headless Chrome / Chromium / Edge. Strona renderuje się w trybie ciemnym, chyba że podasz `--light`.

### thumb

```bash
cutmate thumb <out> --at <s> --title "SAME KONKRETY" [--hook "Czy to nadal działa?"] [--theme <name>] [--side left|right]
```

Tworzy `out/thumbnail.png` i `out/thumbnail.jpg` z klatki w sekundzie `--at` gotowego cięcia (pobranej z `aroll.mp4`, więc bez wypalonych napisów). Shorty dostają 1080×1920, filmy 16:9 1280×720. Tytuł łamie się na najwyżej 3 linie, a hak na 2. W 16:9 `--side` (domyślnie `right`) ustawia ramkę z tekstem po tej stronie, więc wybierz klatkę z twarzą po drugiej stronie.

### save-effect

```bash
cutmate save-effect <out> <name> [--theme <name>] [--description "…"] [--force]
```

Lintuje `out/custom/<name>.html` i kopiuje go (razem z folderem zasobów `out/custom/<name>/`) do `~/.cutmate/themes/<theme>/components/custom/`, zapisując go w `index.json` tego folderu. `--force` zastępuje efekt o tej samej nazwie. Nazwy efektów to małe litery, cyfry i myślniki.

## Motywy

### theme

```bash
cutmate theme new [<name>] [--from clean] [--mode custom|random|clone] [--seed N] [--avoid THEME ...]
cutmate theme list
cutmate theme use <name>
cutmate theme save <name> [--force]
cutmate theme check <name> [--clip <video>] [--language pl|en] [--saved]
cutmate theme font <name> "<Google font family>" --role text|display|num
cutmate theme digits <name>
cutmate theme colors <image> [<image> ...] [--n 8]
```

| Podpolecenie | Co robi |
|---|---|
| `new` | Zakłada szkic w `~/.cutmate/themes/.drafts/<name>/` jako kopię `--from` (domyślnie `clean`). Wypisuje JSON z `name`, `path` i `direction`. `--mode random` losuje kierunek (i może zaproponować nazwę); `--seed` sprawia, że losowanie da się powtórzyć; `--avoid` (można podać wiele razy) odsuwa losowanie od wcześniejszych szkiców. Ostrzega, gdy zapisany motyw ma już taką nazwę. |
| `list` | Jedna linia na motyw, pola rozdzielone tabulatorem: `marker`, `name`, `kind` (bundled / user / draft), `checked`, `path` |
| `use` | Ustawia zapisany motyw jako domyślny (`theme` w konfiguracji) |
| `save` | Przenosi sprawdzony szkic do `~/.cutmate/themes/`. `--force` nadpisuje, a starą wersję zostawia w `themes/.backup/` |
| `check` | Lintuje motyw, renderuje każdy komponent w obu formatach, zapisuje `check/contact.png` i arkusze, a potem oznacza motyw jako sprawdzony. To bramka przed `save`. `--clip` używa twojego nagrania jako A-rollu zamiast obrazu testowego (`--language` ma tu domyślnie `pl`); `--saved` sprawdza zapisany motyw nawet wtedy, gdy istnieje szkic o tej samej nazwie. |
| `font` | Pobiera font Google na licencji OFL do **szkicu** (`text`, `display` albo `num` dla fontu cyfr), razem z jego licencją |
| `digits` | Renderuje liczby motywu w jego foncie nagłówków / cyfr obok podobnych liter (5 i S, 0 i O) i wypisuje ścieżkę do PNG |
| `colors` | Wypisuje dominujące kolory obrazów jako `#hex  NN%` (`--n` kolorów, domyślnie 8) |

### theme-check

```bash
cutmate theme-check [--theme <name>] [--language pl|en] [--format 9:16|16:9|all]
```

Renderuje każdy komponent motywu i wypisuje ścieżkę do arkusza klatek dla każdego formatu (`check passed (9:16) — contact sheet: …`). W odróżnieniu od `theme check` nie lintuje, nie zapisuje `contact.png` i nie oznacza motywu jako sprawdzonego.

## Konfiguracja i środowisko

### config

```bash
cutmate config show
cutmate config set KEY=VALUE [KEY=VALUE ...]
```

`show` wypisuje obowiązującą konfigurację jako JSON. `set` sprawdza wartości i zapisuje, a potem wypisuje ścieżkę pliku i nową konfigurację. Wszystkie klucze są opisane w [configuration.md](configuration.md).

### doctor

```bash
cutmate doctor
```

Wypisuje raport stanu w JSON: Python, venv, ffmpeg, Node.js, pakiety, CUDA, modele, klucze API (czy są ustawione, nigdy ich wartości), carve, konfiguracja, vendor i folder pluginu. Nigdy nie kończy się błędem. Zobacz [installation.md](installation.md#rozwiązywanie-problemów-z-cutmate-doctor).

### models

```bash
cutmate models [--language pl|en] [--backend local|groq|openai|elevenlabs]
```

Pobiera model wyrównania wav2vec2 dla danego języka, Whisper large-v3, gdy backend to `local`, oraz modele MediaPipe do pozy i dłoni. Po ponownym uruchomieniu pobieranie się wznawia.

### vendor

```bash
cutmate vendor
```

Pobiera z jsDelivr do `~/.cutmate/vendor/` biblioteki, których cutmate nie może rozpowszechniać (GSAP), sprawdza każdy plik z sumą sha256 w `assets/vendor/MANIFEST.json` i nie zapisuje niczego, co nie przejdzie kontroli. Jest idempotentne i wypisuje `gsap@3.14.2: ok` albo `fetched …`.

### selftest

```bash
cutmate selftest --clip <video> [--backend …] [--language …]
```

Transkrybuje pierwsze 30 s twojego klipu i wypisuje `backend: … · device: … · compute: …`, liczbę słów i czas trwania oraz pierwsze słowa ze znacznikami czasu. `--clip` jest wymagane, chyba że istnieje wbudowana próbka dla danego języka.

### smoke

```bash
cutmate smoke [--clip <video>] [--music <audio>] [--format 9:16|16:9] [--workdir <dir>]
```

Robi 5-sekundowy render od początku do końca (tytuł plus napisy i opcjonalny podkład muzyczny) w `~/.cutmate/smoke/` albo w `--workdir`. Wypisuje `final:` i `frame:` (PNG z 1,5 s). Bez `--clip` używa jednolitego kolorowego tła. Klip musi mieć co najmniej 2 s.
