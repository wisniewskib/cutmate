# Użycie: montaż filmu

Ten przewodnik prowadzi cię od folderu surowych nagrań do gotowego filmu i pokazuje, w których momentach wkraczasz ty.

## Zanim zaczniesz

- `/cutmate:setup` jest zakończony (zobacz [installation.md](installation.md)).
- Wrzuć **wszystkie ujęcia jednego filmu do jednego folderu**: klipy z telefonu (`.mov`, `.mp4`, …) albo pliki z aparatu, w dowolnej kolejności. Powtórki, falstarty i gadanie do kamery między ujęciami są w porządku. Wycięcie ich to zadanie cutmate.
- Opcjonalnie: wrzuć b-roll (zrzuty ekranu, obrazy, logotypy, klipy) do `<folder>/broll/`.

cutmate **nigdy nie zmienia twoich plików źródłowych**. Wszystko, co generuje, trafia do `<folder>/out/`. Folder `broll/` zawiera wejścia: twoje pliki oraz to, co Claude pobierze lub zrobi na potrzeby montażu (zrzuty stron, obrazy). Istniejących plików w `broll/` nigdy nie nadpisuje; nowy plik dostaje unikalną nazwę (z przyrostkiem `-2`, `-3`).

## Rozpoczęcie montażu

```text
/cutmate:edit ~/Videos/caveman-short
```

W tej samej wiadomości możesz dodać kontekst, na przykład nazwy, które Whisper mógłby przekręcić, motyw albo prośby:

```text
/cutmate:edit ~/Videos/caveman-short — nazwy produktów: Claude, Caveman, GitHub. Użyj motywu neon-pill. Dodaj explainery.
```

Format wynika z klipów: same pionowe oznaczają **short 9:16**, same poziome **długi film 16:9**, a przy mieszance Claude raz zapyta, który format zrobić.

## Co się dzieje, krok po kroku

| Krok | Co robi Claude | Co trafia do `out/` |
|---|---|---|
| 1. Transkrypcja | Transkrybuje każdy klip słowo po słowie, podpowiadając modelowi twoje nazwy własne. Oznacza okna `SUSPECT long word`, w których kryje się zająknięcie. | `work/<clip>/transcript.json`, `silences.json`, `<stem>.wav` |
| 2. Oglądanie | Robi arkusze klatek i **czyta je**: odwracanie wzroku, czytanie z kartki, skoki kadru, wskazywanie palcem | `sheets/*.png` |
| 2b. Konspekt (16:9) | Rozdziały z tytułami, klipami i zakresami czasu | `outline.md` |
| 3. Wybór ujęć | Ponownie transkrybuje podejrzane okna (`probe`), skanuje głośność (`rms`), porównuje każde ujęcie każdej powtarzanej kwestii i zapisuje uzasadnienie każdego wyboru | `takes.md` |
| 4. Fact-check | Gdy `steps.factcheck` jest włączone, Claude sprawdza liczby, ceny, daty, wersje i twierdzenia typu „pierwszy / jedyny / darmowy” przez wyszukiwanie w sieci i stronę źródłową | `factcheck.md` |
| 5. Cięcie | Tnie na granicach ciszy, dociąga cięcia do siatki klatek, wyrównuje głośność każdego fragmentu i dodaje krótkie przejścia audio | `edl.json`, `aroll.mp4` |
| 6. Wyrównanie | Czasy słów dla napisów (wymuszone wyrównanie wav2vec2) | `work/aligned_words.json` |
| 7. Śledzenie | Pozycje twarzy, dłoni i wskazywania w czasie, gdy efekt ich potrzebuje | `work/tracks.json` |
| 8. Plan | Napisy, grafiki, explainery, efekty, panel (motywy split-panel), muzyka | `plan.json` |
| 9. Punkt kontrolny | **„zrozumiałem tak”**: lista tego, co Claude zrobi (zobacz niżej) | `requests.md` |
| 9b. Podgląd (16:9) | Szybki podgląd cięcia w 480p z planszami rozdziałów, do twojego zatwierdzenia | `preview.mp4`, `chapters.txt` |
| 10. Build | Zamienia plan w projekt HyperFrames, potem robi i czyta zrzuty klatek | `composition/`, `snapshots/` |
| 11. Render | Sprawdzenie, render, a potem finalizacja do −14 LUFS z kontrolą specyfikacji | `final.mp4`, `check_*.png` |
| 12. QA | Ponownie transkrybuje gotowe cięcie, żeby wyłapać przeoczone powtórki; sprawdza poziom muzyki i efektów dźwiękowych względem głosu | Raport na czacie |
| 13. Miniatura | Klatka z wyrazistą miną plus tytuł i hak | `thumbnail.png`, `thumbnail.jpg` |
| 14. Notatki | Ostateczna struktura, każda grafika i powód jej użycia, muzyka, użyte polecenia | `EDIT_NOTES.md` |

