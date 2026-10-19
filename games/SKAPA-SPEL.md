# Skapa spel till dash-panelen

Det här dokumentet är en komplett beskrivning av hur man skriver ett spel som fungerar på dash-panelen (en pekskärm på
1024x600 som annars visar Home Assistant). Det är skrivet så att en AI (eller en människa) kan skriva ett nytt spel **utan
att läsa något annat**: allt som behövs står här. Svara och skriv text i spelen på svenska.

Ett spel är **en enda Python-fil**, `games/<id>.py`, som innehåller allt: reglerna, ritningen, ikonen som visas i
spelväljaren, raden om hur det står till ("Rekord 1 234") och all data spelet behöver. Inget annat i projektet ändras när
man lägger till ett spel.

## 1. Kortversionen

1. Kopiera mallen i avsnitt 3, byt `id`, `name`, `desc` och bygg spelet. Filen heter `<id>.py` (till exempel `lampor.py`).
2. Skriv bara det som står i avsnitt 4-9. Importera **bara** `from dashpanel import gamesdk as sdk` (och de få standardmoduler
   som avsnitt 4.3 listar).
3. Provkör: `python3 -m dashpanel.gamecheck games/<id>.py --png ut` (avsnitt 13). Titta på `ut-1.png` och `ut-2.png`.
   Rätta tills det står `OK` och inga varningar du inte förstår.
4. Lägg filen i mappen `games/` i GitHub-repot (`blobba79/dash-panel`, grenen `main`) och skjut den.
5. På panelen: spelikonen → **Uppdatera spel**. Spelet dyker upp i väljaren.

Gör så här för att få det rätt på första försöket:
- Håll dig till exemplen (avsnitt 15). Mallen och exemplen är provade och klarar `gamecheck`.
- Rita bara det som ändrats, aldrig hela skärmen i en loop (avsnitt 7 och 10). Panelens dator är ungefär tio gånger
  långsammare än en vanlig dator.
- Alla mått är heltal. Alla tryckytor minst 64 px höga och breda (avsnitt 11).
- Hitta inte på egna funktioner i `sdk`: det som finns står i avsnitt 17. Finns det inte där, rita det själv med
  `sdk.rbox`, `sdk.circle`, `sdk.text` och Pillow.

## 2. Plattformen

| | |
|---|---|
| Skärm | 1024 x 600 px, liggande, mörkt tema, pekskärm med **ett finger i taget** (ingen multitouch, ingen hovring, ingen högerklick) |
| Inmatning | bara tryck och drag med fingret. Inget tangentbord, ingen mus, inget ljud, ingen vibration, ingen kamera, ingen lutningssensor |
| Dator | Allwinner A33 (fyrkärnig Cortex-A7, en surfplatteprocessor). Räkna med **ca tio gånger långsammare** än en vanlig dator |
| Språk | Python 3.11. Pillow (bara de moduler som avsnitt 4.3 listar). Inget numpy |
| Process | Spelet körs **i panelens egen process**, tillsammans med Home Assistant-kopplingen, klockan och alla andra sidor. Ett spel som tänker länge eller väntar fryser hela panelen. Ingen tråd, ingen `async`, inget `sleep` |
| Minne | hela panelen får ca 110 MB. Spara inga stora tabeller eller bilder (en bild på hela skärmen är 1,8 MB) |
| Filer och nät | inget. Spelet kan inte öppna filer eller nå nätet. Det enda spelet sparar är det som `state()` ger (avsnitt 8) |
| Skärmen släcks | efter en inställd tid utan tryck (spelet står kvar, första trycket tänder bara) och panelen lämnar spelet av sig själv efter 5 minuter utan tryck. Spelet ska tåla att `on_close()` kommer när som helst |

Rubrikraden (y 10-82) med **Tillbaka**-knappen, spelets namn och klockan ritas av panelen. **Spelet har ytan y 84-600**
(`sdk.AREA = (0, 84, 1024, 600)`) för sig själv. Rita aldrig ovanför y 84.

## 3. Mallen: det minsta spelet

Det här är ett helt, fungerande spel. Kopiera det och bygg vidare.

<!-- spelfil: mall -->
```python
"""Mall: det minsta spelet som går att lägga i games/. Kopiera, byt id och namn och bygg vidare."""
from dashpanel import gamesdk as sdk

META = {
    'api': 1,                        # SDK-versionen (nu 1)
    'id': 'mall',                    # samma som filnamnet utan .py
    'name': 'Mall',                  # visas i väljaren (högst 24 tecken)
    'desc': 'Räknar tryck. Mall för nya spel.',     # raden under namnet (högst 120 tecken)
    'version': 1,
}

PLUS = (312, 300, 712, 400)          # tryckytor: (x0, y0, x1, y1), hela tal, y minst 84
RESET = (312, 430, 712, 510)


def draw_icon(im):                   # ikonen: en bild på 128 x 128 som redan är ifylld med bakgrund
    sdk.rbox(im, 14, 14, 114, 114, 22, sdk.BLUE_D)
    sdk.centered(im, 64, 84, '+1', 500, 52, sdk.BLUE_L)


def status(data):                    # raden i väljaren; data är sparade data (dict) eller None
    if data and data.get('count'):
        return 'Räknat %d' % data['count'], True
    return None


class Game(sdk.GameBase):            # skriv ingen __init__, använd setup()
    def setup(self):                 # nytt spel
        self.count = 0

    def state(self):                 # det som sparas (JSON-vänligt), eller None
        return {'count': self.count}

    def restore(self, data):         # läs in sparade data
        self.count = int(data['count'])

    def targets(self):               # knapparna: (namn, ruta)
        return [('plus', PLUS), ('reset', RESET)]

    def on_tap(self, name):          # ett tryck på en knapp
        self.count = self.count + 1 if name == 'plus' else 0
        self.save_soon()             # spara inom några sekunder
        self.invalidate()            # rita om (hela ytan; ge en ruta för att rita om mindre)

    def paint(self, img, rect):      # rita det som ligger i rect (rutan är redan rensad)
        sdk.centered(img, 512, 240, str(self.count), 300, 120, sdk.TEXT)
        sdk.button(img, PLUS, '+1', 'primary', self.pressed == 'plus', size=36)
        sdk.button(img, RESET, 'Nollställ', 'normal', self.pressed == 'reset')
```

Så här hänger det ihop:
- `META` beskriver spelet (avsnitt 4.2). `draw_icon` ritar ikonen i väljaren (4.4) och `status` raden under namnet (4.5). Båda är
  valfria men bör finnas.
- `class Game(sdk.GameBase)` är spelet. Basklassen sköter rubrikraden, tryck, tidtagare, ritning av ändrade rutor och sparfilen.
- Spelet **skriver aldrig till skärmen själv**. Det säger "den här rutan har ändrats" (`invalidate`) och panelen anropar sedan
  `paint(img, rect)` för just den rutan.

