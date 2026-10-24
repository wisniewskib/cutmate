# Dostosowywanie cutmate

cutmate jest zbudowany tak, żeby dało się go rozszerzać bez forkowania. Są trzy warstwy, które możesz zrobić po swojemu:

1. **Własny skill** na bazie cutmate: twoje zasady, stosowane przy każdym montażu.
2. **Własne motywy**: wygląd.
3. **Zapisane efekty**: efekty, które Claude napisał dla jednego filmu, używane ponownie w każdym kolejnym.

## 1. Własny skill na bazie `/cutmate:edit`

Skill w Claude Code to folder z plikiem `SKILL.md`. Osobisty skill wrzuć do swojego folderu ze skillami użytkownika:

| System | Ścieżka |
|---|---|
| Linux / macOS | `~/.claude/skills/<name>/SKILL.md` |
| Windows | `%USERPROFILE%\.claude\skills\<name>\SKILL.md` |

Schemat: twój skill **najpierw ustala zasady** (motyw, język, czego zawsze albo nigdy nie robić, twoje CTA, twoje nazewnictwo), a potem **uruchamia skill `cutmate:edit`** na folderze. cutmate robi montaż, a twoje zasady rozstrzygają wybory, które zostawia Claude'owi.

### Pełny przykład: cotygodniowy short o technologii

Zapisz to jako `~/.claude/skills/tech-short/SKILL.md`:

```markdown
---
name: tech-short
description: Montuje mój cotygodniowy short o narzędziach AI w cutmate według moich zasad — motyw neon-pill, polski, stałe CTA, bez niespodzianek, stat-card dla każdej liczby. Używaj, gdy mówię "tech short", "cotygodniowy short" albo "/tech-short <folder>".
---

# /tech-short <folder>

Moje zasady dla każdego cotygodniowego shorta. Zastosuj je, a potem zmontuj film w cutmate.

## 0. CLI

Ustaw raz CLI cutmate (działa na Linuksie, macOS i w Git Bash na Windowsie):
`CM="$(ls "${CUTMATE_HOME:-$HOME/.cutmate}/venv/bin/cutmate" "${CUTMATE_HOME:-$HOME/.cutmate}/venv/Scripts/cutmate.exe" 2>/dev/null | head -1)"; [ -n "$CM" ] || CM="$(command -v cutmate)"`
Jeśli się nie uruchamia, powiedz mi, żebym uruchomił /cutmate:setup, i zakończ.

## 1. Ustawienia dla tego filmu

- Język tego montażu to polski: powiedz o tym w prośbie do `/cutmate:edit` („język: polski”, tylko dla tego montażu) zamiast zmieniać konfigurację. `config set` to trwała, globalna zmiana, która dotyczy wszystkich kolejnych montaży.
- Motyw: zawsze `neon-pill` (przekaż go do cutmate:edit jako „użyj motywu neon-pill”). Jeśli `"$CM" theme list`
  nie ma `neon-pill`, powiedz o tym i użyj motywu z konfiguracji.
- Napisy: wypalone dla 9:16 (domyślne w konfiguracji). Nigdy nie zmieniaj innych kluczy konfiguracji.

## 2. Moje zasady (przekaż je wszystkie cutmate:edit na starcie)

- Nazwy do podpowiedzi transkrypcji: Claude Code, Anthropic, GitHub, MCP oraz każdy produkt wymieniony w nazwie folderu.
- **Bez niespodzianek**: tylko efekty, o które proszę, i standardowe komponenty.
- Explainery: tak. Każda wypowiedziana liczba dostaje `stat-card`, a każdy wymieniony produkt swoją prawdziwą stronę przez
  `"$CM" shot "<url>" -o "<folder>/broll/<name>.png" --light` (nowa nazwa pliku; nigdy nie nadpisuj istniejącego pliku w `broll/`).
- Efekty WOW: najwyżej jeden na short, `kinetic-word` na NAJWAŻNIEJSZEJ liczbie filmu. Nigdy `burst-out`.
- Hak: najmocniejsza kwestia na początku, najwyżej 3 s. Koniec na moim CTA („Napisz NARZĘDZIA w komentarzu, a wyślę ci listę.”).
  Jeśli żadne ujęcie nie zawiera CTA, powiedz mi o tym przed cięciem — nie wymyślaj go.
- Miniatura: tytuł to obietnica filmu w najwyżej 4 słowach, wielkimi literami; hak to pytanie, które zadaję.
- Nigdy nie zostawiaj ujęcia, w którym patrzę w notatki.

## 3. Montaż

Uruchom skill `cutmate:edit` z `<folder>` i całą sekcją 2 jako prośbą. Przejdź wszystkie punkty kontrolne cutmate
jak zwykle (zatrzymania przy fact-checku, „zrozumiałem tak”).

## 4. Po renderze

- Nie kopiuj `final.mp4` poza `out/`: zostaw go tam, gdzie powstał.
- Napisz `<folder>/out/POST.md`: tytuł (≤ 60 znaków), 2-linijkowy opis i 5 hashtagów, wyłącznie na podstawie transkrypcji.
- Podaj mi w trzech liniach ścieżkę do filmu (`<folder>/out/final.mp4`), miniatury i POST.md.
```

