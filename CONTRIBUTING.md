# Współtworzenie cutmate

Dzięki, że pomagasz. Ten przewodnik prowadzi cię od świeżego klona do przechodzących testów i wyjaśnia zasady, dzięki którym cutmate działa na Windowsie, macOS i Linuksie.

## Środowisko deweloperskie

Wymagania: Python 3.10+, Node.js 22+ (z `npx`), ffmpeg, git. Google Chrome jest opcjonalny (polecenie `shot`).

**Linux / macOS**

```bash
git clone https://github.com/wisniewskib/cutmate.git
cd cutmate
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pip install -e ".[dev,align,track,faster]"   # opcjonalnie: pełny zestaw, do testów -m slow / hf
.venv/bin/cutmate vendor                                         # GSAP, potrzebny testom builda
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/wisniewskib/cutmate.git
cd cutmate
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\cutmate.exe vendor
```

Żeby wypróbować swoją kopię roboczą w Claude Code bez ruszania prawdziwego katalogu domowego cutmate:

```bash
CUTMATE_HOME=/tmp/cm-dev claude --plugin-dir .
```

```powershell
$env:CUTMATE_HOME = "$env:TEMP\cm-dev"; claude --plugin-dir .
```

Potem uruchom w tej sesji `/cutmate:setup`.

## Testy

Testy są w `tests/`. Domyślnie `pytest` pomija ciężkie markery (`addopts = -m 'not slow and not hf and not net'` w `pyproject.toml`).

| Polecenie | Co się uruchamia | Wymaga |
|---|---|---|
| `.venv/bin/python -m pytest` | Szybki zestaw (setki testów; kilka minut) | Dodatek `dev`, ffmpeg |
| `.venv/bin/python -m pytest -m hf` | Testy, które budują i renderują przez `npx hyperframes` (motywy, komponenty, efekty WOW, budżety renderu) | Node.js 22+, sieć przy pierwszym uruchomieniu, Chrome pobrany przez HyperFrames |
| `.venv/bin/python -m pytest -m net` | Testy, które pobierają fonty z Google Fonts | Sieć |
| `.venv/bin/python -m pytest -m slow` | Testy, które potrzebują pobranych modeli albo nagranych próbek | Dodatki `align` / `track` / `faster`, modele |
| `.venv/bin/python -m pytest tests/test_plan.py -k density` | Jeden plik / jeden test | |

Na Windowsie użyj `.venv\Scripts\python.exe -m pytest …`.

Przed każdym PR uruchom szybki zestaw. Uruchom `-m hf`, gdy ruszasz `build.py`, komponenty motywów, efekty, `web/*.js` albo cokolwiek, co zmienia renderowany wynik. Niektóre buildy są przypięte do **identycznych bajt w bajt „złotych”** wyników, więc zamierzona zmiana wizualna wymaga aktualizacji złotego pliku w tym samym PR, z notką wyjaśniającą dlaczego.

Najpierw napisz test, który nie przechodzi, a potem poprawkę.

## Konwencje