## 4. Filens delar

### 4.1 Filnamn och id
- Filnamnet är `<id>.py`. Id:t är 2-32 tecken av `a-z`, `0-9`, `_` och `-`, och börjar med en bokstav eller siffra
  (`lampor`, `fanga-bollen`, `2048`). `META['id']` måste vara **exakt samma** som filnamnet utan `.py`.
- En fil får vara högst 400 000 tecken och måste vara UTF-8. Högst 64 spel kan finnas samtidigt.
- Id:t är också namnet på sparfilen (`game-data/<id>.json`). Byt aldrig id på ett spel som folk spelat, då försvinner deras
  sparade resultat.

### 4.2 META
En vanlig `dict` med **bara bokstavliga värden** (text, tal, `None`; inga uttryck, inga variabler), eftersom panelen läser den
ur källtexten utan att köra något.

| Nyckel | Krav | Betydelse |
|---|---|---|
| `api` | heltal, `1` | SDK-versionen spelet är skrivet för. En panel som är äldre än spelet visar "kräver nyare panel" |
| `id` | se 4.1 | samma som filnamnet |
| `name` | text, 1-24 tecken | namnet i väljaren och i rubrikraden |
| `desc` | text, 1-120 tecken | en eller två meningar under namnet i väljaren (ryms ca 3 rader x 40 tecken; skriv gärna under 100 tecken) |
| `version` | heltal, valfri (standard 1) | räkna upp när du ändrar spelet. Visas inte, men hjälper den som felsöker |
| `legacy_save` | text, valfri | sökväg till en äldre sparfil som spelet ska ta över (slutet av avsnitt 8). Nästan alltid utelämnad |

### 4.3 Vad filen får importera och använda
Panelen kontrollerar filen innan den körs. Kontrollen är ett **skyddsräcke mot misstag, inte en säkerhetsgräns**: spelet körs i
panelens process, så lägg bara spel i repot som du litar på.

Tillåtna importer (allt annat avvisas):
- `from dashpanel import gamesdk as sdk` (det enda du får importera ur `dashpanel`)
- `math, cmath, random, time, datetime, json, itertools, collections, functools, heapq, bisect, string, enum, dataclasses, typing, re, copy, textwrap, operator, fractions, decimal, statistics, base64, zlib, struct, array, abc, numbers, __future__`
- Pillow: `from PIL import Image, ImageDraw, ImageChops, ImageFilter, ImageOps` (inte `ImageFont`: text ritas med `sdk.text`)

Förbjudet (filen avvisas med ett felmeddelande):
- alla andra importer, relativa importer (`from . import x`)
- namnen `open exec eval compile input breakpoint globals locals vars help exit quit __import__ __builtins__ memoryview`
  (observera att `exit` som *namn* är förbjudet; det är `self.exit()` som gäller)
- attribut som börjar och slutar med `__` utom vanliga som `__init__`, `__len__`, `__iter__`, `__eq__`, `__repr__`, `__getitem__`
  (alltså inte `__class__`, `__dict__`, `__subclasses__`, `__globals__`)
- `async`, `await` och `global` (spara tillstånd i `self` eller i modulens konstanter; ändra aldrig modulvariabler från metoder)
- `print` fungerar men syns bara i panelens logg. Använd `self.log(...)`.

### 4.4 Ikonen: `draw_icon(im)`
Valfri men bör finnas. Anropas en gång (per bakgrundsfärg) för att rita spelets ikon i väljaren.
- `im` är en `PIL.Image` i RGB, **128 x 128 px**, redan ifylld med bakgrunden `sdk.ICON_BG` (24, 24, 24). Rita direkt i den.
- Rita med `sdk.rbox(im, x0, y0, x1, y1, radie, färg)`, `sdk.circle(im, x, y, diameter, färg)`, `sdk.text(...)`,
  `sdk.centered(...)` eller Pillow (`ImageDraw.Draw(im)`). Håll dig 10 px från kanten. Använd få, kraftiga former och 2-4 färger
  ur temat (avsnitt 7.3): ikonen visas ganska liten.
- Saknas funktionen, eller kastar den ett fel, får spelet en standardikon (spelets första bokstav).
- Får inte vara tung (den körs på enheten, men bara en gång).

### 4.5 Raden i väljaren: `status(data)`
Valfri. Anropas varje gång väljaren öppnas, med spelets **sparade data** (den `dict` som `state()` gav) eller `None` om
spelet aldrig sparat. Ger `(text, aktiv)` eller `None`:
- `text`: en kort rad, helst under 30 tecken (längre kortas med …). Till exempel `'Rekord 1 234'`, `'Pågående spel · 41 rutor kvar'`.
- `aktiv`: `True` om något pågår (raden blir blå och fet), `False` för vanlig grå (rekord, antal klarade).
- `None`: ingen rad.
- Funktionen körs **utan att spelet startas**: den får bara läsa `data` (kan vara `None` eller saknad nyckel: använd
  `data.get(...)`). Kastar den ett fel visas ingen rad.

### 4.6 Klassen `Game`
Måste heta `Game` och ärva `sdk.GameBase`. **Skriv ingen `__init__`**: basklassen anropar `setup()` (nytt spel) och läser sedan
sparfilen. Överskugga bara det du behöver (avsnitt 5-9).

## 5. Livscykeln

1. Spelet **skapas** när spelaren trycker på kortet första gången (och på nytt om filen ändrats): `setup()` körs, sedan, om det
   finns en sparfil, `restore(data)`.
2. `on_open()` anropas varje gång spelet visas. Därefter ritas hela ytan (`paint` anropas för hela `sdk.AREA`).
3. Spelaren spelar: `on_tap`, `on_down/on_move/on_up`, tidtagare, `paint`.
4. Trycker spelaren **Tillbaka** anropas `on_close()`, alla tidtagare du startat med `later` avbryts och spelet sparas.
   Spelinstansen **ligger kvar** i minnet: kommer spelaren tillbaka anropas `on_open()` igen, men inte `setup()` eller `restore()`.
   Allt i `self` är alltså kvar. Spelet ska därför kunna fortsätta (eller pausa, eller avsluta en omgång snyggt) i `on_close()`.
5. När panelen stoppas sparas spelet en sista gång.
6. Går något fel i spelet (ett undantag i någon av metoderna, i en tidtagare eller i `paint`) loggas det, panelen går tillbaka
   till flikarna, spelets sparfil läggs undan som `<id>.json.broken` och spelet börjar om nästa gång. Panelen faller aldrig för
   ett spel, men spelaren tappar sitt sparade. **Fånga därför fel du kan förutse** (konstig sparfil, tom lista) i stället för att låta dem
   kasta.

## 6. Tryck

Tryck kommer som koordinater i skärmens pixlar (x 0-1023, y 0-599). Det finns två sätt, och du kan blanda dem i samma spel.