Kroki 4 (fact-check), 12 (QA) i 13 (miniatura) są opcjonalne. Włączasz je i wyłączasz kluczami `steps.factcheck`, `steps.qa` i `steps.thumbnail` (zobacz [configuration.md](configuration.md)).

**Wznawianie:** jeśli uruchomisz `/cutmate:edit` ponownie na tym samym folderze, Claude kontynuuje od pierwszego brakującego pliku w `out/`.

### Kiedy Claude się zatrzymuje i pyta

Claude robi pauzę tylko w kilku miejscach:

1. **Twierdzenie nie przechodzi fact-checku** (❌ albo ⚠️). Wybierasz: użyć innego ujęcia, w którym mówisz to poprawnie, wyciąć kwestię, nagrać ją ponownie albo zostawić z korektą na ekranie.
2. **Mieszane formaty**: który format zrobić.
3. **Punkt kontrolny „zrozumiałem tak”**: gdy miałeś jakiekolwiek prośby.
4. **Podgląd 16:9**: zawsze przy długich filmach, przed powolnym pełnym renderem (15-minutowy film renderuje się około 45–60 minut).

## Prośby: na czacie albo powiedziane w nagraniu

O rzeczy możesz prosić na dwa sposoby:

- **Na czacie:** „daj kosmiczne tło za mną w 0:41”, „dodaj explainery”, „licznik na tych 75%”.
- **Na głos, podczas nagrywania:** uwagi reżyserskie skierowane do montażysty, takie jak „tu daj kartę z liczbą”, „tu dodaj globus”, „przesuń mnie gdzie indziej”. cutmate rozpoznaje te kwestie w transkrypcji, zamienia je w prośby i **wycina je z filmu**, chyba że są też częścią treści.

Claude zbiera każdą prośbę w `out/requests.md`, po jednej w linii:

```text
- [<source>] <what> → <target> [@ <anchor>]
```