Potem w Claude Code:

```text
/tech-short ~/Videos/2026-10-24-mcp-servers
```

**Dlaczego to działa:**

- Skille cutmate czytają twoje prośby tak samo, niezależnie od tego, czy przychodzą z czatu, czy z innego skilla. Wszystko z sekcji 2 trafia do `requests.md` i punktu kontrolnego „zrozumiałem tak”, więc dalej możesz to zobaczyć i skreślić.
- Twoje zasady tylko zawężają wybory, które cutmate zostawia Claude'owi: jakie efekty, ile, hak, motyw. Gwarancje samego cutmate nadal obowiązują: nietykanie klipów źródłowych, limity WOW i zasady gęstości. Fact-check (gdy włączony) nadal wykonuje Claude, a build ostrzega tylko o części liczb.
- Linia z CLI jest taka sama jak w skillach cutmate, więc działa na wszystkich trzech systemach.

### Wskazówki do własnego skilla

- **Trwałe ustawienia trzymaj w kluczach konfiguracji** (`cutmate config set …`), a zasady dla pojedynczych filmów w treści skilla.
- **Używaj słów samego cutmate** na jego funkcje: „explainery”, „bez niespodzianek”, nazwy efektów WOW, nazwy komponentów (`stat-card`, `stamp`, `chip`). To terminy, które rozpoznaje jego skill.
- **Nie implementuj kroków od nowa.** Niech `cutmate:edit` transkrybuje, wybiera ujęcia i renderuje. Dodawaj kroki przed (sprawdzenie folderu, nazwy) albo po (kopiowanie, notatki do posta).
- **Pisz przenośne polecenia**: bierz ścieżki w cudzysłów, używaj `"$CM"` i unikaj narzędzi dostępnych tylko na Linuksie w krokach, które mają działać też w Git Bash na Windowsie.

## 2. Własne motywy

Najprościej użyć `/cutmate:theme` albo `/cutmate:clone-style` (zobacz [themes.md](themes.md)). Żeby zbudować albo podrasować motyw ręcznie, pracuj na **szkicu** i pozwól, żeby zatwierdziła go bramka kontrolna:

```bash
cutmate theme new my-look --from clean --mode custom       # szkic w ~/.cutmate/themes/.drafts/my-look/
cutmate theme font my-look "Space Grotesk" --role display
cutmate theme font my-look "Manrope" --role text
# edytuj tokens.css (kolory, --radius, --shadow), theme.css (napisy), components/*.html, theme.json (sfx), frame.md
cutmate theme check my-look --clip ~/Videos/take1.mp4      # lint + render obu formatów → check/contact.png
cutmate theme save my-look
cutmate theme use my-look
```