**Knappar (det vanliga):** `targets()` ger en lista med `(namn, ruta)` eller `(namn, ruta, slop)`. Rutan är `(x0, y0, x1, y1)` med
heltal, `x1` och `y1` exklusiva, och ligger helt inom `sdk.AREA`. Första träffen i listan vinner (lägg små knappar före stora).
- Trycker fingret ner på en knapp blir `self.pressed == namn` och knappens ruta ritas om (rita den "intryckt", se `sdk.button`).
- Glider fingret mer än `slop` px (standard 16) utanför knappen avbryts trycket (knappen ritas som vanligt), och glider det
  tillbaka räknas knappen som intryckt igen. Lyfts fingret på knappen anropas `on_tap(namn)`. Ett tryck som börjar på en knapp ger aldrig `on_down/on_move/on_up`.
- `targets()` anropas vid **varje nedtryck**: hämta inte något tungt där. Listan får gärna ändras mellan anropen (en knapp som
  inte ska gå att trycka på utelämnas helt).

**Fri yta (drag, rutnät, ritning):** ett tryck som **inte** började på en knapp ger `on_down(x, y)`, sedan `on_move(x, y)` medan
fingret rör sig (kan komma ofta: gör lite per anrop) och till sist `on_up(x, y)` när det lyfts. Räkna inte med att `on_up` alltid kommer (spelet kan
stängas mitt i en tryckning, då anropas `on_close()`): nollställ ett pågående drag i `on_close()`.

**Tillbaka:** knappen uppe till vänster hanteras helt av basklassen och anropar panelens `exit()`. Du behöver inte (och
får inte) göra en egen. Anropa **inte** `self.exit()` från en vanlig knapp (spelaren förväntar sig att Tillbaka är det
enda sättet ut); `gamecheck` ger fel om en tryckning på en knapp lämnar spelet.

Praktiska regler: gör tryckytor stora (avsnitt 11), ge omedelbar återkoppling (färgen på en lampa, en knapp som ändras) och
dra inte slutsatser av ett enda `on_move`.

## 7. Ritning

### 7.1 Hur det fungerar
- Du ritar aldrig direkt. När något ändrats anropar du `self.invalidate(rect)` (en ruta `(x0, y0, x1, y1)`; utan argument hela
  `sdk.AREA`). Panelen rensar då rutan till bakgrundsfärgen och anropar `paint(img, rect)`; du ritar det som ligger **i** rutan.
- `paint(img, rect)` kan anropas flera gånger i rad med olika rutor (en per ändrad del) och med hela ytan när spelet öppnas eller
  skärmen ritas om. **Rita varje del bara om den träffar `rect`:** `if sdk.meets(rect, DELENS_RUTA): ...`. Annars ritar du allt
  varje gång, vilket på panelen är för långsamt för drag och animeringar.
- **Ritas något som träffar `rect`, rita hela det föremålet** (och fyll gärna först hela föremålets ruta med
  `sdk.fill(img, ruta)`): delar utanför `rect` skickas inte till skärmen, men om en halvtransparent kant ritas två gånger ovanpå
  sig själv blir den tjockare. För en rektangulär yta som fylls helt (en spelplan) kan du i stället fylla bara
  `sdk.clip(rect, PLAN)` och rita de föremål som träffar `rect` ovanpå (se exemplet "Fånga bollen").
- `invalidate(rect, urgent=True)`: `urgent=True` (standard) ritar direkt, bra för svar på tryck. Använd `urgent=False` för
  sådant som kommer av en tidtagare (sekundräknare, animering): då slås flera ändringar ihop.
- Ritningen går till `img`, en `PIL.Image` i RGB (hela skärmen, 1024 x 600). Det finns en bild på hela skärmen: rita aldrig en ny
  `Image` stor som skärmen för varje bildruta.
- Rita med **heltalskoordinater** i alla `sdk`-funktioner (`//` och `int()`). Flyttal ger `TypeError` utom för `x` i `sdk.text`.
  Färger är tuplar `(r, g, b)` med heltal 0-255.
- Rubrikraden och klockan ritas av basklassen. Du kan ändra rubriken: `self.title = 'Nivå 3'` följt av `self.refresh()`.

### 7.2 Ritverktyg
Alla ligger i `sdk` (`img` är bilden som `paint` får, eller `im` i `draw_icon`). Rutor är `(x0, y0, x1, y1)`, kantpunkterna
`x1`, `y1` är exklusiva. Alla argument är heltal om inget annat sägs.

| Anrop | Gör |
|---|---|
| `sdk.fill(img, rect, color=sdk.BG)` | fyller rutan med en färg (standard bakgrunden) |
| `sdk.rbox(img, x0, y0, x1, y1, r, color)` | fylld ruta med rundade hörn, radie `r` (`r=0` ger skarpa hörn), kantutjämnad |
| `sdk.bbox(img, x0, y0, x1, y1, r, fill, border, bw)` | ruta med rundade hörn och kant: `fill` fyllning, `border` kantfärg, `bw` kantbredd i px |
| `sdk.circle(img, x, y, d, color)` | fylld cirkel med diametern `d`; `(x, y)` är **övre vänstra hörnet** av omskrivande kvadrat |
| `sdk.text(img, x, baseline, s, weight, size, color, anchor='ls')` | text. `x` kan vara flyttal; `baseline` (textens baslinje, y) **heltal**. `weight` 300, 400 eller 500, `size` i px. `anchor='ls'` har `x` vid textens vänsterkant, `anchor='rs'` vid högerkanten |
| `sdk.centered(img, cx, baseline, s, weight, size, color)` | text centrerad kring `cx` |
| `sdk.text_width(s, weight, size)` | textens bredd i px (flyttal) |
| `sdk.fit(s, weight, size, maxw)` | kortar `s` med … så att den ryms i `maxw` px |
| `sdk.wrap(s, weight, size, maxw)` | delar `s` i en lista av rader som var för sig ryms i `maxw` px |
| `sdk.button(img, rect, label, kind='normal', pressed=False, enabled=True, size=24, icon_name=None, icon_color=None)` | panelens knapp: `kind` är `'normal'`, `'primary'` (blå), `'ok'` (grön), `'warn'` (orange) eller `'danger'` (röd). Skicka `self.pressed == namn` som `pressed` |
| `sdk.blend(a, b, t)` | färg mellan `a` och `b` (`t` 0.0-1.0), till exempel `sdk.blend(färg, (255, 255, 255), 0.2)` för en ljusare "intryckt" färg |
| `sdk.icon(img, name, size, x, y, color)` | en av panelens ikoner (7.5) i en färg |
| `sdk.inside(rect, x, y, slop=0)` | ligger punkten i rutan? |
| `sdk.meets(a, b)` | överlappar rutorna? |
| `sdk.clip(rect, area)` | `rect` beskuren till `area` |
| `sdk.union(a, b)` | den minsta ruta som rymmer båda (`None` räknas som tom) |
| `sdk.thousands(n)` | `1234567` → `'1 234 567'` |

