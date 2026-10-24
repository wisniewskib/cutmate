# Motywy

Motyw (theme) decyduje o tym, jak wyglądają twoje filmy: styl napisów, fonty, kolory, kształt i ruch każdej grafiki, efekty dźwiękowe i układ kadru. cutmate ma w zestawie jeden neutralny motyw, `clean`. Własnych możesz zrobić tyle, ile chcesz.

## Skąd wziąć motyw

| Sposób | Skill | Co dostajesz |
|---|---|---|
| Clean | brak | Neutralny wygląd na start: Inter, białe napisy z miękkim cieniem, białe zaokrąglone karty, jeden błękitny akcent (`#7dd3fc`) |
| 🎲 „Zaskocz mnie” | `/cutmate:theme` | Losowy, odważny wygląd: paleta, para fontów, kształty, ruch, napisy. Możesz losować ponownie, aż ci się spodoba. |
| Własne kolory i fonty | `/cutmate:theme` | Sam wybierasz akcent, kolor kart, fonty, kształty, ruch i układ |
| Klon stylu | `/cutmate:clone-style` | Motyw wyglądający jak rolka, film, zrzuty ekranu albo folder, który ci się podoba |
| Zmiana aktywnego motywu | `/cutmate:theme` | Ustawia zapisany motyw jako domyślny |

`/cutmate:setup` też pyta, jak mają wyglądać twoje filmy, i uruchamia za ciebie jedną z tych opcji.

## Gdzie są motywy

| Rodzaj | Lokalizacja | Uwagi |
|---|---|---|
| Wbudowany | `<plugin>/themes/clean/` | Nigdy nie jest edytowany |
| Twój (zapisany) | `~/.cutmate/themes/<name>/` | Używany przez twoje filmy |
| Szkice | `~/.cutmate/themes/.drafts/<name>/` | Praca w toku. Twoje filmy nie zmieniają się, dopóki nie zapiszesz. |
| Kopie zapasowe | `~/.cutmate/themes/.backup/<name>-<timestamp>/` | Stara wersja, gdy nadpisujesz zapisany motyw |

```bash
cutmate theme list
```

wypisuje jedną linię na motyw, z polami rozdzielonymi tabulatorem: `marker  name  kind  checked  path`. Znacznik `*` oznacza obecny motyw domyślny, kind to `bundled`, `user` albo `draft`, a checked to `checked`, `unchecked` albo `-`.

## Używanie motywu

- **Jako domyślny:** `cutmate theme use <name>` albo `cutmate config set theme=<name>`.
- **Dla jednego filmu:** podaj go, gdy zaczynasz montaż („użyj motywu neon-pill”). Claude przekazuje `--theme <name>` do `build`, `preview` i `thumb`.

## 🎲 „Zaskocz mnie”: losowanie

`cutmate theme new --mode random` losuje kierunek z takich składników:

| Składnik | Opcje |
|---|---|
| Paleta | 12 palet (6 z jasnymi kartami, 6 z ciemnymi), akcenty rozłożone po całym kole barw: paper-red, bubblegum, arctic, mint, sand, violet, noir, lime, ocean, magenta, coral, periwinkle |
| Para fontów (nagłówki / tekst) | Anton / Inter, Oswald / Lato, Archivo Black / Archivo, Space Grotesk / Manrope, Syne / Rubik, Unbounded / Manrope, Bricolage Grotesque / DM Sans, DM Serif Display / DM Sans, Playfair Display / Source Sans 3, Fraunces / Work Sans, Space Mono / Space Grotesk, Caveat / Lato, Titan One / Rubik, Bangers / Manrope |
| Kształty | `sharp`, `pill`, `outline`, `brutal`, `tape` |
| Ruch | `snappy`, `smooth`, `glitch`, `typewriter`, `slam` |
| Napisy | `shadow`, `boxed`, `outline`, `highlight` |

Potem Claude przerabia szkic (fonty, tokeny, napisy i każdy komponent wyglądu: title, counter, list, chip, stamp, bars, lower-third, chapter, point), renderuje go i pokazuje ci arkusz klatek. Wybierz **Losuj jeszcze raz**, żeby dostać kolejny. `--avoid <draft>` trzyma nowe losowanie z dala od wcześniejszych, a `--seed N` sprawia, że losowanie da się powtórzyć.

Losowanie nigdy nie wybiera układu. Losowy motyw zostaje klasyczny, chyba że poprosisz o panel.

## Własne kolory i fonty

`/cutmate:theme` → **Własne kolory i fonty** pyta o:

