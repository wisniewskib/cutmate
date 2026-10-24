# FAQ

## Ogólne

**Jakie filmy montuje cutmate?**
Filmy typu „gadająca głowa”: jedna osoba mówi do kamery, nagrana w kilku ujęciach. Robi shorty 9:16 (Reels, Shorts, TikTok) i długie filmy 16:9 na YouTube. To nie jest uniwersalny edytor do vlogów z mnóstwem b-rollu, teledysków ani wywiadów z wielu kamer.

**Jakie języki są obsługiwane?**
Polski (`pl`) i angielski (`en`) dla filmu: transkrypcja, wyrównanie i wbudowane etykiety. Zmieniasz go przez `cutmate config set language=en`. Skille i tak rozmawiają z tobą w twoim języku.

**Czy potrzebuję GPU?**
Nie. Bez GPU wybierz backend przez API (Groq jest szybki i tani), a cała reszta działa na CPU. Żeby lokalny Whisper large-v3 miał sens, potrzebujesz GPU NVIDIA albo Apple Silicon. Renderowanie korzysta z headless Chrome i CPU.

**Czy działa na Windowsie?**
Tak. Obsługiwane są Windows, macOS i Linux. Na Windowsie Claude Code uruchamia polecenia przez Git Bash; `setup.ps1` i `detect.ps1` to odpowiedniki skryptów instalacyjnych w PowerShellu. Zobacz [installation.md](installation.md).

**Ile trwa montaż?**
To zależy od twojego komputera i filmu. Orientacyjnie short 9:16 renderuje się około 1–2 minut, a film 16:9 około 45–60 minut na każde 15 minut materiału. Do tego dochodzi transkrypcja i kroki, w których Claude przegląda materiał. Efekty `bg` (wycinanie mówiącego z tła) zajmują na CPU około 17× swojej długości.

**Czy cutmate rusza moje oryginalne nagrania?**
Nigdy. Wszystko, co tworzy, trafia do `<folder>/out/`.

## Prywatność i klucze

**Gdzie trafiają moje klucze API?**
Tylko do zmiennych środowiskowych, które ustawiasz sam (`GROQ_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`). cutmate nigdy nie zapisuje ich do pliku, `cutmate config set` je odrzuca, a `cutmate doctor` pokazuje tylko, czy każdy z nich jest ustawiony. Nigdy nie wklejaj klucza na czat.

**Czy mój dźwięk opuszcza komputer?**
Przy `transcription=local` nie. Przy backendzie przez API dźwięk klipu jest wysyłany do danego dostawcy (przekodowany do małego pliku MP3 mono). Krok fact-check korzysta z wyszukiwania w sieci. Muzyka i obrazy AI przez HeyGen działają tylko wtedy, gdy sam zalogowałeś się do HeyGen.

**Czy Claude loguje się gdzieś albo uruchamia za mnie `sudo`?**
Nie. Polecenia `sudo` i logowania (`heygen auth login --oauth`) uruchamiasz sam, na przykład przez `! <command>` na czacie.

## Montaż