Du kan också rita med Pillow direkt i `img` (`ImageDraw.Draw(img).line(...)`, `polygon`, `ellipse`, `img.paste(...)`). Pillows
egna former är **inte kantutjämnade**: använd `sdk.circle` och `sdk.rbox` för runda former, och ritar du en linje eller polygon
som ska se bra ut, rita den på en bild som är 3-4 gånger större och förminska den (`Image.resize(..., Image.LANCZOS)`) en gång
(och spara resultatet; rita inte om det varje bildruta).

### 7.3 Färger (panelens tema)
Använd temats färger så att spelet ser ut som resten. Alla finns som `sdk.<NAMN>` (tuplar):

| Namn | Värde | Används till |
|---|---|---|
| `BG` | `#111111` | bakgrunden |
| `CARD` | `#1c1c1c` | kort och ytor på bakgrunden |
| `CARD_BORDER` | `#2c2c2c` | kant på kort |
| `BTN_BG` | `#242424` | vanliga knappar, tomma rutor |
| `SKELETON` | `#262626` | tomma/avstängda ytor |
| `TEXT` | `#e1e1e1` | vanlig text |
| `MUTED` | `#9b9b9b` | sekundär text |
| `FOOT` | `#8f8f8f` | små etiketter |
| `STALE_TEXT` | `#6b6b6b` | avstängd text |
| `BLUE`, `BLUE_L`, `BLUE_D`, `BLUE_BG` | `#03a9f4`, `#4fc3f7`, `#0b4a6e`, `#0f2230` | val, aktivt, primära knappar |
| `GREEN`, `GREEN_D`, `GREEN_BORDER` | `#66bb6a`, `#163a1c`, `#2f7a36` | lyckat, klart |
| `WARN`, `WARN_D`, `WARN_BORDER` | `#ffa726`, `#3a2a0e`, `#8a5d12` | varning, "tryck igen" |
| `RED`, `RED_D`, `RED_BORDER` | `#ef5350`, `#3a1a1a`, `#7a2c2c` | fel, krock, förlust |
| `YELLOW`, `ORANGE` | `(255, 193, 7)`, `(224, 131, 42)` | tända lampor |
| `ICON_BG` | `#242424` | ikonens bakgrund |

Egna färger går bra (spelbrickor behöver ofta fler), men håll bakgrunden mörk (skärmen sitter i ett rum), undvik stora vita
ytor och se till att text har bra kontrast mot sin yta (ljus text på mörk bakgrund, minst `MUTED`).

### 7.4 Text
- Typsnittet är Roboto i tre tjocklekar: **300** (tunn, stora siffror), **400** (vanlig) och **500** (fet, knappar och rubriker). Andra
  värden ger `KeyError`.
- Storlekar i px: brödtext 18-24, rubriker 28-34, stora tal 60-120 (tjocklek 300). Allt under 16 px är svårt att läsa på skärmen.
- Svenska tecken (å ä ö é) och `· … × ÷ − – — ½ ° ± € %` finns. **Det finns inga** symboler som pilar (← → ↑ ↓), hjärtan eller
  spelkortsfärger (♥ ♠), bockar (✓), geometriska former (▲ ● ■), stjärnor eller `≤ ≥ ≠`: de blir tomma rutor. Rita sådant som
  former (`sdk.circle`, `sdk.rbox`, `ImageDraw.polygon`).
- `baseline` är y för textens nedre kant (där bokstäver utan svans slutar). Text av storlek `S` når ungefär `0,75*S` uppåt från
  baslinjen. Vill du placera en rad i en ruta: `baseline = ruta_y0 + (höjd + S * 0,7) // 2`, eller se `sdk.button` som gör det.
- Mät långa texter med `sdk.fit` (kortar) eller `sdk.wrap` (radbryter) innan du ritar dem.

### 7.5 Ikoner
`sdk.icon(img, 'Namn', storlek, x, y, färg)` ritar en av panelens ikoner (en mask i en enda färg). Bara dessa kombinationer av namn och
storlek finns; en annan ger `FileNotFoundError`:
`ChevronLeft 32`, `ChevronRight 28`, `Cog 32`, `GamepadVariant 32`, `CloudDownload 40/64`, `ExitToApp 40/64`, `Power 40/64`,
`Restart 40/64`, `Plus 44`, `Minus 44`, `Lightbulb 26/36/52`, `LightbulbOff 26/36/52`, `LightbulbMultiple 26/36`, `Thermometer 22/26/28`,
`Brightness6 28`, `MonitorOff 28`, `Wifi 18`, `WifiOff 18`. De flesta spel klarar sig utan ikoner.

### 7.6 Knappar
`sdk.button` ritar en knapp i panelens stil (rundad ruta, centrerad fet text). Gör så här:
```python
def targets(self):
    return [('ny', NY_RECT)]

def paint(self, img, rect):
    if sdk.meets(rect, NY_RECT):
        sdk.button(img, NY_RECT, 'Nytt spel', 'normal', self.pressed == 'ny')
```
För "ångra inte"-knappar (Nytt spel mitt i en pågående omgång): första trycket ändrar knappen till `'warn'` med texten "Tryck igen"
och startar `self.later('bekräfta', 3.0, self.ångra)`; ett andra tryck inom tiden gör det. Se Lampor-exemplet.

## 8. Spara

Spelet sparar **tillstånd som JSON**. Du skriver två metoder:

```python
def state(self):               # anropas när det ska sparas
    return {'best': self.best, 'board': self.board}      # en dict, eller None om det inte finns något att spara

def restore(self, data):       # anropas efter setup() om en sparfil finns
    self.best = int(data['best'])
    self.board = [list(r) for r in data['board']]
```

- **`state()`** ger en `dict` med JSON-vänliga värden: `dict` med **textnycklar**, `list`, `str`, `int`, `float`, `bool`, `None`.
  Tupler blir listor och heltalsnycklar i en `dict` blir **text** när filen läses tillbaka (`{1: 'a'}` blir `{'1': 'a'}`): använd
  textnycklar från början. Inga `set`, objekt, `NaN` eller `inf`. Hela sparfilen får vara högst 200 000 tecken.
- **`restore(data)`** läser tillbaka. `data` är den `dict` du sparade (kan vara från en äldre version av spelet: kontrollera
  och använd `.get()`). Är den konstig: kasta ett fel, eller ge `False`. Panelen lägger då undan filen som `<id>.json.broken` och
  startar ett nytt spel (`setup()`). Spelaren ska aldrig se en krasch för en trasig sparfil.
- **När sparas det?** Anropa `self.save_soon()` när något ändrats (sparar inom 8 sekunder, flera anrop blir en skrivning) och
  `self.save_now(force=True)` vid viktiga stunder (omgången är slut, nytt rekord). Spelet sparas dessutom alltid när spelaren lämnar det
  och när panelen stoppas. Spara aldrig i varje `on_move`.