1. **Akcent** (czerwony, żółty, limonkowy, fioletowy albo dowolna nazwa / hex) i **karty** (ciemne, jasne albo w danym kolorze).
2. **Fonty**: dopasowane do stylu, krzykliwe (Anton, Archivo Black), eleganckie szeryfowe (DM Serif Display, Fraunces), techniczne (Space Grotesk, Space Mono) albo dowolny font Google, który podasz.
3. **Kształty, ruch i układ**: klasyczny albo **panel u góry** (zobacz [Układy](#układy)).
4. **Nazwę** (litery, cyfry, `_`, `-`).

Resztę palety Claude wylicza sam i sprawdza kontrast.

## Klonowanie stylu

`/cutmate:clone-style <source>` przyjmuje:

- **link** do rolki albo filmu. Za twoją zgodą pobiera jeden publiczny film przez `yt-dlp`, wyłącznie do analizy stylu. Nigdy nie używa ciasteczek ani logowania. `yt-dlp` instalujesz sam (`pipx install yt-dlp`, `winget install yt-dlp`, `brew install yt-dlp`).
- **lokalny film**, **zrzuty ekranu** albo **folder** z nimi.

Claude czyta arkusze klatek źródła (najwyżej 2 filmy i 4 arkusze), zbliżenia wejść grafik (ruch) i pełnowymiarowe kadry. Uruchamia `cutmate theme colors`, żeby dostać dokładne wartości hex, a potem mówi ci, co widzi: paletę, fonty, kształty, napisy, ruch, gęstość i układ. Po twoim OK buduje motyw i porównuje go ze źródłem **obok siebie** (jeden obraz zbiorczy na porównanie), przez najwyżej 3 rundy.

**Czego nigdy się nie kopiuje:** logotypów, znaków wodnych, nazw kont, tekstu źródła, jego obrazów i grafik. Fonty pochodzą wyłącznie z Google Fonts na licencji OFL. Motyw *wygląda jak* źródło, ale jest twoją własną pracą. Pliki robocze trafiają do `~/.cutmate/clone/<name>/` i możesz je potem usunąć.

### Przechwytywanie układu

Klon przechwytuje nie tylko wygląd, ale też **układ**. Jeśli w większości klatek źródła na ekranie stale jest panel, klon staje się motywem `split-panel`. Bierze wtedy pozycję panelu i jego udział w kadrze, to, jak często zmienia się jego zawartość, gdzie są napisy, ile scen pełnoekranowych pojawia się na minutę i kolor panelu.

## Układy

| Układ | Format | Jak wygląda |
|---|---|---|
| `classic` (domyślny) | 9:16 i 16:9 | Grafiki pojawiają się i znikają na tle twarzy. Explainery w podzielonym panelu pojawiają się tylko wtedy, gdy o nie poprosisz. |
| `split-panel` | Tylko 9:16 (film 16:9 go ignoruje) | Górna część kadru to **jeden stały panel** przez cały film, w którym pojawiają się explainery, makiety aplikacji / przeglądarki, tabele statusu, duże liczby i zrzuty stron, zmieniające się co 1–3 s. Ty jesteś w dolnej części, a napisy siedzą na styku. Od czasu do czasu sceny pełnoekranowe. |

Motyw split-panel deklaruje swój układ w `theme.json`:

```json
"layout": {"mode": "split-panel", "ratio": 0.5, "cadence": [1.0, 3.0], "captions": "seam", "transition": "cut", "fullscreen": {"max_per_min": 3}}
```

| Klucz | Wartości | Domyślnie |
|---|---|---|
| `mode` | `classic`, `split-panel` | `classic` |
| `panel` | `top` | `top` |
| `ratio` | Udział panelu w wysokości kadru, 0.40–0.60 | 0.5 |
| `cadence` | `[min, max]` sekund na element panelu, 0.5 ≤ min < max ≤ 6 | `[1.0, 3.0]` |
| `captions` | `seam`, `bottom` | `seam` |
| `transition` | `cut`, `fade` | `cut` |
| `fullscreen.max_per_min` | Sceny pełnoekranowe na minutę, 0–6 | 3 |

Motyw split-panel potrzebuje też `--panel-bg` w `tokens.css` (lint to sprawdza). W tym układzie explainery są włączone bez proszenia: Claude planuje jeden element panelu na każdą część zdania.

## Budowa folderu motywu

```text
<name>/
├── theme.json        # nazwa, akcent, fonty, sfx dla komponentów, sfx uderzenia, kierunek, opcjonalny układ
├── tokens.css        # tokeny kolorów / kształtów + bloki @font-face (zapisywane przez `cutmate theme font`)
├── theme.css         # style napisów (.cw, .cw.key, .cw.num) i strefy bezpieczne
├── frame.md          # zasady, które Claude czyta przed napisaniem plan.json (strefy, budżet, gęstość, komponenty)
├── fonts/            # pliki TTF + tekst ich licencji OFL
├── components/       # title, counter, list, chip, stamp, bars, point, split, pip, lower-third, chapter,
│                     # bg, side, panel, panel-media, scene (.html)
│   └── custom/       # efekty: explainery, pakiet WOW, VFX + index.json
└── check/            # contact.png, sheet-9x16.png, sheet-16x9.png (zapisywane przez `cutmate theme check`)
```

### Tokeny

Każdy komponent, explainer i efekt WOW czyta motyw **wyłącznie przez zmienne CSS (custom properties)**, więc zmiana tokenów przestylowuje wszystko naraz.

| Token | Rola | Wymagany |
|---|---|---|
| `--accent` | Słowa kluczowe, liczby, wyróżnienia, krawędź styku panelu | Tak |
| `--on-accent` | Tekst na wypełnieniach w kolorze akcentu (kontrast ≥ 4.5 z `--accent`) | Zalecany |
| `--text` | Kolor napisów | Tak |
| `--ink` | Tekst na kartach (kontrast ≥ 4.5 z `--card`) | Tak |
| `--card` | Tło kart / grafik | Tak |
| `--muted` | Etykiety na kartach | Tak |
| `--shadow` | Cień kart (twarde przesunięcie dla brutal, `none` dla sharp, miękkie rozmycie dla pill) | Tak |
| `--radius` | Promień zaokrąglenia kart i elementów panelu | Zalecany |
| `--panel-bg` | Kolor panelu w split-panel | Tak dla split-panel |
| `--font`, `--font-display` | Font tekstu, font nagłówków | Tak |
| `--font-num` | Font cyfr, gdy cyfry fontu nagłówków wyglądają jak litery | Opcjonalny |
| `--spark`, `--spark-glow` | Kolory iskier dla `hand-control` | Opcjonalny |
| `--glitch-a`, `--glitch-b` | Kolory duchów RGB dla `topic-change` | Opcjonalny |

`theme.json` → `accent` musi być dokładnie równy `--accent`.

Tokeny motywu clean:

```css
:root {
  --accent: #7dd3fc;
  --text: #ffffff;
  --ink: #0f172a;
  --muted: #475569;
  --card: rgba(255, 255, 255, 0.94);
  --panel-bg: #0b0b0f;
  --radius: 28px;
  --shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
}
```

### Fonty (tylko OFL)

Fonty dodaje się wyłącznie przez `cutmate theme font`. Polecenie pobiera statyczne grubości (400–900) **rodziny z Google Fonts na licencji SIL Open Font License**, zapisuje jej licencję `OFL-<family>.txt` obok plików TTF, sprawdza, czy rodzina ma polskie znaki (ą ę ł ń ó ś ź ż), i przepisuje bloki `cutmate:font` w `tokens.css`.

```bash
cutmate theme font my-theme "Anton" --role display
cutmate theme font my-theme "Manrope" --role text
cutmate theme font my-theme "VT323" --role num      # tylko cyfry, gdy 5 w foncie nagłówków wygląda jak S
cutmate theme digits my-theme                        # renderuje "-75% 0123456789" obok podobnych liter
```

Rodzina, która nie jest na OFL albo nie ma jej w Google Fonts, zostaje odrzucona. Fonty trafiają do **szkicu**, nigdy prosto do zapisanego motywu. Clean ma w zestawie Inter (OFL 1.1, `themes/clean/fonts/OFL-inter.txt`).

### Efekty dźwiękowe

`theme.json` → `sfx` przypisuje każdemu komponentowi dźwięki z dołączonego zestawu (`whoosh`, `pop`, `click`, `impact`, `swell`, `ping`, wszystkie na CC0 z Kenney.nl). W `plan.json` możesz wyciszyć pojedynczą grafikę przez `"sfx": false` albo podmienić jej dźwięk przez `"sfx": "impact"`.

## Bramka kontrolna

Motyw zostaje zapisany dopiero wtedy, gdy przejdzie `cutmate theme check`:

```bash
cutmate theme check my-theme                       # lint + render każdego komponentu w 9:16 i 16:9
cutmate theme check my-theme --clip take1.mp4      # twoje nagranie zamiast obrazu testowego
cutmate theme save my-theme                        # przenosi sprawdzony szkic do ~/.cutmate/themes/
cutmate theme save my-theme --force                # nadpisuje zapisany motyw (stary trafia do .backup)
cutmate theme use my-theme
```

Kontrola lintuje motyw (wymagane tokeny, kontrast, układ oraz to, czy motyw losowy / klon nie jest po prostu clean w nowych kolorach), renderuje każdy komponent w obu formatach i zapisuje `check/contact.png` (dla wbudowanego `clean`: `~/.cutmate/checks/clean/contact.png`). Ten arkusz klatek ma trzy rzędy: wejścia (ruch), ustabilizowane grafiki 9:16 i narożne grafiki 16:9. Szkic zmieniony po ostatniej kontroli trzeba sprawdzić ponownie przed `save`.

## Co dalej

- Efekty, które biorą tokeny z twojego motywu: [effects.md](effects.md)
- Budowanie motywu ręcznie i zapisywanie w nim efektów: [customizing.md](customizing.md)