**Czy mogę powiedzieć, czego chcę, bez pisania?**
Tak. Powiedz to w nagraniu, kierując słowa do montażysty („tu daj globus”, „dodaj licznik”). cutmate zamienia te kwestie w prośby i wycina je z filmu. Zobacz [usage.md](usage.md#prośby-na-czacie-albo-powiedziane-w-nagraniu).

**Czym jest „zrozumiałem tak”?**
To punkt kontrolny przed buildem: lista wszystkich próśb i niespodzianek przypisanych do planu, którą zatwierdzasz albo poprawiasz. Zobacz [usage.md](usage.md#punkt-kontrolny-zrozumiałem-tak).

**Czym jest „zaskocz mnie”?**
Przy motywach losuje odważny, przypadkowy wygląd. Podczas montażu Claude dodaje 1–3 efekty-niespodzianki, gdy poprosiłeś o efekty. Powiedz „bez niespodzianek”, żeby to wyłączyć.

**Claude wybrał złe ujęcie. Jak to poprawić?**
Odpowiedz ze znacznikiem czasu i tym, czego chcesz („1:12 użyj innego ujęcia tego zdania”). Poprawka trafia do `requests.md`, EDL się zmienia, a grafiki przesuwają się razem ze swoimi słowami. `takes.md` pokazuje, które ujęcia były porównywane i dlaczego wygrało to jedno.

**Dlaczego nie ma muzyki?**
`music.source` ma domyślnie wartość `none`. Ustaw folder (`cutmate config set music.source=folder music.folder=…`) albo użyj HeyGen po zalogowaniu. Jeśli wybrałeś HeyGen, ale nie jesteś zalogowany, montaż idzie dalej bez muzyki i informuje o tym w `EDIT_NOTES.md`.

**Muzyka jest za głośna albo za cicha.**
`cutmate config set music.volume=0.3` (0–2, domyślnie 0.45). Zainstaluj plugin HyperFrames, żeby podkład ściszał się pod głosem (`cutmate doctor` → `carve: true`).

**Czy mogę dostać plik `.srt` także dla shorta?**
Tak: `cutmate config set captions.9:16=both`. Zobacz [configuration.md](configuration.md#napisy-w-zależności-od-formatu).

**Czy mogę ręcznie edytować `plan.json` albo `edl.json`?**
Tak. To zwykły JSON. Potem uruchom `cutmate build <out>` i `cutmate render <out>` (po zmianie EDL najpierw uruchom `cut`, `align` i `track`). Build waliduje wszystko i nazywa problem, jeśli coś jest nie tak. Formaty opisuje [architecture.md](architecture.md#kontrakty-edljson-i-planjson).

## Motywy i efekty

**Czy mogę użyć stylu jakiegoś twórcy?**
`/cutmate:clone-style` buduje motyw, który *wygląda jak* źródło: paleta, charakter fontów, kształty, napisy, ruch i układ. Nigdy nie kopiuje logotypów, znaków wodnych, tekstu, obrazów ani grafik i używa wyłącznie fontów Google na OFL. Publikując, szanuj prawa twórcy źródła.

**Czy mogę użyć dowolnego fontu?**
Tylko fontów z Google Fonts na licencji SIL Open Font License, a fonty tekstu i nagłówków muszą mieć polskie znaki. `cutmate theme font` sprawdza oba warunki.

**Dlaczego build odrzucił mój efekt?**
Efekty muszą być deterministyczne: bez czasu zegarowego, bez `Math.random`, bez timerów i `requestAnimationFrame`, bez callbacków odtwarzania i wyłącznie z dołączonymi bibliotekami. Komunikat błędu podaje zakazany element. Zobacz [effects.md](effects.md#zasady-determinizmu).

**Dlaczego GSAP nie ma w repozytorium?**
Jego licencja nie pozwala jednoznacznie na rozpowszechnianie. `cutmate vendor` go pobiera i sprawdza każdy plik z przypiętą sumą sha256. Zobacz [libraries.md](libraries.md#gsap).

## Rozwiązywanie problemów

**Coś nie działa. Od czego zacząć?**
Uruchom `cutmate doctor` i porównaj każde pole z tabelą w [installation.md](installation.md#rozwiązywanie-problemów-z-cutmate-doctor). Ponowne uruchomienie `/cutmate:setup` jest bezpieczne: wznawia pracę i powtarza tylko to, czego brakuje.

**Zaktualizowałem plugin i teraz coś się sypie.**
Uruchom raz `/cutmate:setup`. Zauważy, że venv wskazuje na stary folder pluginu, i zainstaluje go ponownie.

**`WARN hyperframes check ran out of time`**
Zajęty albo wolny komputer, a nie błąd. Render idzie dalej.