- Spelet läser aldrig själv några filer. Sparfilen ligger i `/var/lib/dash-panel/game-data/<id>.json` och hör till spelet. Ta bort den
  för att nollställa spelet.
- **Spela vidare** efter att panelen startat om är det vanliga. Spara alltså det som behövs för att fortsätta (brädet, poängen,
  vems tur), inte det som kan räknas om (ritade bilder, rutor på skärmen, `self.pressed`).

### Ta över en äldre sparfil (`legacy_save`)
Bara för spel som ersätter ett äldre spel med en annan sparfil. `META['legacy_save'] = '/var/lib/dash-panel/gammal.json'`: finns ingen ny
sparfil läses den gamla (ett JSON-objekt) en gång och skickas till `restore(data)`. Den gamla filen ändras eller tas inte bort. Nya
spel behöver inte detta.

## 9. Tid och animering

- **`self.later(namn, sekunder, funktion)`** anropar `funktion()` om en stund. Samma `namn` en gång till ersätter den väntande. Det
  upprepar sig **inte**: låt funktionen starta nästa (som `tick` i exemplet "Fånga bollen"). `self.cancel(namn)` avbryter. Alla tidtagare
  avbryts av panelen när spelaren lämnar spelet, och ett fel i `funktion` hanteras som ett fel i spelet.
- `self.now()` är en monoton klocka i sekunder: för att mäta tid mellan två händelser. För
  klockslag och datum: `time.time()` eller `datetime` (tiden på panelen är UTC).
- `self.rng` är en `random.Random`. **Använd den i stället för `random`-modulens funktioner** (då går spelet att prova
  deterministiskt).
- **Animering:** bildrutor var 100-250 ms är lagom på panelen (10 per sekund är redan mycket). Rita bara de rutor som rör sig
  (`invalidate(union(gammal_ruta, ny_ruta), urgent=False)`) och sluta starta tidtagare när inget rör sig (en tidtagare som tickar i
  onödan tar processortid från hela panelen). Tänk på att drag med fingret redan ger många `on_move` per sekund.
- **Lång beräkning:** blockera aldrig. Allt som tar mer än ca 20 ms *på en vanlig dator* (generera ett pussel, sök efter drag, flod-
  fyllning av stor yta) ska delas upp över flera `later(...)`-anrop, eller förberäknas och läggas in som data i filen.
- `time.sleep(...)` får aldrig användas.

## 10. Prestanda och minne

- Mät med `gamecheck` (avsnitt 13): raden "längsta ritning här" ska vara **under 50 ms** (på panelen blir det ca tio gånger
  så mycket). Över 1 s ger en varning.
- Rita bara det som ändrats (avsnitt 7.1). Rita aldrig en hel bräda för att en bricka flyttats.
- Förbered det som är dyrt en gång (bilder, text som inte ändras) och spara i `self` eller i en modulvariabel (en dict används som
  cache). Rita det sedan med `img.paste(...)`. En bild i skärmstorlek tar 1,8 MB: spara inga tiotals av dem.
- Undvik att skapa nya `Image`-objekt och långa listor i varje `paint`.
- `sdk.text` har en cache för färdigritad text (de senaste 400 olika texterna/storlekarna): en text som ritas första gången kostar ca 2 ms här
  (ca 20 ms på panelen), samma text igen under 0,1 ms. Ett rutnät med 81 siffror är i sin ordning; hundratals olika texter i varje ritning är det inte.
- Håll spelets datatabeller små (pussel, ordlistor): 400 000 tecken är gränsen för hela filen, men ju större fil, desto längre tar
  det att öppna spelväljaren första gången (filen tolkas varje gång den ändrats).

## 11. Utseende och användbarhet

- **Tryckytor minst 64 x 64 px**, helst 80 eller mer, med minst 8 px mellanrum. Fingret är grovt: små knappar
  missas. Lämna 16-24 px fri marginal mot skärmens kanter.
- Spelet ska fungera helt med **ett finger i taget**. Ingen dubbeltryckning och ingen långtryckning som enda sätt att göra något.
- Visa **allt som behövs** utan förklaringstext: poäng, vad som pågår, vad som går att trycka på. En kort text (en mening) för regler är
  bättre än en lång.
- Svenska i alla texter. Korta, tydliga knappar: "Nytt spel", "Starta", "Igen", "Kontrollera", "Ångra", "Klart!". Siffror med
  tusentalsavgränsare: `sdk.thousands(n)`.
- Farliga knappar (nytt spel mitt i en omgång) frågar först med "Tryck igen" (avsnitt 7.6).
- Efter en klarad omgång: visa resultatet och en knapp för att börja om. Spara rekord.
- Spelet ska vara **klart att spela direkt**: ingen inloggning, inga inställningar att göra först.
- Färgblindhet: lita inte bara på röd/grön. Lägg till en form, en siffra eller en text.
- Panelen släcker skärmen efter en stund och lämnar spelet efter fem minuter utan tryck; spelaren väntar sig att spelet står kvar. Spara
  tillståndet så att det går att fortsätta, och låt tidspress vara frivillig (som en omgång på 30 s som spelaren själv startar).

## 12. Vanliga fel

| Fel | Orsak och rätt |
|---|---|
| "importen av x är inte tillåten" | du importerade något som inte står i 4.3. Skriv det själv eller använd `random`, `math` och `itertools` |
| "META['id'] måste vara samma som filnamnet" | `META['id']` och filnamnet skiljer sig |
| `TypeError: 'float' object cannot be interpreted as an integer` | en koordinat är ett flyttal. Använd `//` i stället för `/`, eller `int(...)` |
| `KeyError: 600` i `sdk.text` | tjocklek måste vara 300, 400 eller 500 |
| texten syns inte alls | `baseline` ligger utanför bilden, eller färgen är samma som bakgrunden |
| tomma rutor i stället för tecken | tecknet finns inte i typsnittet (7.4) |
| delar av skärmen ritas inte om / lämnar spår | du ritade utanför `rect`, eller glömde `invalidate` för det som flyttats (rita även den **gamla** platsen: `invalidate(union(gammal, ny))`) |
| ritningen är seg | du ritar allt i varje `paint`. Använd `sdk.meets(rect, ...)` och mindre `invalidate`-rutor |
| spelet sparar inget | `state()` ger `None`, eller så anropas aldrig `save_soon()`/`save_now()` |
| sparfilen verkar trasig efter omstart | heltalsnycklar i en `dict` blev text, eller något blev en lista i stället för en tupel. Kontrollera i `restore` |
| knappen reagerar inte | rutan ligger inte inom `sdk.AREA` (y minst 84), eller en annan knapp ligger före den i listan och täcker den |
| `exit()` ... lämnade spelet | en vanlig knapp anropade `self.exit()`. Bara Tillbaka lämnar spelet |
| tidtagaren går vidare efter Tillbaka | `later` avbryts av panelen, men det du satt i `self` ligger kvar: återställ i `on_close()` |
| Spelet är nedtonat i väljaren med "Kan inte öppnas" | filen klarade inte kontrollen: texten säger varför (syntaxfel, META, förbjuden import, saknad klass `Game`) |

