# Efekty

Poza napisami i podstawowymi komponentami cutmate ma trzy poziomy animowanych efektów:

1. **Explainery**: animowane wyjaśnienia tego, co mówisz (liczba, kroki, narzędzie, mechanizm).
2. **Pakiet WOW**: sześć sprawdzonych efektów, które robią wrażenie w kluczowych momentach filmu.
3. **Własne efekty**: pisane przez Claude'a, gdy prosisz o coś, czego nic innego nie pokrywa, i zapisywane w twoim motywie, gdy ci się spodobają.

Wszystkie biorą tokeny z twojego motywu (kolory, fonty, zaokrąglenia, cień), więc sklonowany styl też je przestylowuje. Działają poprawnie przy przewijaniu (seek-safe) i są deterministyczne (zobacz [zasady](#zasady-determinizmu)), a renderują się offline z dołączonych bibliotek.

Efekty są zdefiniowane w `themes/clean/components/custom/` (każdy w osobnym pliku `.html`), a `index.json` opisuje ich parametry. Claude czyta `index.json`, zanim użyje efektu.

## Kiedy efekty są używane

| Układ motywu | Explainery | Efekty WOW | Własne efekty |
|---|---|---|---|
| Classic (9:16 albo 16:9) | Tylko gdy poprosisz („dodaj explainery”, „wytłumacz to animacją”) | Gdy prosisz o efekty albo gdy niespodzianki są włączone | Na życzenie |
| Split-panel (9:16) | Zawsze: wypełniają panel, jeden element na każdą część zdania | `exploded-view` / `globe` jako elementy panelu, `kinetic-word` / `topic-change` jako sceny, `hand-control` nad połową kadru z mówiącym | Na życzenie |

W motywie klasycznym Claude wybiera 2–4 explainery na 60 s, każdy trwa co najmniej 2 s, a między nimi jest co najmniej 2 s samej twarzy.

## Wbudowane komponenty (ściąga)

To podstawowe grafiki dostępne w każdym motywie (`plan.json` → `graphics`):

| Komponent | Zastosowanie | Główne pola |
|---|---|---|
| `title` | Przedstawienie się albo temat (najwyżej 1) | `at`, `text`, `kicker?`, `logo?` |
| `counter` | NAJWAŻNIEJSZA liczba filmu, odliczana w górę | `at`, `to`, `prefix?`, `suffix?`, `label` |
| `list` | Wypowiadana lista (≤ 4 punkty) | `items[{text, at}]`, `head?` |
| `chip` | Mała etykieta z nazwą / narzędziem | `at`, `text`, `logo?` / `icon?` |
| `stamp` | Puenta w jednym słowie | `at`, `text` |
| `bars` | Porównanie (≤ 3 wiersze) | `at`, `head`, `rows[{label, value}]`, `illustrative` |
| `point` | Karta przy palcu, gdy coś wskazujesz | `at`, `image`, `corner` |
| `split` | 9:16: panel z b-rollem u góry, twarz na dole | `from`, `to`, `media` albo `effect` + `params` |
| `pip` | 16:9: b-roll na pełnym ekranie, twarz w kółku | `from`, `to`, `media`, `corner?`, `fit?` |
| `lower-third` | 16:9: imię i rola, raz, gdy się przedstawiasz | `at`, `name`, `role?` |
| `side` | 16:9: mówiący na jednej połowie, grafika na drugiej | `from`, `to`, `media` albo `effect`, `speaker` |
| `bg` | Podmienia tło za mówiącym | `from`, `to`, `media` albo `effect` |
| `custom` | Dowolny efekt po nazwie | `name`, `from`/`to` albo `at`/`until`, `params`, `follow?`, `place?` |

Każda grafika może też przyjąć `until`, `hit` (dźwięk uderzenia i wstrząs) oraz `sfx`. Kotwice to `"S2:word"`, `"S2:word#2"` albo sekundy.

## Explainery

| Efekt | Wybierany dla | Kluczowe parametry |
|---|---|---|
| `stat-card` | Liczby | `value` (odliczana w górę), `prefix?`, `suffix?`, `label`, `note?`, `media?` (przyciemniony zrzut ekranu w tle), `accent?`, `layout` `card` \| `hero` |
| `flow` | Kroków / procesu | `nodes` (2–6), `edges?`, `style` `clean` \| `rough` (rysowany odręcznie), `seed?`, `title?`, `accent?` |
| `ui-mock` | Narzędzia, czatu, polecenia, strony | `kind` `chat` \| `terminal` \| `post` \| `browser` \| `app`; `lines` (chat / terminal / post); `url`, `search?`, `rows`, `highlight?` (browser); `title`, `search?`, `rows` z `toggle?` / `click?` (app); `replies?` / `reposts?` / `likes?` (post: tylko prawdziwe liczby) |
| `iso-machine` | Mechanizmu, „jak to działa” | `parts` (2–5, kształty `box`, `cylinder`, `funnel`, `screen`, `gear`), `token?` `cube` \| `sphere`, `counter?` `{to, label}`, `title?`, `theme` `light` \| `dark` \| `panel` |
| `checklist` | Sprawdzenia / porównania | `rows` (2–8, status `ok`, `bad`, `warn`, `info`, `label?`), `strike?`, `summary?` `{value, suffix?, label?}`, `title?` |
| `headline` | Kluczowej frazy bez liczby, produktu i kroków | `text` (1–6 słów), `kicker?`, `mode` `type` \| `pop` |

W klasycznym filmie 9:16 explainer trafia do `split` (panel 1000×820), a w 16:9 do `side`:

```json
{"type": "split", "from": "S3:Claude", "to": "S3:linki.", "effect": "stat-card",
 "params": {"value": 50, "suffix": "%", "label": "linków nie działa"}}
```

**Tekst i liczby pochodzą wyłącznie z tego, co zostało powiedziane.** Liczba w explainerze musi być potwierdzona linią ✅ w `factcheck.md`. Build ostrzega tylko o `value` w `stat-card` i `summary.value` w `checklist`; resztę Claude sprawdza sam.

### 3D i VFX

| Efekt | Co robi | Kluczowe parametry |
|---|---|---|
| `showcase-3d` | Główny obiekt 3D wlatuje obok mówiącego, obraca się i wylatuje | `shape` `torus-knot` \| `icosahedron` \| `text` \| `glb`, `text?`, `model?`, `color?`, `size?`, `x?`, `y?` |
| `burst` | Jednorazowe uderzenie energii (~1–1,4 s): błysk, fale uderzeniowe, iskry | `colors?`, `size?` (1.2–1.6 na kluczowy moment), `x?`, `y?` |
| `hand-sparks` | Energia wylewająca się z dłoni | `mode` `stream` \| `sparks`, `link?` (łuk między dłońmi), `colors?`, `size?` |
| `energy-ball` | Wirująca kula energii na dłoni, która podąża za ręką | `radius?`, `colors?`, `x?`, `y?` |

Wszystkie cztery obsługują `"place": "gesture"`. `energy-ball` i `hand-sparks` podążają za dłonią.

## Pakiet WOW

Sześć gotowych efektów robiących wrażenie (`"kind": "wow"` w `index.json`). Gdy któryś z nich pasuje do momentu, używa się go zamiast pisać nowy efekt.

| Efekt | Moment | Tryby | Długość |
|---|---|---|---|
| `exploded-view` | „Rozbierzmy to na części”, „co jest w środku”, warstwy, wyjaśnianie urządzenia albo systemu | panel, scene, side, overlay | 3–4,5 s |
| `globe` | „Na całym świecie”, kraje, miasta, globalna liczba | panel, scene, side | 3–5 s |
| `burst-out` | Wielkie odsłonięcie: „to zmienia wszystko”, „poznajcie …”, nazwa produktu wypowiedziana z naciskiem | bg (tylko classic) | 3–5 s |
| `hand-control` | Otwarta dłoń skierowana do kamery, gest „czarowania” | overlay | 3–6 s |
| `topic-change` | Zmiana rozdziału, „teraz…”, „przechodzimy do”, „druga rzecz” | overlay, scene, chapter | 1,2–2,0 s |
| `kinetic-word` | NAJWAŻNIEJSZE słowo albo liczba filmu: premiera, „+300%”, „ZA DARMO” | scene, overlay | 2,5–6 s (najlepiej czyta się 3–4) |

### `exploded-view`

Rozłożony widok produktu w 3D. Złożony obiekt obraca się w kadr, jego części rozsuwają się z ponumerowanymi etykietami na liniach odniesienia, kamera krąży wokół, a potem wszystko z trzaskiem składa się z powrotem z błyskiem.

| Parametr | Wartości |
|---|---|
| `parts` | 2–7 elementów `{"label", "shape", "color"?}` od dołu do góry. Kształty: `block`, `cylinder`, `disc`, `ring`, `gear`, `board`, `screen`, `shell` |
| `preset` | Gdy brakuje `parts`: `engine` (domyślnie), `phone`, `layers`; etykiety w języku filmu |
| `axis` | `y` (pionowy stos, domyślnie) albo `x` (poziomo) |
| `title` | Opcjonalny nagłówek |
| `bg` | `panel` (`--panel-bg` z motywu, domyślnie) albo `none` (przezroczyste tło nad filmem) |

### `globe`

Jasny, kropkowany globus 3D. Obraca się do kraju początkowego, z niego wystrzeliwują łuki w kolorze akcentu do każdego celu i lądują pulsującymi pinezkami, a na końcu „dekodują się” etykiety krajów.

| Parametr | Wartości |
|---|---|
| `from` | Punkt startowy, kod ISO-2 (na przykład `"PL"`) |
| `to` | 1–6 kodów ISO-2 celów |
| `labels` | `auto` (nazwy krajów w języku filmu) albo lista nazw |
| `style` | `dots` (domyślnie) albo `solid` |
| `title` | Opcjonalny nagłówek |

Dane krajów pochodzą z Natural Earth (domena publiczna) i są wbudowane w `globe/land.json` oraz `globe/countries.json`.

### `burst-out`

Obiekt 3D wybucha zza głowy mówiącego razem ze snopami światła, przelatuje łukiem nad nim i leci na kamerę. Na słowie uderzenia płótno wskakuje na pierwszy plan z pulsem rozszczepienia RGB, iskrami, falą uderzeniową i wstrząsem kadru. Potem obiekt zatrzymuje się obok mówiącego (nigdy na twarzy, nad napisami) i odlatuje, wirując.

```json
{"type": "bg", "from": "S4:to", "to": "S4:wszystko.", "effect": "burst-out", "hit": "S4:Claude",
 "params": {"shape": "gem", "label": "Claude Code"}}
```

| Parametr | Wartości |
|---|---|
| `shape` | `gem` (domyślnie), `cube`, `knot`, `sphere`, `logo` (obraz z `media` na zaokrąglonej, wytłoczonej karcie) |
| `color` | Opcjonalny (domyślnie `--accent`) |
| `rays` | Snopy światła (domyślnie `true`) |
| `label` | Opcjonalny tytuł, który „dekoduje się” pod obiektem po uderzeniu |
| `media` | Obraz logo dla `shape: "logo"` |

Zakotwicz `hit` na słowie uderzenia, zacznij co najmniej 1 s przed nim i skończ co najmniej 1,5 s po nim. `burst-out` potrzebuje pozycji twarzy (ze śledzenia albo z `face` w planie). To efekt typu `bg`: wycina mówiącego z tła (`remove-background` z HyperFrames), co na CPU zajmuje około 17× długości efektu. Tylko układy klasyczne, raz na short.

### `hand-control`

Magia na twojej prawdziwej dłoni. Z każdego wyprostowanego palca sypią się ciepłe smugi iskier, a gdy twoja dłoń jest otwarta w stronę kamery, nad palcami rozkłada się karta w stylu motywu, podąża za ręką i składa się z powrotem w dłoń, gdy ją zamkniesz.

```json
{"type": "custom", "name": "hand-control", "from": "S5:patrzcie", "to": 21.5,
 "params": {"card": {"title": "Sterowanie gestem", "lines": ["Iskry z każdego palca", "Karta na otwartej dłoni"]}}}
```

| Parametr | Wartości |
|---|---|
| `card` | `{"title", "lines" (≤ 3), "media"?}`: to, o czym właśnie mówisz |
| `sparks` | `tips` (domyślnie) albo `off` |
| `hand` | `auto` (uniesiona otwarta dłoń, domyślnie), `left`, `right`: **twoja własna** ręka, więc przy nieodbitym obrazie z kamery `right` jest po lewej stronie ekranu |
| `colors` | Opcjonalnie `[core, body, glow]` (domyślnie `--spark` / `--spark-glow` albo ciepły bursztyn) |
| `media` | Opcjonalny obraz na karcie |

Potrzebuje śladów czubków palców, więc uruchom raz `cutmate track --force <out>`, gdy build o to poprosi. Działa w 9:16 classic, w 9:16 split-panel (w połowie kadru z mówiącym) i w 16:9. Nigdy nie jest elementem panelu ani sceną.

### `topic-change`

Sam A-roll glitchuje przez 0,6 s (rozszczepienie RGB albo fala), pojawiają się paski i linie skanowania, tytuł wyłania się z potrójnego rozszczepienia RGB, a kicker wpisuje się literka po literce. Kończy się twardym cięciem i 2-klatkowym białym błyskiem.

| Parametr | Wartości |
|---|---|
| `title` | Następny temat, ≤ 40 znaków |
| `kicker` | Opcjonalna mała etykieta (plansze rozdziałów: `ROZDZIAŁ 02`) |
| `style` | `glitch` (domyślnie) albo `wave` |

W długich filmach `"chapter_fx": "topic-change"` na najwyższym poziomie `plan.json` zamienia w ten efekt każdą planszę rozdziału od rozdziału 2. Plansze rozdziałów nie liczą się do limitów WOW.

### `kinetic-word`

Pełnoekranowe uderzenie zrobione w anime.js. Około 600 kształtów w stylu motywu wyskakuje jako siatka, rozchodzi się falą, wybucha i wlatuje w kształty liter twojego słowa. Słowo ląduje z uderzeniem kamery, pierścieniem, podkreśleniem i rozbłyskiem, „oddycha”, gdy stoi, a potem rozpada się na kawałki.

| Parametr | Wartości |
|---|---|
| `text` | ≤ 14 znaków ze zdania (`"+300%"`, `"FREE"`) |
| `kicker` | Opcjonalna etykieta nad słowem |
| `count` | Liczba kształtów, 300–900 (domyślnie 600) |
| `shapes` | `mixed` (domyślnie), `squares`, `dots`, `dashes` |
| `bg` | `panel` (domyślnie, pełny kadr) albo `none` (nad filmem) |

Słowo ląduje 1,0 s po `from`. Zacznij efekt około 1 s przed wypowiedzeniem słowa albo zakotwicz `"hit": "S3:word"` (tylko custom, co najmniej 0,6 s po `from`).

### Limity WOW

| Film | Limit |
|---|---|
| Short (gotowy film ≤ 90 s) | ≤ 2 efekty WOW, co najmniej 12 s odstępu między ich początkami; `burst-out` i `kinetic-word` najwyżej raz każdy |
| Długi film | ≤ 1 na minutę, ≤ 8 łącznie; plansze rozdziałów (`chapter_fx`) się nie liczą |

Elementy panelu i sceny liczą się do limitów. Nigdy nie ma jednego efektu WOW zaraz po drugim bez zwykłego nagrania pomiędzy i nigdy żadnego na twarzy. Build wypisuje `WARN wow …`, gdy limit jest przekroczony, a Claude naprawia to przed punktem kontrolnym.

## Własne efekty pisane przez Claude'a

Gdy prosisz o coś, czego nic powyżej nie pokrywa („daj kosmiczne tło za mną”, „Rasengan w mojej dłoni”), Claude pisze nowy efekt w `out/custom/<name>.html`. Zaczyna od najbliższego szablonu, sprawdza go lintem builda i czyta jego zrzuty co 0,25 s, zanim pokaże ci punkt kontrolny.

Plik efektu ma trzy sekcje, tak jak komponent motywu:

```html
<style>ROOT { position: absolute; inset: 0; }</style>
<markup><div class="fx" style="position:absolute;inset:0"></div></markup>
<script>
U.three({ el: root.querySelector(".fx"), bloom: { strength: 1.2, radius: 0.6, threshold: 0.1 } }).then(S => {
  const orb = U.glowOrb(S, { radius: P.radius || 1, colors: P.colors, swirl: 1 });
  U.clock(t => {
    const p = U.trackAt(P.track, t);
    const vis = p ? Math.min(1, Math.max(0, (t - P.at) / 0.25)) * Math.min(1, Math.max(0, (P.end - t) / 0.25)) : 0;
    if (p) orb.group.position.copy(S.toWorld(p[0], p[1], 0));
    orb.group.scale.setScalar(Math.max(0.001, vis));
    orb.update(t); S.render();
  });
});
</script>
```

### API efektów

| Nazwa | Co to jest |
|---|---|
| `P` | Parametry: `P.w`, `P.h`, `P.dur`, `P.at`, `P.end`, `P.track`, `P.assets` plus twoje własne `params` na najwyższym poziomie |
| `root` | Główny element efektu (`ROOT` w stylach) |
| `U.clock(fn)` | **Jedyny sterownik wywoływany co klatkę**: `fn(t)` z czasem lokalnym |
| `U.seed(n)` | **Jedyne źródło losowości** (z ziarnem) |
| `U.trackAt(P.track, t)`, `U.follow(el, P.track)` | Pozycja twarzy / dłoni w chwili `t`; przyklejenie do niej elementu |
| `U.three({el, bloom, camera})` | Scena three.js z opcjonalnym kompozytorem bloom, `toWorld(xPx, yPx, z)` i `render()` |
| `U.glowOrb`, `U.particles` | Świecąca kula, system cząsteczek |
| `U.draw`, `U.rough`, `U.tex` | Rysowanie linii SVG, odręczne kształty z Rough.js, wzory KaTeX |
| `U.anime(tl)`, `U.lottie(anim)` | Przekazuje oś czasu anime.js / animację Lottie (`autoplay: false`) zegarowi, który ją przewija |
| `U.fonts([...])`, `U.ready(promise)` | Czeka na font motywu; każe pierwszej klatce poczekać na asynchroniczną inicjalizację |
| `U.scramble` | Mieszanie tekstu z ziarnem (zamiast ScrambleTextPlugin z GSAP) |

Pliki potrzebne efektowi (JSON Lottie, tekstury, modele GLB) trafiają do `out/custom/<name>/`, a `P.assets` to przedrostek ich adresów URL.

### Zasady determinizmu

HyperFrames renderuje, **przewijając** (seek) do każdej klatki niezależnie, często w równoległych procesach. Dlatego efekt musi za każdym razem i w dowolnej kolejności rysować te same piksele dla tego samego `t`. Build **odrzuca** plik, który zawiera którykolwiek z tych elementów, nawet w komentarzu albo w stringu:

| Zakazane | Użyj zamiast tego |
|---|---|
| `Date.now`, `new Date`, `performance.now`, `THREE.Clock` | `t` z `U.clock` |
| `Math.random`, `crypto.getRandomValues`, `anime.utils.random`, `gsap.utils.random`, `utils.random`, `utils.randomPick`, `utils.shuffle`, wartości `"random(…)"`, staggery `from: "random"` | `U.seed(n)` |
| `requestAnimationFrame`, `setTimeout`, `setInterval`, `setAnimationLoop`, `gsap.ticker`, `onUpdate`, `.play(` | `U.clock` |
| `onComplete`, `onRepeat`, `onRender`, `onBegin`, `onLoop`, `onStart`, `onReverseComplete`, `onBeforeUpdate`, `onPause`, `onInterrupt`, `onSwapped`, `.restart(` | Wyliczaj stan z `t` (renderer, który przewija, pomija te callbacki) |
| `d3.transition`, `AfterimagePass`, `GlitchEffect`, `ScrambleTextPlugin` | Czas albo losowość wewnątrz biblioteki; do mieszania tekstu użyj `U.scramble` |

Inne zasady:

- Obiekty anime.js i Lottie twórz z `autoplay: false` i przekazuj je do `U.anime` / `U.lottie`.
- Ręcznie umieszczone efekty `custom` nie dostają automatycznego zanikania. Nie rysuj niczego przed `P.at` i zniknij do `P.end` (uzależnij wszystko od współczynnika widoczności, jak w przykładzie wyżej).
- Ładują się tylko dołączone dodatki three.js (`RoomEnvironment`, `TextGeometry`, `FontLoader`, `GLTFLoader`, `EffectComposer`, `RenderPass`, `UnrealBloomPass`, `OutputPass`, `ShaderPass`, `SavePass`, `MaskPass`, `Pass`, `CopyShader`, `LuminosityHighPassShader`, `OutputShader`, `BufferGeometryUtils`). Build odrzuca każdy inny dodatek.

## Umieszczanie gestem

Gdy mówisz „tutaj” / „tam” bez nazwania miejsca albo po prostu pokazujesz je rękami, Claude zapisuje `"place": "gesture"` (dla `custom` i `chip`) albo `"speaker": "gesture"` (dla `side`). Nazwane miejsce („w prawym dolnym rogu”, „po lewej”) zawsze wygrywa.

O miejscu decyduje dłoń, na podstawie śladów kształtu dłoni z `cutmate track`:

| Co robi dłoń | Gdzie trafia efekt |
|---|---|
| Otwarta / prezentująca dłoń | Tuż nad tą dłonią, podążając za ręką przez cały czas trwania (`P.hands` zawiera obie dłonie) |
| Wyraźne wskazanie palcem wskazującym | Wskazane miejsce, tuż za czubkiem palca |
| Ani jedno, ani drugie | Wyżej uniesiona widoczna dłoń |

Efekt bierze pozycję z próbki dłoni najbliższej swojemu początkowi, więc Claude kotwiczy go na **geście**, a nie na słowie. Każdy widoczny gest dostaje efekt na tyle duży, żeby był czytelny na telefonie: `burst` na obramowanym miejscu albo uderzeniu, `showcase-3d` na prezentującej dłoni, `energy-ball` na złożonej w miseczkę dłoni, `hand-sparks` przy rozłożonych rękach, a `hand-control` przy najwyraźniejszej otwartej dłoni.

Efekty mogą też przez cały czas trwania **podążać** za śledzoną częścią ciała dzięki `"follow": "face" | "hand_left" | "hand_right" | "hand"`. To wymaga świeżego `work/tracks.json`: uruchamiaj `cutmate track <out>` po każdym ponownym cięciu, bo build ignoruje ślady starsze niż `aroll.mp4`.

## Zapisywanie efektu

Gdy zaakceptujesz film, w którym użyto nowego własnego efektu:

```bash
cutmate save-effect <folder>/out <name> --description "co robi"
cutmate save-effect <folder>/out <name> --theme my-theme --force     # wybór motywu, nadpisanie
```

Polecenie lintuje efekt, kopiuje `out/custom/<name>.html` (i jego folder z zasobami) do `~/.cutmate/themes/<theme>/components/custom/` i zapisuje go w `index.json` tego folderu, razem z parametrami i trybem `follow`, z którymi był użyty. Każdy późniejszy montaż z tym motywem może go wtedy używać. Zobacz [customizing.md](customizing.md#3-zapisane-efekty).