| Część | Wartości |
|---|---|
| source (źródło) | `[czat]`, `[nagranie <clip> <time>]` (powiedziane w nagraniu), `[uwagi <mm:ss>]` (twoje uwagi po renderze), `[niespodzianka]` (niespodzianka dodana przez Claude'a) |
| target (cel) | Komponent (`counter`, `split`, `stamp` …), `custom:<name>`, `explainers`, `cut` albo `skip` |
| anchor (kotwica) | Fragment (`S5`), słowo we fragmencie (`S7:Rasengan`) albo czas w gotowym filmie (`41.0` lub `0:41`; dopasowanie w zakresie ±1 s) |

Przykład:

```text
- [czat] kosmiczne tło za mną → bg @ 0:41
- [nagranie IMG_6050.MOV 12.3] globus z krajami → custom:globe @ S4:świecie
- [niespodzianka] klejnot na „poznajcie” → custom:burst-out @ S2:poznajcie
```

Przed punktem kontrolnym Claude uruchamia `cutmate requests <folder>/out`. Polecenie dopasowuje każdą linię do `plan.json` i dla każdej prośby wypisuje `OK`, `MISSING`, `BAD` albo `NOTE` (niespodzianki dostają przedrostek `SURPRISE`), a na końcu podsumowanie w stylu `requests: 5 ok, 0 missing, 0 bad`. Claude poprawia każde `MISSING` i `BAD`, zanim cokolwiek ci pokaże.

### „Zaskocz mnie” (niespodzianki)

Gdy prosisz o efekty albo explainery, Claude może dorzucić od siebie 1–3 niespodzianki: efekt na geście, efekt WOW w kluczowym momencie albo stempel na puencie. Są zapisywane jako `[niespodzianka]` i oznaczone na liście w punkcie kontrolnym, więc możesz je skreślić. Powiedz „bez niespodzianek”, żeby je wyłączyć. Zwykłe cięcie bez żadnych próśb nigdy nie dostaje niespodzianek.

## Punkt kontrolny „zrozumiałem tak”

Tuż przed buildem Claude pokazuje ci listę w takim stylu:

```text
zrozumiałem tak:
- [czat] kosmiczne tło → bg @ 0:41                         OK
- [nagranie IMG_6050.MOV 12.3] globus → custom:globe @ S4   OK
- [niespodzianka] wybuch na otwartej dłoni @ 18.2           SURPRISE OK
- [wow] kinetic-word → "+300%" @ S6:wystartowało
```

Odpowiedz OK albo skreśl lub zmień linie („wyrzuć wybuch”, „przesuń globus do następnego zdania”). Claude nanosi twoje zmiany, ponownie uruchamia `cutmate requests` i dopiero wtedy robi build i render. Przy motywie split-panel lista pokazuje też oś czasu panelu, po jednej linii na element (na przykład `0.00–1.40 stat-card 44%`).

Jeśli nie miałeś żadnych próśb, nie ma pauzy: te same informacje trafiają do `EDIT_NOTES.md`.

## Po renderze: uwagi

Obejrzyj `final.mp4` i odpowiedz, podając znaczniki czasu:

```text
1:12 etykieta zasłania mi usta; 2:03 wytnij to „yyy”; 2:40 zrób globus na czerwono
```

Każda uwaga trafia do `requests.md` jako `[uwagi <mm:ss>]`. Wszystkie zmiany są zbierane w jeden ponowny build i jeden render. Gdy poprawka dotyka cięcia (EDL), grafiki automatycznie przesuwają się razem ze swoimi słowami.

## Zapisywanie efektu na później

Gdy Claude napisał dla tego filmu nowy efekt (w `out/custom/<name>.html`), a ty go zaakceptowałeś, Claude raz zapyta, czy zapisać go w twoim motywie:

```bash
cutmate save-effect ~/Videos/caveman-short/out space-bg --description "gwiazdy za mówiącym"
```

Od tej chwili każdy film z tym motywem może go używać. Zobacz [effects.md](effects.md#zapisywanie-efektu).

## Pliki wynikowe

Wszystko, co cutmate generuje, ląduje w `<folder>/out/`:

| Plik | Co to jest |
|---|---|
| `final.mp4` | Gotowy film: 1080×1920 (9:16) albo 1920×1080 (16:9), 30 kl./s, H.264 + AAC, −14 LUFS |
| `thumbnail.png`, `thumbnail.jpg` | Miniatura: 1080×1920 dla shortów, 1280×720 dla 16:9 (gdy `steps.thumbnail` jest włączone) |
| `chapters.txt` | 16:9: znaczniki czasu rozdziałów do wklejenia w opis na YouTube |
| `captions.srt` | Gdy tryb napisów dla danego formatu to `srt` albo `both` (domyślnie dla 16:9) |
| `EDIT_NOTES.md` | Ostateczna struktura, każda grafika i powód jej użycia, muzyka, źródła scen, użyte polecenia |
| `takes.md` | Każde porównane ujęcie, wybrane ujęcie i powód wyboru; kontrole dla każdego fragmentu |
| `factcheck.md` | Jedna linia na twierdzenie: znacznik czasu, cytat, werdykt, poprawna wersja, link |
| `requests.md` | Twoje prośby i niespodzianki od Claude'a |
| `edl.json` | Cięcie: fragmenty z plikiem źródłowym, punktami wejścia / wyjścia i poprawionym tekstem |
| `plan.json` | Grafiki, napisy, panel, sceny, muzyka |
| `aroll.mp4` | Pocięty A-roll (wyrównany głos, bez grafik) |
| `preview.mp4` | Tylko 16:9: podgląd 480p do punktu kontrolnego |
| `composition/` | Projekt HyperFrames (HTML, media, dołączone biblioteki) |
| `snapshots/`, `sheets/`, `check_*.png` | Klatki, które Claude czytał, żeby sprawdzić swoją pracę |
| `work/` | Pliki pośrednie: transkrypcje, pliki WAV, wyrównane słowa, ścieżki śledzenia, `render.log` |

## Jak uzyskać lepsze wyniki

- **Powtarzaj każdą kwestię, aż wyjdzie idealnie.** cutmate porównuje wszystkie ujęcia, więc dodatkowe ujęcia nic cię nie kosztują.
- **Wymawiaj nazwy wyraźnie** i wymień je, gdy zaczynasz montaż (`nazwy produktów: …`). Stają się podpowiedzią dla transkrypcji.
- **Rób krótką pauzę między ujęciami.** Cięcia wypadają na ciszy.
- **Używaj rąk celowo.** Otwarta dłoń skierowana do kamery albo wyraźne wskazanie palcem dają efektom miejsce, w którym mogą się pojawić.
- **Uwagi reżyserskie mów krótko i kieruj je do montażysty** („tu daj …”, „dodaj …”), żeby zostały rozpoznane i wycięte.