## 13. Prova spelet innan det läggs i repot

I en kopia av repot (`blobba79/dash-panel`, kräver bara Python 3 och Pillow):

```
python3 -m dashpanel.gamecheck games/<id>.py                 # kontrollerar och skriver en rapport
python3 -m dashpanel.gamecheck games/<id>.py --png ut        # sparar dessutom ut-1.png (start) och ut-2.png (efter tryck)
python3 -m dashpanel.gamecheck games/<id>.py --quick         # färre slumptryck
python3 -m dashpanel.gamecheck games/<id>.py --json          # rapporten som JSON
```

Avslutskoden är 0 om inget **fel** hittades (varningar räknas inte). Provet laddar filen på samma sätt som panelen, ritar,
trycker på varje knapp, trycker och drar slumpmässigt, låter tiden gå, trycker på Tillbaka, sparar och läser tillbaka sparfilen
(även en trasig sparfil och en med konstigt innehåll) och stänger spelet. Det kontrollerar bland annat att:
- filen klarar kontrollen i avsnitt 4 (importer, META, klassen `Game`);
- `paint` ritar något och inte ovanför y 84; `targets()` ger heltalsrutor inom ytan;
- ingen knapp lämnar spelet; Tillbaka gör det;
- `state()` går att spara som JSON och sparfilen går att läsa tillbaka; en trasig sparfil kraschar inte;
- inga tidtagare ligger kvar efter att spelet stoppats; ritningarna inte tar orimligt lång tid;
- ikonen inte är tom.

`gamecheck` är **inget bevis för att spelet är bra eller att reglerna stämmer**; det bevisar att det går att ladda, rita och trycka på
utan att något går sönder. Bilderna (`ut-1.png`, `ut-2.png`) är 1024 x 600 och visar vad som hamnar på skärmen: titta på dem och kontrollera
att inget överlappar, att text ryms och att allt går att trycka på. Skriv gärna egna prov för spelreglerna: gör reglerna till vanliga
metoder i `Game` (eller en egen klass i filen) som går att anropa utan skärm.

Har du ingen kopia av repot: följ reglerna i det här dokumentet noga och hänvisa i leveransen till att filen inte kunnat provas.

## 14. Checklista innan du lämnar ifrån dig filen

- [ ] Filen heter `<id>.py` och `META['id']` är samma. `api` är 1. `name` ≤ 24 och `desc` ≤ 120 tecken, på svenska.
- [ ] Bara tillåtna importer (4.3). Inga förbjudna namn. Ingen `__init__`, ingen `async`, ingen `global`.
- [ ] `draw_icon(im)` finns och ritar något tydligt i 128 x 128.
- [ ] `status(data)` finns om spelet har rekord eller pågående spel.
- [ ] Allt ritas i `paint(img, rect)` och bara det som träffar `rect`. Inget ritas ovanför y 84.
- [ ] Alla tryckytor ≥ 64 px, med mellanrum, inom `sdk.AREA`.
- [ ] Alla koordinater till `sdk` är heltal. Tjocklekarna är 300, 400 eller 500. Inga tecken som saknas i typsnittet.
- [ ] `state()` ger bara JSON (textnycklar), `restore()` tål gamla och konstiga data.
- [ ] Inga långa beräkningar eller `sleep`; animering högst ca 10 bildrutor per sekund.
- [ ] `on_close()` lämnar spelet i ett läge där det går att fortsätta.
- [ ] `python3 -m dashpanel.gamecheck games/<id>.py --png ut` ger `OK` och bilderna ser rätt ut.
- [ ] Spelet är provat på alla sätt det kan ta slut (vinst, förlust, "Nytt spel" mitt i, Tillbaka mitt i).

## 15. Exempel

Mallen (avsnitt 3) och de här två är hela, provade spel (provet `tools/simgames.py` kör dem, så de fungerar). Börja med det som liknar ditt spel mest.

### 15.1 Lampor: rutnät, knappar, "tryck igen", vinst, rekord, sparande
Fem gånger fem lampor; ett tryck växlar lampan och dess fyra grannar; släck alla. Visar `targets()` med många knappar, `on_tap`,
`save_soon`/`save_now`, `restore` som kontrollerar sina data, `status`, `draw_icon` och en knapp som ber om bekräftelse med `later`.

