# Konfiguracja

cutmate trzyma ustawienia w jednym pliku JSON:

| System | Ścieżka |
|---|---|
| Linux / macOS | `~/.cutmate/config.json` |
| Windows | `%USERPROFILE%\.cutmate\config.json` |

Ustaw zmienną środowiskową `CUTMATE_HOME`, żeby przenieść cały katalog domowy cutmate: konfigurację, venv, modele, motywy, render testowy i pobrany GSAP.

Ustawienia możesz zmienić na dwa sposoby: uruchomić ponownie `/cutmate:setup` (zapyta, którą sekcję zmienić) albo użyć CLI:

```bash
cutmate config show                                   # wypisuje obowiązującą konfigurację jako JSON
cutmate config set language=en music.volume=0.3       # ustawia jedną lub więcej par KEY=VALUE
```

`config set` sprawdza każdą wartość i zapisuje dopiero wtedy, gdy wszystkie są poprawne. Odrzuca nieznane klucze i **nigdy nie wyświetla odrzuconej wartości**, bo może to być wklejony klucz API. Klucze API należą do zmiennych środowiskowych (zobacz [installation.md](installation.md#5-klucze-api-tylko-zmienne-środowiskowe)).

## Wszystkie klucze do ustawienia

| Klucz | Wartości | Domyślnie | Co robi |
|---|---|---|---|
| `transcription` | `local`, `groq`, `openai`, `elevenlabs` | `local` | Backend transkrypcji dla `transcribe`, `probe`, `qa`, `selftest` |
| `language` | `pl`, `en` | `pl` | Język filmu: transkrypcja, model wyrównania, wbudowane etykiety |
| `theme` | Nazwa motywu (litery, cyfry, `_`, `-`) | `clean` | Motyw domyślny; musi istnieć w `~/.cutmate/themes/` albo być wbudowany |
| `steps.factcheck` | `true`, `false` | `true` | Claude sprawdza twierdzenia możliwe do zweryfikowania przed cięciem; build ostrzega tylko o części niepotwierdzonych liczb |
| `steps.qa` | `true`, `false` | `true` | Uruchamia `cutmate qa` po renderze |
| `steps.thumbnail` | `true`, `false` | `true` | Tworzy `thumbnail.png` / `.jpg` |
| `music.source` | `heygen`, `folder`, `none` | `none` | Skąd pochodzi podkład muzyczny |
| `music.folder` | Ścieżka do folderu (albo `""` / `null`, żeby wyczyścić) | `null` | Używany, gdy `music.source=folder`; ścieżka jest zapisywana jako bezwzględna |
| `music.volume` | Liczba od 0 do 2 | `0.45` | Poziom podkładu względem głosu (bez voice carve build go zmniejsza o połowę, zobacz [Muzyka](#muzyka)) |
| `captions.9:16` | `burn`, `srt`, `both`, `none` | `burn` | Tryb napisów dla shortów |
| `captions.16:9` | `burn`, `srt`, `both`, `none` | `srt` | Tryb napisów dla długich filmów |

Domyślna konfiguracja wygląda tak:

```json
{
  "transcription": "local",
  "language": "pl",
  "theme": "clean",
  "steps": {"factcheck": true, "qa": true, "thumbnail": true},
  "music": {"source": "none", "folder": null, "volume": 0.45},
  "captions": {"9:16": "burn", "16:9": "srt"}
}
```

Większość flag wiersza poleceń nadpisuje konfigurację na jedno uruchomienie: `--language`, `--backend`, `--theme`. Zobacz [cli.md](cli.md).

## Napisy w zależności od formatu

| Tryb | Wypalone w filmie | `out/captions.srt` |
|---|---|---|
| `burn` | Tak | Nie |
| `srt` | Nie | Tak |
| `both` | Tak | Tak |
| `none` | Nie | Nie |

Dlaczego wartości domyślne się różnią:

- **9:16 → `burn`.** Shorty ogląda się bez dźwięku, a Shorts / Reels / TikTok nie mają porządnego wgrywania napisów. Wypalone napisy słowo po słowie to po prostu ten styl.
- **16:9 → `srt`.** YouTube natywnie wyświetla wgrane napisy (wgraj `captions.srt` w YouTube Studio). Wypalone napisy w 16:9 dzielą dolny pas z belką (lower-third) i kółkiem obrazu w obrazie.

Plik `.srt` używa dokładnie tych samych stron napisów co wersja wypalona.

```bash
cutmate config set captions.9:16=both captions.16:9=burn
```

Napisy są zawsze zsynchronizowane ze słowami (wymuszone wyrównanie wav2vec2 poprawionego tekstu z EDL). Słowa kluczowe wymienione w `plan.json` → `captions.key` dostają kolor akcentu z motywu i pasują też do odmienionych form słowa.

## Muzyka

| `music.source` | Skąd pochodzi podkład |
|---|---|
| `none` | Bez muzyki |
| `folder` | **Pierwszy plik audio** (w kolejności nazw) w `music.folder`: `.mp3 .m4a .wav .ogg .flac .aac` |
| `heygen` | Utwór lo-fi dobierany do każdego filmu przez `media-use` z HyperFrames (wymaga HeyGen CLI ≥ 0.3.0 i zalogowania się przez `heygen auth login --oauth`) |

```bash
cutmate config set music.source=folder music.folder=~/Music/beds
cutmate config set music.source=heygen
cutmate config set music.source=none
```

`music.source=folder` zostanie odrzucone, chyba że folder istnieje i zawiera co najmniej jeden plik audio.

**Jak miksowany jest podkład:**

- Jest zapętlany albo przycinany do długości filmu, sprowadzany do −14 LUFS (tak samo jak głos) i dostaje 0,8 s narastania na początku oraz do 1,8 s wyciszenia na końcu.
- Leży pod głosem na poziomie `music.volume` (domyślnie 0.45). Gdy voice carve jest niedostępny, build **zmniejsza tę wartość o połowę** (domyślnie do 0.225) i wypisuje `WARN music: no voice carve — bed volume halved to …`.
- Gdy zainstalowany jest skill audio z pluginu HyperFrames, podkład przechodzi **carve**: ścisza się pod mową (ducking). `cutmate doctor` pokazuje wtedy `"carve": true`. Bez niego podkład gra na stałym poziomie (po zmniejszeniu głośności o połowę, jak wyżej), a build wypisuje linię `WARN music:`.
- Po renderze `finalize` jeszcze raz sprowadza cały miks do −14 LUFS.

Dla pojedynczego filmu Claude może ustawić konkretny plik w `plan.json`: `"music": {"src": "/abs/path/bed.mp3"}`, opcjonalnie z `"volume"`, które nadpisuje konfigurację. Przy HeyGen bez zalogowania montaż idzie dalej bez muzyki i informuje o tym w `EDIT_NOTES.md`; Claude nigdy nie loguje się za ciebie.

## Kroki opcjonalne

```bash
cutmate config set steps.factcheck=false steps.qa=true steps.thumbnail=true
```

| Krok | Włączony | Wyłączony |
|---|---|---|
| `factcheck` | Claude weryfikuje twierdzenia możliwe do sprawdzenia przez wyszukiwanie w sieci i stronę źródłową, i zapisuje `factcheck.md`. Werdykt ❌ albo ⚠️ wstrzymuje montaż. | Bez `factcheck.md`; build pomija ostrzeżenia o liczbach |
| `qa` | `cutmate qa` ponownie transkrybuje cięcie, żeby znaleźć przeoczone powtórki, i oznacza muzykę albo efekty dźwiękowe głośniejsze od głosu oraz zbyt ciche fragmenty | Bez kontroli QA |
| `thumbnail` | `thumbnail.png` i `thumbnail.jpg` z wybranej klatki plus tytuł i hak | Bez miniatury |

## Zmienne środowiskowe

| Zmienna | Do czego służy |
|---|---|
| `CUTMATE_HOME` | Katalog domowy cutmate (domyślnie `~/.cutmate`) |
| `GROQ_API_KEY` | `transcription=groq` |
| `OPENAI_API_KEY` | `transcription=openai` |
| `ELEVENLABS_API_KEY` | `transcription=elevenlabs` |

## Co jest w katalogu domowym cutmate

| Ścieżka | Zawartość |
|---|---|
| `config.json` | Ustawienia opisane wyżej |
| `venv/` | Środowisko Pythona z CLI `cutmate` |
| `models/` | Modele MediaPipe do pozy i dłoni (Whisper i wav2vec2 są w cache Hugging Face) |
| `vendor/` | GSAP, pobrany przez `cutmate vendor` |
| `themes/` | Twoje zapisane motywy, `.drafts/`, `.backup/` |
| `checks/` | Arkusze klatek wbudowanych motywów z `cutmate theme check` |
| `clone/` | Pliki robocze `/cutmate:clone-style` (można bezpiecznie usunąć) |
| `smoke/` | 5-sekundowy render testowy |