- **Jedna sprawa na zmianę.** Poprawki są małe. Komunikaty commitów są krótkie, w trybie rozkazującym i używają istniejących przedrostków (`feat:`, `fix:`, `docs:`, `test:`).
- **Błąd to jedna linia z rozwiązaniem.** Rzucaj `CutmateError` (albo podklasę) z przyczyną i poleceniem, które to naprawia. CLI wypisuje `cutmate: …` i kończy się kodem 2. Nigdy nie pokazuj stack trace'a przy spodziewanym błędzie.
- **Nigdy nie dotykaj sekretów.** Klucze API pochodzą wyłącznie ze zmiennych środowiskowych. Nigdy nie wyświetlaj danych od użytkownika, które mogą być kluczem (zobacz `config.set_values`).
- **Determinizm.** Wszystko, co się renderuje, musi być czystą funkcją czasu: jedna zatrzymana oś czasu albo `U.clock`, losowość wyłącznie z `U.seed`. Nowe zakazane elementy dodawaj do lintu w `effects.py` razem z testem.
- **Rendery offline.** Nowa biblioteka JS przechodzi przez `tools/vendor_libs.py` z przypiętą wersją, sumami sha256 i licencją w `assets/vendor/LICENSES/`. Jeśli jej licencja nie pozwala na rozpowszechnianie, oznacz ją `"redistribute": false`, żeby zamiast tego pobierał ją `cutmate vendor`.
- **Licencje.** Fonty muszą być na OFL (Google Fonts), a efekty dźwiękowe na CC0 albo podobnej licencji, z plikiem licencji obok. Nigdy nie commituj nagrania prawdziwej osoby.
- **Skille to produkt.** Jeśli zmieniasz wyjście CLI, flagi albo nazwy plików, zaktualizuj każdy `skills/*/SKILL.md`, który o nich wspomina, i dokumentację w `docs/`. Polecenia w skillach używają `"$CM"` (CLI z venv) i muszą działać w Git Bash z Claude Code na Windowsie.
- **Dokumentacja idzie razem ze zmianą.** Nowe polecenie, flaga, klucz konfiguracji albo parametr efektu potrzebuje wpisu w `docs/cli.md`, `docs/configuration.md` albo `docs/effects.md`, a w przypadku efektów także w `index.json`.

## Zasady dla Windowsa

Większość użytkowników cutmate jest na Windowsie, więc każda zmiana musi działać tam tak samo jak na Linuksie i macOS:

- **Tylko `pathlib`.** Żadnych ścieżek sklejanych przez `/` i żadnego zakodowanego na sztywno `/tmp`. Używaj `tempfile` albo katalogu domowego cutmate.
- **`encoding="utf-8"`** przy każdym `open`, `read_text` i `write_text`. Domyślne kodowanie Windowsa (cp1250 / cp1252) psuje polski tekst.
- **Żadnych dowiązań symbolicznych.** Zamiast tego kopiuj.
- **Podprocesy:** argumenty jako lista, nigdy `shell=True`, żadnych poleceń tylko dla basha wywoływanych z Pythona. Programy znajduj przez `shutil.which` (żeby znaleźć `npx.cmd` i `ffmpeg.exe`).
- **Nazwy plików bezpieczne dla ASCII** dla wszystkiego, co zapisuje cutmate.
- **Filtry ffmpeg:** unikaj `drawtext` ze ścieżkami do fontów, bo litery dysków w Windowsie psują składnię filtra. Rysuj tekst przez Pillow, tak jak robi to `preview.py`.
- **Treść skilli:** polecenia muszą działać w Git Bash z Claude Code na Windowsie: bierz w cudzysłów każdą ścieżkę (spacje w folderach użytkownika), używaj linii `CM=…`, która znajduje też `venv/Scripts/cutmate.exe`, i podawaj warianty dla PowerShella (`setx`, `setup.ps1`) tam, gdzie użytkownik coś uruchamia we własnym terminalu.
- **Skrypty instalacyjne:** trzymaj `setup.sh` / `setup.ps1` i `detect.sh` / `detect.ps1` w zgodzie ze sobą. `setup.ps1` musi pozostać zgodny z Windows PowerShell 5.1.

Jeśli coś działa tylko na Linuksie, napisz to w PR. Przed wydaniem setup i montaż są uruchamiane od zera na prawdziwym komputerze z Windowsem.

## Pull requesty

1. Utwórz gałąź od `main`.
2. Wprowadź zmianę, z testami i dokumentacją.
3. Uruchom szybki zestaw testów (i `-m hf`, jeśli zmiana dotyka renderowania).
4. Otwórz PR z opisem tego, co się zmieniło, dlaczego, jak to przetestowałeś i na jakim systemie.

Wnosząc wkład, zgadzasz się, że jest on objęty [licencją MIT](LICENSE).