<!-- spelfil: lampor -->
```python
"""Lampor: släck alla lampor. Ett tryck på en lampa växlar den och dess fyra grannar."""
from dashpanel import gamesdk as sdk

META = {
    'api': 1,
    'id': 'lampor',
    'name': 'Lampor',
    'desc': 'Släck alla lampor. Ett tryck växlar lampan och dess fyra grannar.',
    'version': 1,
}

N = 5                                    # rutnätet är N x N lampor
CELL = 88                                # en lampas ruta (pixlar)
BX, BY = 40, 112                         # rutnätets övre vänstra hörn
BOARD = (BX - 16, BY - 16, BX + N * CELL + 16, BY + N * CELL + 16)
SIDE = (548, 100, 1008, 580)             # högerkolumnen
NEW_RECT = (580, 470, 984, 550)
LAMP = sdk.YELLOW
OFF = (0x2b, 0x2b, 0x2b)


def draw_icon(im):
    """Ikonen (128x128): tre gånger tre lampor, några tända."""
    for r in range(3):
        for c in range(3):
            on = (r + c) % 2 == 0
            sdk.rbox(im, 10 + c * 40, 10 + r * 40, 10 + c * 40 + 34, 10 + r * 40 + 34, 12, LAMP if on else OFF)


def status(data):
    """Raden under namnet i spelväljaren: (text, aktiv) eller None."""
    if not data:
        return None
    if data.get('moves', 0) > 0 and not data.get('won'):
        return 'Pågående spel · %d drag' % data['moves'], True
    best = data.get('best', 0)
    return ('Rekord %d drag' % best, False) if best else None


class Game(sdk.GameBase):
    def setup(self):
        self.best = 0
        self.confirm = False
        self.new_game()

    def new_game(self):
        self.cancel('confirm')
        self.confirm = False
        self.moves = 0
        self.won = False
        while True:
            self.lit = [False] * (N * N)
            for i in self.rng.sample(range(N * N), 8):
                self.press(i)
            if sum(self.lit) >= 4:
                break

    def press(self, i):
        r, c = divmod(i, N)
        for rr, cc in ((r, c), (r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= rr < N and 0 <= cc < N:
                self.lit[rr * N + cc] = not self.lit[rr * N + cc]

    # --- sparfil
    def state(self):
        return {'lit': self.lit, 'moves': self.moves, 'best': self.best, 'won': self.won}

    def restore(self, d):
        lit = d['lit']
        if not (isinstance(lit, list) and len(lit) == N * N and all(isinstance(v, bool) for v in lit)):
            return False
        self.lit, self.moves, self.best, self.won = lit, int(d['moves']), int(d['best']), bool(d['won'])

    # --- tryck
    def cell_rect(self, i):
        r, c = divmod(i, N)
        return (BX + c * CELL, BY + r * CELL, BX + (c + 1) * CELL, BY + (r + 1) * CELL)

    def targets(self):
        ts = [('new', NEW_RECT)]
        if not self.won:
            ts += [('c%d' % i, self.cell_rect(i)) for i in range(N * N)]
        return ts

    def on_tap(self, name):
        if name == 'new':
            if self.moves > 0 and not self.won and not self.confirm:
                self.confirm = True
                self.later('confirm', 3.0, self.end_confirm)
            else:
                self.new_game()
                self.save_soon()
            self.invalidate()
            return
        self.press(int(name[1:]))
        self.moves += 1
        if not any(self.lit):
            self.won = True
            self.best = self.moves if not self.best else min(self.best, self.moves)
            self.save_now(force=True)
        else:
            self.save_soon()
        self.invalidate()

    def end_confirm(self):
        self.confirm = False
        self.invalidate(NEW_RECT)

    # --- ritning
    def paint(self, img, rect):
        if sdk.meets(rect, BOARD):
            sdk.fill(img, BOARD)                      # ritas något, ritas hela föremålet om (kanterna blandas mot bakgrunden)
            sdk.bbox(img, *BOARD, 18, sdk.CARD, sdk.CARD_BORDER, 1)
            for i in range(N * N):
                x0, y0, x1, y1 = self.cell_rect(i)
                col = LAMP if self.lit[i] else OFF
                if self.pressed == 'c%d' % i:
                    col = sdk.blend(col, (255, 255, 255), 0.2)
                sdk.rbox(img, x0 + 4, y0 + 4, x1 - 4, y1 - 4, 14, col)
        if sdk.meets(rect, SIDE):
            sdk.fill(img, SIDE)
            sdk.text(img, 580, 150, 'Drag', 400, 26, sdk.MUTED)
            sdk.text(img, 580, 230, str(self.moves), 300, 80, sdk.TEXT)
            if self.best:
                sdk.text(img, 580, 290, 'Rekord %d drag' % self.best, 400, 24, sdk.MUTED)
            if self.won:
                sdk.text(img, 580, 380, 'Klart på %d drag!' % self.moves, 500, 34, sdk.GREEN)
            sdk.button(img, NEW_RECT, 'Tryck igen' if self.confirm else 'Nytt spel',
                       'warn' if self.confirm else 'normal', pressed=self.pressed == 'new')
```

### 15.2 Fånga bollen: drag, tidtagare, delritning
Dra bollen in i ringen på 30 sekunder. Visar `on_down`/`on_move`/`on_up` för drag, `later` som tickar varje sekund, att bara det som
ändrats ritas om (`invalidate(union(gammal, ny))`) och att bara den del av planen som ritas om fylls (`sdk.clip`), och `on_close()`
som avslutar en pågående omgång.

<!-- spelfil: bollen -->
```python
"""Fånga bollen: dra bollen in i ringen. Hur många hinner du på 30 sekunder?"""
from dashpanel import gamesdk as sdk

META = {
    'api': 1,
    'id': 'bollen',
    'name': 'Fånga bollen',
    'desc': 'Dra bollen in i ringen. Hur många hinner du på 30 sekunder?',
    'version': 1,
}

FIELD = (24, 160, 1000, 580)                 # spelplanen
HUD_SCORE = (24, 96, 300, 152)
HUD_TIME = (724, 96, 1000, 152)
START = (400, 94, 624, 154)
BALL_R, GOAL_R = 34, 54
ROUND = 30                                   # sekunder


def draw_icon(im):
    sdk.circle(im, 20, 20, 88, sdk.GREEN)
    sdk.circle(im, 34, 34, 60, sdk.ICON_BG)
    sdk.circle(im, 44, 44, 40, sdk.BLUE_L)


def status(data):
    if data and data.get('best'):
        return 'Rekord %d' % data['best'], False
    return None


class Game(sdk.GameBase):
    def setup(self):
        self.best = 0
        self.score = 0
        self.left = ROUND
        self.running = False
        self.dragging = False
        self.place()

    def place(self):
        """Ny plats åt bollen och ringen, ungefär en halv skärm ifrån varandra."""
        x0, y0, x1, y1 = FIELD
        self.bx = self.rng.randrange(x0 + 60, x1 - 60)
        self.by = self.rng.randrange(y0 + 60, y1 - 60)
        while True:
            self.gx = self.rng.randrange(x0 + 80, x1 - 80)
            self.gy = self.rng.randrange(y0 + 80, y1 - 80)
            if (self.gx - self.bx) ** 2 + (self.gy - self.by) ** 2 > 300 ** 2:
                break

    def state(self):
        return {'best': self.best}

    def restore(self, data):
        self.best = max(0, int(data['best']))

    def on_close(self):
        self.running = False                 # tidtagarna stoppas av panelen när spelet lämnas
        self.dragging = False

    # --- omgången
    def targets(self):
        return [] if self.running else [('start', START)]

    def on_tap(self, name):
        self.score, self.left, self.running = 0, ROUND, True
        self.place()
        self.later('tick', 1.0, self.tick)
        self.invalidate()

    def tick(self):
        self.left -= 1
        if self.left <= 0:
            self.running = self.dragging = False
            if self.score > self.best:
                self.best = self.score
                self.save_now(force=True)
            self.invalidate()
        else:
            self.later('tick', 1.0, self.tick)
            self.invalidate(HUD_TIME, urgent=False)

    # --- dra bollen
    def ball_rect(self):
        return (self.bx - BALL_R - 2, self.by - BALL_R - 2, self.bx + BALL_R + 2, self.by + BALL_R + 2)

    def on_down(self, x, y):
        if self.running and (x - self.bx) ** 2 + (y - self.by) ** 2 <= (BALL_R + 20) ** 2:
            self.dragging = True
            self.on_move(x, y)

    def on_move(self, x, y):
        if not self.dragging:
            return
        old = self.ball_rect()
        self.bx = min(max(x, FIELD[0] + BALL_R), FIELD[2] - BALL_R)
        self.by = min(max(y, FIELD[1] + BALL_R), FIELD[3] - BALL_R)
        if (self.bx - self.gx) ** 2 + (self.by - self.gy) ** 2 <= (GOAL_R - BALL_R // 2) ** 2:
            self.score += 1
            self.dragging = False
            self.place()
            self.invalidate(FIELD)
            self.invalidate(HUD_SCORE)
        else:
            self.invalidate(sdk.union(old, self.ball_rect()))

    def on_up(self, x, y):
        self.dragging = False

    # --- ritning
    def paint(self, img, rect):
        if sdk.meets(rect, HUD_SCORE):
            sdk.text(img, 24, 138, 'Poäng %d' % self.score, 500, 34, sdk.TEXT)
        if sdk.meets(rect, HUD_TIME):
            sdk.text(img, 1000, 138, '%d s' % self.left, 500, 34, sdk.WARN if self.left <= 5 else sdk.TEXT, anchor='rs')
        if sdk.meets(rect, START) and not self.running:
            sdk.button(img, START, 'Start' if self.left == ROUND else 'Igen', 'primary', self.pressed == 'start')
        if sdk.meets(rect, FIELD):
            sdk.fill(img, sdk.clip(rect, FIELD), sdk.CARD)       # bara den del av planen som ska ritas om
            if sdk.meets(rect, (self.gx - GOAL_R, self.gy - GOAL_R, self.gx + GOAL_R, self.gy + GOAL_R)):
                sdk.circle(img, self.gx - GOAL_R, self.gy - GOAL_R, 2 * GOAL_R, sdk.GREEN)
                sdk.circle(img, self.gx - GOAL_R + 6, self.gy - GOAL_R + 6, 2 * GOAL_R - 12, sdk.CARD)
            if sdk.meets(rect, self.ball_rect()):
                sdk.circle(img, self.bx - BALL_R, self.by - BALL_R, 2 * BALL_R, sdk.BLUE_L)
```