Co zmieniać, od najbezpieczniejszego do najbardziej zaawansowanego:

| Zmiana | Gdzie | Uwagi |
|---|---|---|
| Kolory, narożniki, cienie | `tokens.css` | Przestylowuje naraz każdy komponent, explainer i efekt WOW. Zachowaj wymagane tokeny i kontrast (≥ 4.5). |
| Fonty | `cutmate theme font` | Tylko fonty Google na OFL z polskimi znakami; nigdy nie edytuj bloków `cutmate:font` ręcznie |
| Styl napisów | `theme.css` → `.cw`, `.cw.key`, `.cw.num` | Zachowaj `opacity: 0` w `.cw` i zasady stref bezpiecznych |
| Dźwięk dla komponentu | `theme.json` → `sfx` | Nazwy dźwięków: `whoosh`, `pop`, `click`, `impact`, `swell`, `ping` |
| Wygląd komponentu | `components/<type>.html` | Zachowaj strukturę i parametry wersji z clean: skill montażowy opiera się na kontrakcie komponentu |
| Zasady, którymi kieruje się Claude | `frame.md` | Strefy, budżety, gęstość i komponenty; zachowaj sekcje z zasadami |
| Układ | `theme.json` → `layout` | `split-panel` wymaga `--panel-bg` (zobacz [themes.md](themes.md#układy)) |

Standardowe explainery i efekty WOW (`components/custom/*`) zostaw w spokoju: przejmują twój wygląd wyłącznie przez tokeny.

**Udostępnianie motywu:** motyw to zwykły folder. Skopiuj `~/.cutmate/themes/<name>/` do `~/.cutmate/themes/` innej osoby, a potem raz uruchom `cutmate theme check <name> --saved`, zanim zaczniesz go używać. Udostępniaj tylko fonty na OFL (ich pliki `OFL-*.txt` są w `fonts/`).

## 3. Zapisane efekty

Gdy Claude napisze efekt dla jednego filmu (`out/custom/<name>.html`), a tobie się spodoba, zapisz go w swoim motywie:

```bash
cutmate save-effect ~/Videos/short/out space-bg --description "gwiazdy za mówiącym"
cutmate save-effect ~/Videos/short/out space-bg --theme my-look --force
```

| Co się dzieje | Gdzie |
|---|---|
| Efekt jest lintowany ([zasady determinizmu](effects.md#zasady-determinizmu)) | |
| HTML i jego folder z zasobami są kopiowane | `~/.cutmate/themes/<theme>/components/custom/<name>.html` i `<name>/` |
| Zapisywany jest wpis z twoim opisem, parametrami, z którymi efekt był użyty, i jego trybem `follow` | `~/.cutmate/themes/<theme>/components/custom/index.json` |

Przy kolejnych montażach Claude czyta zarówno wbudowany `index.json`, jak i twój, zanim napisze cokolwiek nowego. Prośba o „to kosmiczne tło jeszcze raz” użyje twojego efektu. Możesz też sam napisać efekt w `<folder>/out/custom/<name>.html` i użyć go w planie jako `{"type": "custom", "name": "<name>", …}`. API i zasady są opisane w [effects.md](effects.md#własne-efekty-pisane-przez-claudea).

> `--theme` domyślnie bierze motyw z konfiguracji. Efekty są zawsze zapisywane w `~/.cutmate/themes/<theme>/components/custom/`, nawet dla wbudowanego `clean`, a cutmate szuka tam, zanim sięgnie po efekty samego pluginu. Sam folder pluginu nigdy nie jest modyfikowany. Kolejność szukania efektu po nazwie: `out/custom/`, potem folder twojego motywu, potem motyw pluginu, a na końcu standardowe efekty w `clean`.