## 16. Lämna spelet till enheten

1. Lägg filen som `games/<id>.py` i repot och skjut den till grenen `main` (spelen hämtas från grenen `games_ref` i panelens
   uppdateringsinställningar, standard `main`). Inget mer i repot behöver ändras, och panelens kod uppdateras inte av det här.
2. På panelen: tryck på spelikonen (bredvid kugghjulet) och sedan **Uppdatera spel**. Under korten visas "Klart: 1 nytt." (eller
   "1 uppdaterat", "1 filer hoppades över (<fil>)" om filen inte klarade kontrollen, med skälet i loggen `/run/dash-games-sync.log`).
3. **Byta ett spel:** ändra filen, skjut, tryck Uppdatera spel. En pågående omgång och rekord ligger kvar (sparfilen hör till id:t), så ändra inte
   vad som sparas på ett sätt som gör gamla sparfiler oläsbara utan att `restore` klarar dem.
4. **Ta bort ett spel:** radera filen ur `games/` på `main`, skjut, tryck Uppdatera spel (spelets sparfil i `game-data/` ligger kvar och återanvänds om filen läggs tillbaka).
5. Den vanliga knappen **Uppdatera** (inställningarna) installerar ny panelkod och rör inte spelen.
6. Innan allt detta: filen kontrolleras både av `Uppdatera spel` och av väljaren. Klarar den inte kontrollen läggs den inte på plats
   (en äldre fungerande version ligger kvar).

## 17. SDK-referens (allt spelet får röra)

`from dashpanel import gamesdk as sdk`

**Konstanter:** `sdk.API` (1), `sdk.AREA` `(0, 84, 1024, 600)`, `sdk.W` 1024, `sdk.H` 600, `sdk.ICON` 128, `sdk.ICON_BG`, `sdk.HIT_SLOP` 16,
`sdk.SAVE_DELAY` 8.0, `sdk.MAX_SAVE_BYTES` 200 000, och färgerna i 7.3.

**Ritverktyg:** `fill, rbox, bbox, circle, text, centered, text_width, fit, wrap, button, blend, icon, snap, inside, clip, union, meets, thousands`
(avsnitt 7.2). `sdk.snap(v)` är `int(floor(v + 0.5))` (avrundar halvt uppåt). `sdk.rbox_mask(w, h, r)` ger en mask (`L`-bild) för en rundad ruta.

**`GameBase`** (överskugga det du behöver, anropa aldrig basklassens privata metoder):

| Metod | När den anropas / vad den gör |
|---|---|
| `setup()` | nytt spel; sätt allt tillstånd i `self`. Anropas också om en sparfil var trasig |
| `restore(data)` | läs sparade data (`dict`); kasta fel eller ge `False` om de är konstiga |
| `state()` | ge det som ska sparas (JSON-vänlig `dict`) eller `None` |
| `paint(img, rect)` | rita det som ligger i `rect` (rutan är redan fylld med bakgrunden) |
| `targets()` | lista `(namn, ruta)` eller `(namn, ruta, slop)` med knappar |
| `on_tap(namn)` | en knapp trycktes (nedtryck och lyft på knappen) |
| `on_down(x, y)`, `on_move(x, y)`, `on_up(x, y)` | tryck som inte började på en knapp |
| `on_open()`, `on_close()` | spelet visas / lämnas |

| Tjänst | Gör |
|---|---|
| `self.invalidate(rect=None, urgent=True)` | rutan har ändrats, rita om den (utan `rect`: hela ytan) |
| `self.refresh(urgent=False)` | be panelen rita om (till exempel efter att `self.title` ändrats) |
| `self.save_soon()` / `self.save_now(force=False)` | spara snart / spara nu |
| `self.later(namn, sek, fn)` / `self.cancel(namn)` | anropa `fn()` om `sek` sekunder (en gång) / avbryt |
| `self.now()` | monoton tid i sekunder |
| `self.rng` | `random.Random` att slumpa med |
| `self.log(...)` | skriv en rad i panelens logg (`journalctl -u dash-panel`) |
| `self.pressed` | namnet på knappen som trycks ner just nu, annars `None` |
| `self.clock` | klockan som text, "12:34" |
| `self.title` | rubriken (börjar som `META['name']`) |
| `self.meta` | `META` som `dict` |
| `self.exit()` | lämna spelet (bara Tillbaka ska göra det) |

## 18. Hur panelen hittar och startar spelet (för felsökning)

- Väljaren söker igenom `/var/lib/dash-panel/games/` varje gång den öppnas. Bara filer med namn `[a-z0-9][a-z0-9_-]{1,31}.py`
  räknas. Den ändrade filen laddas om; resten minns den (på ändringstid och storlek).
- En fil som inte klarar kontrollen visas nedtonad med orsaken ("Kan inte öppnas: ..."). Samma kontroll görs av `Uppdatera spel` och
  av `gamecheck`, så det du ser där är det du ser i väljaren.
- Felen på enheten: `journalctl -u dash-panel -b` (spelets fel och `self.log`), `/run/dash-games-sync.log` (senaste Uppdatera spel).
- Sparfiler: `/var/lib/dash-panel/game-data/<id>.json` (och `.broken` om en fil lagts undan).
- Spelfilerna på enheten: `/var/lib/dash-panel/games/` (hämtade med Uppdatera spel). Panelen läser dem; ändra dem inte för hand (nästa
  Uppdatera spel skriver över).
