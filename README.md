# simple_ha_dash

Pekskärmspanel för Home Assistant på billiga Allwinner A33 "Q8"-plattor (1024x600) som kör dash-avbilden (Armbian). Ritar direkt på skärmen (/dev/fb0) och pratar med
Home Assistant över WebSocket. Ingen webbläsare och inget tillägg i HA. Vyer: lampor, dimvy, temperaturer,
inställningar (kugghjulet längst till höger) och spel (spelikonen bredvid kugghjulet öppnar en sida där man väljer spel).
Spelen är egna filer i mappen `games/` (Blockpussel, Sudoku och Patians följer med) och nya spel läggs till utan att panelens kod
ändras, se [Spel](#spel) och `games/SKAPA-SPEL.md`.

## Installera på en platta

Plattan ska köra dash-avbilden (Armbian, från SD-kort eller installerad i det inbyggda minnet) och vara på nätet. git,
Python 3 och Pillow finns i avbilden. Logga in med ssh som root och kör:

    git clone https://github.com/blobba79/simple_ha_dash.git /opt/dash-panel
    /opt/dash-panel/install.sh --now

`install.sh --now` lägger in tjänsten `dash-panel`, slår på den vid uppstart, kopierar spelen till `/var/lib/dash-panel/games`
och startar panelen. Home Assistants adress och token fylls i på inställningskortet (`dash-config.txt` på DASHCFG) före
första start; vad som visas väljs sedan på redigeringssidan `http://<plattans adress>:8099`.

Uppdatera: knappen **Uppdatera** på panelens inställningssida, eller `dash-update apply` över ssh (se `update/README.md`;
första gången ersätts git-klonen av en vanlig installation med `VERSION.json`). Ta bort: `/opt/dash-panel/install.sh --remove`
och sedan `rm -rf /opt/dash-panel`. Panelens interna namn är `dash-panel` (katalogen `/opt/dash-panel`, tjänsten
`dash-panel.service`), som på plattor som installerats tidigare.

## Filer

| Sökväg | Vad |
|---|---|
| `/opt/dash-panel/` | programmet (denna katalog) |
| `/etc/dash-panel/config.json` | vilka flikar och vad som visas på dem, ordning och namn |
| `/etc/dash-panel/token` | Home Assistants åtkomsttoken (läge 600, skrivs aldrig i andra filer eller loggar) |
| `/etc/dash-panel/touch.json` | pekskärmens kalibrering |
| `/var/lib/dash-panel/state.json` | senast använd ljusstyrka per dimbar lampa |
| `/var/lib/dash-panel/games/` | spelfilerna, en `.py` per spel (läggs dit av **Uppdatera spel**, se nedan) |
| `/var/lib/dash-panel/game-data/` | spelens sparfiler, `<spel>.json` (rekord, pågående spel; kan tas bort utan följder) |
| `/var/lib/dash-panel/games-sync.json` | vilka spelfiler som Uppdatera spel själv lagt dit (bara de tas bort när de försvinner ur GitHub) |
| `/var/lib/dash-panel/game.json`, `sudoku.json` | äldre sparfiler (före version 1.4); Blockpussel och Sudoku tar över dem första gången och rör dem inte mer |
| `/var/lib/dash-panel/settings.json` | skärmens ljusstyrka (10-100 %) och tid tills skärmen släcks (5-120 s), ställs in på inställningssidan |
| `/etc/systemd/system/dash-panel.service` | tjänsten som startar panelen vid uppstart |

Programkoden ligger i `dashpanel/` (`ui.py` gränssnitt och pek, `views.py` ritning, `sysinfo.py` Wi-Fi-styrka och
omstart/avstängning/avslut, `battery.py` batteriets laddnivå, `display.py` bakgrundsbelysning och skärminställningar,
`qr.py` QR-bild och spelplattformen: `gamesdk.py` det spel skriver mot (basklassen `GameBase`, ritverktyg, sparfil),
`gamelib.py` som hittar, kontrollerar och laddar spelfilerna, `gamepick.py` spelväljaren, `gamesync.py` knappen Uppdatera
spel och `gamecheck.py` provet en spelförfattare kör på sin fil). Spelen själva ligger i `games/` (utanför `dashpanel/`).
`dashpanel/qrcodegen.py` är Project Nayukis QR-biblioteket (MIT-licens, medföljer oförändrat med licenstexten i filens
huvud); ikonerna är Material Design Icons (Apache 2.0) och typsnittet Roboto (SIL Open Font License 1.1). Se
`THIRD-PARTY-NOTICES.md`.

## Installera / ta bort för hand

Med koden i `/opt/dash-panel` (se ovan):

    /opt/dash-panel/install.sh --now      # installerar, slår på vid uppstart och startar direkt
    /opt/dash-panel/install.sh --remove   # stänger av och tar bort tjänsten; konsolen kommer tillbaka

Loggar: `journalctl -u dash-panel -b`. Starta om: `systemctl restart dash-panel`.

## Ändra vad som visas

Öppna redigeringssidan i en webbläsare på samma nät: `http://<dashs adress>:8099`
(adressen står också på skärmen när en flik är tom). Sidan är byggd som Home Assistants egna inställningar:
flikarna i en meny till vänster (bakom ☰ på mobilen), och för varje flik

- **rubrik och ikon**, och på knappflikar bockrutan **Visa knappen som slår om alla lampor på fliken** (`show_all`)
  med texten på knappen (`all_label`);
- **På fliken**: rutorna som de ligger på panelen. Dra i greppet för att flytta (fungerar med finger), tryck på en
  ruta för namn, dimbar (lampor), decimaler (sensorer) eller för att ta bort den;
- **Lägg till från Home Assistant**: sök (namn, område, enhet, id), filtrera på typ (Lampor, Scener, Automationer,
  Hjälpare, Temperatur, Luftfuktighet, El och energi, Batteri …) och på område, och gruppera listan efter
  **område och enhet** (inom ett område samlas det som sitter i samma enhet i en egen grupp), **enhet**, typ eller
  inte alls. Alla grupper går att fälla ihop. **Lägg till alla** lägger till en hel grupp, så mycket som får plats.

**Ny flik** kan fyllas direkt från ett område i Home Assistant. Alla flikar går att ta bort; utan flikar visar
panelen en välkomstskärm som förklarar vad den gör, med adressen hit och en QR-kod. Tre sorters flikar:

| Flik | Vad som får ligga där | På panelen |
|---|---|---|
| Knappar (högst 8) | lampor, strömbrytare, fläktar, automationer, hjälpare av/på (`input_boolean`), scener, skript, knappar (`button`, `input_button`) | växel för på/av; scener, skript och knappar får en tryckknapp (▶) som kör dem och visar "Aktiverad"/"Startat" en stund |
| Värden (högst 11) | sensorer (temperatur, luftfuktighet, el, batteri …), binära sensorer, hjälpare med värde (`input_number`, `counter`, `input_select`, `input_text`, `input_datetime`), `number`, `select`, väder, personer, jalusier och portar, lås, mediaspelare, klimat, sol, uppdateringar, timrar | två stora och nio små kort; text visas på svenska (Öppen/Stängd, Hemma, Halvklart, 7 °C …). **Tryck på ett kort med ett tal** öppnar grafen för det |
| Graf (högst 3 kurvor) | sensorer och hjälpare med tal | hur värdena ändrats: 6 tim, 24 tim, 7 dagar eller 30 dagar (knappar ovanför grafen). Max och min står stort med tid och är markerade i kurvan |

"Alla lampor" och siffran i fliken ("3 tända") räknar bara lampor och strömbrytare, aldrig scener eller automationer,
och knappen visas bara om fliken har minst en lampa (då rymmer fliken sju saker plus knappen). En automations växel
slår på och av automationen; den körs inte. Mediaspelare, klimat och luftfuktare kan också ligga på en knappflik
(på/av). Områden och enheter läses ur Home Assistants register; har token inte rätt att läsa dem visas listan utan.

Graferna hämtas ur Home Assistants historik: upp till två dygn rå historik, längre som timvärden ur
långtidsstatistiken (medel, min och max per timme). Sensorer utan statistik (`state_class`) kan visas upp till en
vecka. Inget sparas på plattan.

**Säkerhetskopia** (under Allmänt): **Ladda ned konfigurationen** ger en fil (`simple_ha_dash-<datum>.json`) med
flikarna, vad som ligger på dem, namn och inställningarna. **Läs in från fil** på en annan platta visar vad filen
innehåller (och vad som saknas i den Home Assistant) innan den ersätter det som visas; det gäller först när du
sparar. Home Assistants adress och token följer inte med.

Sidan nås bara från det lokala nätet och visar eller ändrar aldrig tokenen.

Konfigurationen kan också ändras för hand i `/etc/dash-panel/config.json` (läses om av sig själv inom ett par
sekunder, eller `systemctl kill -s HUP dash-panel`). Är filen trasig sparas en kopia som `config.json.broken`.


## Pek

Kalibreras om med `tools/touchtest.py` (stoppa tjänsten först: `systemctl stop dash-panel`). Pekenheten hittas på
namnet (silead_ts); kan åsidosättas med `DASH_INPUT`.

## Hur det beter sig

- Tryck på lampans symbol eller växel = på/av. Tryck på namnet (med ›) öppnar dimvyn. "Alla lampor" slår om alla
  (om fliken visar den knappen, se bockrutan ovan).
- Skärmen ändras direkt och går tillbaka om Home Assistant inte bekräftar inom ca 2 s.
- Dimbara lampor minns sin ljusstyrka: släckt och tänd igen ger samma nivå som sist.
- Dimvyn för en lampa som kan färgtemperatur eller färg har tre lägen överst: **Ljusstyrka**, **Vitt** (en list från
  varmt till kallt med tre snabbval, inom lampans eget område i kelvin) och **Färg** (tryck eller dra i fältet:
  nyans åt sidan, mättnad uppifrån, vitt längst ned, och åtta färdiga färger). Reglaget för ljusstyrka till höger
  finns kvar i alla lägen. Ett färgval tänder en släckt lampa. Under drag skickas högst ca fyra värden i sekunden.
- Förlorad kontakt: sidfoten visar "Ingen kontakt med Home Assistant" direkt och värdena blir grå efter en kort
  frist (`stale_after`, 4 s). Gammal data visas aldrig som aktuell. Panelen ansluter om av sig själv.
- Tid visas i Europe/Stockholm (dash går på UTC).
- **Spelikonen** (en spelkontroll) och **kugghjulet** sitter längst till höger i överraden, till höger om klockan, på alla
  sidor utom i själva spelet. Spelikonen öppnar spelväljaren, kugghjulet inställningssidan.
- **Inställningssidan** (kugghjulet): QR-kod till redigeringssidan
  (`http://<dashs adress>:8099`, mobilen måste vara på samma Wi-Fi), adressen, IP och port i klartext, hur man startar
  panelen igen efter Avsluta (`ssh root@<IP>` och `systemctl start dash-panel`), knapparna **Uppdatera** (med
  versionsnumret, se nedan), **Starta om**, **Stäng av** och **Avsluta** samt två reglage. Knapparna ber om bekräftelse först. Starta om och Stäng av kör `systemctl reboot` /
  `systemctl poweroff` (ren nedstängning); efter avstängning måste strömsladden dras ur och sättas i. **Avsluta**
  stoppar bara panelens tjänst (`systemctl stop --no-block dash-panel.service`): skärmen går tillbaka till
  textkonsolen, enheten och ssh fortsätter, redigeringssidan försvinner med panelen och tjänsten startas inte om
  förrän man kör `systemctl start dash-panel` över ssh (eller enheten startar om). Sidan lämnas av sig själv efter
  `dim_timeout` sekunder utan tryck.
- **Reglagen** på inställningssidan: *Ljusstyrka* (10-100 %, i steg om 10 %, syns direkt medan man drar) och *Skärmen
  släcks efter* (5-120 s, i steg om 5 s; standard 60 s). Värdena sparas när fingret lyfts i `settings.json` och gäller
  också efter omstart. Skärmen släcks genom att bakgrundsbelysningen (`/sys/class/backlight/*`, nivå 0) stängs av; ett
  tryck på skärmen tänder den igen, och det första trycket räknas bara som väckning (det trycker aldrig på en lampa
  eller knapp). Skärmen släcks inte medan man drar i ett reglage eller medan enheten stängs ned. När panelen stannar,
  hur det än sker, tänds skärmen igen så att konsolen syns (panelen gör det själv, tjänsten har en `ExecStopPost`
  som reserv). Finns ingen styrbar bakgrundsbelysning visas ett besked i stället för reglagen och skärmen släcks aldrig.
- **Wi-Fi-styrka** visas i procent (1-100) bredvid wifisymbolen i sidfoten på alla sidor. Den läses ur
  `/proc/net/wireless` var 5:e sekund (inget ändras i nät eller Wi-Fi) och räknas om från dBm: -100 dBm = 0 %,
  -50 dBm eller bättre = 100 %. Under 30 % blir siffran orange. Utan Wi-Fi-signal visas ingen siffra.
- **Batteri** visas i sidfoten till vänster om wifi: en batterisymbol (blå fyllning, gul blixt när det laddar), uppskattad
  laddnivå i procent och texten "Laddar", "Full", "Laddar inte" eller "På batteri". Orange under 20 % och röd under 10 % när det
  inte laddar. Visas inget batteri i sysfs (`/sys/class/power_supply`, första posten med `type` = Battery) syns inget alls.
  Läses var 10:e sekund, skrivskyddat (`battery.py`). **Nivån är en uppskattning:** PMIC:ns egen procentsiffra används inte
  (den är okalibrerad på dash). I stället räknas cellens vilospänning ut (spänning minus ström gånger inre resistans
  vid laddning, 170 mΩ, median av fem avläsningar) och översätts med en vanlig LiPo-kurva. 100 % är 4,0 V vilospänning (där
  `dash-batt-limit` pausar laddningen) och 0 % är 3,3 V. Läget byts först när det varit så i sex avläsningar i rad (en minut),
  så att korta laddpauser inte får texten att blinka. **"Full"** visas (som "100 % Full", utan blixt) när laddningen står
  still med nätdelen inkopplad (PMIC:n visar `Not charging` eller `Full`) och nivån är minst 85 %: det gäller både när
  mjukvarugränsen 4,0 V pausat laddningen och när hårdvarugränsen 4,1 V avslutat den. Efter en paus har cellens spänning
  vilat ut några tiopartar volt, så uppskattningen ligger då på 90-95 % fast ingen energi gått åt; därför visas 100 %.
  Under 85 % (släpps först vid 82 %) visas nivån som den är med "Laddar inte". Värdena kan ändras med `DASH_BATT_FULL_UV`,
  `DASH_BATT_EMPTY_UV`, `DASH_BATT_FULL_SNAP` (85) och `DASH_BATT_R_MOHM` (miljövariabler i tjänstefilen).
- Med fyra flikar blir märkena "N tända" bara siffran när flikraden annars inte ryms, därefter ritas siffran i en tätare ruta
  (spelikonen tar plats i hörnet); först sist kortas något fliknamn.

## Uppdatera från skärmen
Knappen **Uppdatera** på inställningssidan visar versionen (`Version 1.1 · 9efc105`: paketets versionsnummer,
`__version__` i `dashpanel/__init__.py`, och incheckningen som `dash-update` installerade, ur `/opt/dash-panel/VERSION.json`).
Ett tryck ger en fråga; **Uppdatera** kör då `dash-update apply` (se `update/README.md`) som en egen tillfällig
systemd-tjänst (`dash-update-manual`), så att den lever kvar när uppdateraren startar om panelen. Skärmen visar
"Söker efter ny version …", sedan "Installerar ny version …" med versionens nummer, och till sist resultatet:
- **Du har senaste versionen** (inget nytt att hämta, inget startas om),
- **Uppdaterad** (panelen har startats om och visar den nya versionen; den nystartade panelen tar upp tråden själv
  eftersom panelen minns i `/var/lib/dash-panel/update.json` att en uppdatering pågår),
- **Uppdateringen gick inte igenom** (uppdateraren lade tillbaka förra versionen), eller **Det gick inte att uppdatera**
  med orsaken (till exempel nekad för att koden ändrats för hand, tjänstefilen kräver godkännande, ingen kontakt med GitHub).
Hela uppdateringen tar ungefär 50 sekunder om det finns en ny version (panelen startar om efter cirka 10 s, och
uppdateraren följer sedan panelen i 40 s innan den räknar versionen som frisk); finns ingen ny version är det klart på några sekunder.
Resultatet visas tills man trycker (eller i 8 s). Knappen ändrar inget i uppdaterarens egna inställningar: timern
(`dash-update.timer`) och `auto_apply` i `/etc/dash-update/config.ini` är som förut (av), så uppdatering sker bara när man
trycker på knappen eller kör `dash-update apply` över ssh. Resultatfilerna ligger i `/run` (`dash-update-manual.rc`
och `.log`); miljövariablerna `DASH_UPDATE_BIN`, `DASH_UPDATE_RUN` och `DASH_UPDATE_MARKER` styr dem för prov.

## Spel
Spelen är **egna filer**, en Python-fil per spel i mappen `games/` i GitHub-repot (`blobba79/dash-panel`). Panelen
innehåller inga spel i sin egen kod: den hittar filerna på enheten (`/var/lib/dash-panel/games/`), kontrollerar dem och
visar dem. Att lägga till, byta eller ta bort ett spel är att lägga till, byta eller ta bort en fil.

**Spelikonen** bredvid kugghjulet (på flikarna, dimvyn och inställningarna) öppnar **spelväljaren**, "Spel". Den söker
igenom spelmappen varje gång den öppnas och visar ett kort per spel: spelets egen ikon, namn, en rad om spelet och, om det
finns, hur det står till ("Pågående spel · 41 rutor kvar", "Rekord 1 234", "Klarade sudokun: 3"; läses ur spelets
sparfil utan att starta spelet). Fyra kort i taget, finns fler bläddrar man med pilarna. En spelfil som inte går att
köra visas nedtonad med orsaken ("Kan inte öppnas") i stället för att döljas, och stoppar aldrig väljaren. Ett tryck på
ett kort öppnar spelet. **Tillbaka** i ett spel går till väljaren, **Tillbaka** i väljaren till flikarna. Efter 5 minuter utan tryck
lämnar panelen spelen av sig själv (väljaren och spelen räknas som samma sida, `GAME_IDLE_SECONDS`), och skärmen släcks som
vanligt med spelet kvar.

### Uppdatera spel
Under korten sitter knappen **Uppdatera spel**. Den hämtar mappen `games/` från GitHub och lägger filerna i spelmappen:
- Den **vanliga knappen Uppdatera** (inställningarna) rör inte spelen, och **Uppdatera spel** rör inte panelens kod.
  `games/` är `export-ignore` i `.gitattributes`, så den ingår inte i det `dash-update` installerar.
- Hämtningen går som en egen tillfällig systemd-tjänst (`dash-games-sync`, som knappen Uppdatera gör) med samma uppgifter
  som `dash-update` (`/etc/dash-update/config.ini`). Den läser grenen `games_ref` (nyckel i samma fil,
  under `[update]`; standard `main`) skrivskyddat. Resultatet visas under korten ("Klart: 1 nytt, 1 uppdaterat.",
  "Spelen är redan aktuella.", "Det gick inte: …") och spelen i väljaren läses om.
- Varje fil kontrolleras innan den läggs på plats (samma kontroll som väljaren gör). En fil som inte klarar den hoppas över
  och rapporteras, och en äldre fungerande version ligger kvar. Nya och ändrade filer installeras, spel som tagits bort ur
  repot tas bort från enheten (bara de som den här hämtningen själv lagt dit, de står i `games-sync.json`), och sparade
  resultat i `game-data/` rörs aldrig. Hittas ingen `games/`-mapp alls tas inget bort.
- Nytt på en enhet: spelmappen är tom tills man trycker **Uppdatera spel** en gång.
- Lägga till ett spel: lägg `games/<id>.py` på grenen `main`, tryck på Uppdatera spel på panelen. Ta bort: radera filen på `main`
  och tryck igen. Så skriver man ett spel: **`games/SKAPA-SPEL.md`** (en komplett beskrivning som en AI kan skriva spel efter).
- Prova en spelfil innan den läggs i repot: `python3 -m dashpanel.gamecheck games/mitt_spel.py --png ut`.

### Så fungerar plattformen
- En spelfil importerar bara `dashpanel.gamesdk` (och några ofarliga standardmoduler och Pillow), har en `META`-dict (id, namn,
  rad om spelet), en klass `Game(sdk.GameBase)` och gärna `draw_icon(im)` (ikonen) och `status(data)` (raden i väljaren). All
  tråkig hantering sköter `GameBase`: rubrikraden med Tillbaka och klockan, tidtagare, att bara ritade rutor skickas till
  skärmen, tryck på knappar, sparfilen (atomisk skrivning, trasig fil läggs undan som `.broken`) och att ett fel i spelet bara
  loggas och för panelen tillbaka till flikarna, sparfilen läggs undan som `<id>.json.broken` (panelen faller inte). SDK:ts version är `API = 1` (`META['api']`); en spelfil
  som kräver ett nyare API visas som "kräver nyare panel".
- Filen kontrolleras innan den körs: syntax, `META`, och ett **skyddsräcke** som stoppar importer utanför listan och
  `open`/`exec`/`eval`/`__class__` och liknande. Det är till för att fånga misstag och slarvigt genererad kod, **inte en
  sandlåda**: spelen körs i panelens process (som root), så en spelfil ska man bara lägga i repot om man litar på den.
- Spelen bor i panelprocessen (inget extra program) och delar skärm, klocka och sparmapp. Sparfilen är
  `/var/lib/dash-panel/game-data/<id>.json` (`{"sdk":1,"game":"<id>","data":{…}}`, högst 200 000 tecken) och skrivs högst var 8:e
  sekund, direkt när spelet säger till, när man lämnar spelet och när panelen stoppas.
- Gamla sparfiler: en spelfil kan ange `META['legacy_save']` (en `.json` under `/var/lib/dash-panel/`); finns ingen ny sparfil
  läser spelet den gamla en gång. Så behöll Blockpussel och Sudoku rekord och pågående spel när de blev spelfiler.
- Miljövariabler för prov: `DASH_GAMES` (spelmappen, eller `none`), `DASH_GAMEDATA` (sparmappen, eller `none`) och
  `DASH_GAMES_RUN` (var hämtningens resultatfiler ligger, standard `/run`). Utan riktig skärm är alla tre `none`.

## Sudoku
`games/sudoku.py`. Ett enkelt sudoku: 9x9 rutor, varje rad, kolumn och 3x3-ruta ska innehålla 1-9 en gång. Brädet ligger till vänster; en
del siffror är givna (vita), resten skriver man själv (blå).
- **Tryck på en tom ruta**: den markeras och en liten ruta med siffrorna 1-9, **Radera** och **OK** visas till höger (den
  skymmer inte brädet). Varje siffra visar hur många som återstår att lägga ("3 kvar"; "klar" och avstängd när alla nio ligger).
- **Upp till fyra siffror i en ruta.** Siffer-rutan ligger kvar när man trycker på en siffra: tryck fler, eller tryck en
  vald siffra igen för att ta bort den. **En siffra är svaret** (stor och blå, räknas för krockar, Kontrollera och
  för att sudokut blir klart). **Två till fyra siffror är anteckningar**: små siffror, två och två, i rutan, som en
  påminnelse om vad rutan kan vara (de räknas inte som svar, ger ingen krock och kontrolleras inte av Kontrollera; en
  ruta med bara anteckningar räknas som tom). Man trycker **OK** när man är klar (även med en enda siffra); väljer man
  den **fjärde** siffran stängs rutan av sig själv. **Radera** tömmer rutan (svar och anteckningar) och rutan ligger
  kvar öppen. Ett tryck utanför rutan eller på den valda rutan igen stänger den med det som redan valts kvar, ett tryck på
  en annan ruta flyttar valet. En ruta som redan har fyra siffror öppnas med dem markerade; fler går inte att lägga till
  förrän en tagits bort. Rutorna i samma rad, kolumn och 3x3-ruta ljusnar svagt medan en ruta är vald.
- Samma siffra två gånger i en rad, kolumn eller 3x3-ruta blir **röd** (båda rutorna) och meddelandet till höger säger det.
- **Kontrollera** jämför svaren (inte anteckningarna) med den rätta lösningen: fel rutor får röd kant ("2 rutor är fel") eller "Inga fel hittills".
  Markeringen försvinner när man ändrar något eller efter 7 s.
- Klart när alla rutor är fyllda utan krockar: "Klart!" och knappen **Nytt spel**. Antalet klarade sparas.
- **Nytt spel** frågar först ("Tryck igen") om ett spel pågår.
- Pusslen ligger i en färdig tabell i själva spelfilen (mellan `# PUZZLES BEGIN` och `# PUZZLES END`; 240 pussel, gjorda av `tools/make_sudoku_data.py`, ändra inte för hand): varje pussel
  har exakt en lösning och går att lösa utan att gissa (bara "enda möjliga siffra" och "enda möjliga ruta"), 38-44 givna
  siffror. Vid varje nytt spel slumpas ett pussel om (byt siffror, byt rader och kolumner inom grupperna om tre och
  grupperna, spegla), så att de sällan känns igen. Inget pussel görs på dash (det vore för tungt för processorn).
  `python3 tools/make_sudoku_data.py --check` kontrollerar tabellen.
- Sparfilen `/var/lib/dash-panel/game-data/sudoku.json` skrivs högst var 8:e sekund, direkt när
  sudokut blir klart, när man lämnar spelet och när panelen stoppas. Trasig fil ger ett nytt spel; ett fel i spelet lägger
  undan filen som `sudoku.json.broken` och panelen går tillbaka till flikarna. Ta bort filen för att nollställa. Äldre sparfilen
  `/var/lib/dash-panel/sudoku.json` tas över första gången (`legacy_save`).
  Anteckningarna sparas i fältet `notes` (ruta -> siffror, bara rutor som har några); fältet är valfritt, så filer från
  före anteckningarna läses som vanligt (versionen i filen är fortfarande 1).

## Blockpussel
`games/blockpussel.py`. Ett enkelt spel i stil med Block Blast. Öppnas från spelväljaren. Rutnät 8x8; tre bitar åt gången i fältet till höger. Dra en bit med fingret till rutnätet (den visas ovanför fingret och
snäpper till närmaste lediga plats; rader och kolumner som blir fulla lyser upp innan man släpper). Hela rader och
kolumner försvinner; när alla tre bitarna är lagda delas tre nya ut. Spelet är slut när ingen av bitarna som är kvar får
plats. Bitarna kan inte vridas. Poäng: en per ruta i biten, plus 10 per rensad linje gånger antalet linjer i samma drag i
kvadrat, gånger kombon (rensning i följd; kombon bryts efter tre drag utan rensning), plus 300 för ett helt tomt bräde.
Utdelningen ger helst en uppsättning där alla tre går att lägga i någon ordning.
- **Tillbaka** (uppe till vänster) går till spelväljaren. Spelet står kvar (sparas), så man kan komma tillbaka till det.
- **Nytt spel** frågar först ("Tryck igen") om ett spel pågår. Rekordet nollställs inte.
- Panelen går vidare som vanligt medan spelet visas (Home Assistant, klockan). Skärmen släcks efter den inställda tiden
  utan tryck men spelet står kvar; första trycket tänder bara. Efter 5 minuter utan tryck lämnar panelen spelet av sig
  själv och visar flikarna (`GAME_IDLE_SECONDS` i `ui.py`).
- Går något fel i spelet loggas det, panelen går tillbaka till flikarna och sparfilen läggs undan som `blockpussel.json.broken`;
  panelen faller inte.
- Sparfilen `/var/lib/dash-panel/game-data/blockpussel.json` skrivs högst var 8:e sekund, när spelet lämnas och när panelen
  stoppas. Ta bort filen för att nollställa rekordet. Äldre sparfilen `/var/lib/dash-panel/game.json` tas över första gången.

## Miljövariabler (för prov och demo)

På dash behövs inga. `DASH_CONFIG`, `DASH_FB`, `DASH_INPUT`, `DASH_TOUCH_CAL`, `DASH_STATE` (se `dashpanel/app.py`) samt
`DASH_SETTINGS` (sökväg till `settings.json`, eller `none`) och `DASH_BACKLIGHT` (katalog i sysfs, eller `none`) samt
`DASH_BATTERY` (batteriets katalog i sysfs, eller `none`) samt `DASH_GAMES` (spelmappen, eller `none`), `DASH_GAMEDATA`
(spelens sparmapp, eller `none`) och `DASH_GAMES_RUN` (knappen Uppdatera spel) samt
`DASH_UPDATE_BIN`, `DASH_UPDATE_RUN` och `DASH_UPDATE_MARKER` (knappen Uppdatera). Utan riktig skärm (`DASH_FB=none`) rör panelen varken `/sys`
eller `/var/lib` och visar inget batteri om inget av detta anges.

## Prov

    python3 -m dashpanel.gamecheck games/blockpussel.py    # provar en enskild spelfil (se games/SKAPA-SPEL.md)
    python3 update/tests/test_dash_update.py               # uppdateraren mot ett lokalt git-repo och en låtsas-systemctl

På dash (när ingen sitter vid skärmen): `tools/fbshot.py` sparar en skärmbild av det som visas och
`tools/touch_inject.py` ger fiktiva tryck i pekenheten, så att reglage, släck/väck och Avsluta kan provas på riktigt.
Tryck aldrig blint (se filens huvud): på flikarna ligger lampor där knapparna på andra sidor sitter, och
`guard-tap` trycker bara om rätt sida visas. Riktiga och fiktiva fingrar trycker i varandra, så rör inte skärmen under provet.

## Rör inte

Nätverk, Wi-Fi, wifi-rescue, dash-netlog, inloggningstexten och getty@ttyGS0 hör inte till panelen.

## Licens

Koden är MIT-licensierad, se `LICENSE`. Typsnitten (Roboto, SIL Open Font License 1.1), ikonerna (Material Design Icons,
Apache 2.0) och `dashpanel/qrcodegen.py` (MIT, Project Nayuki) har sina egna licenser, se `THIRD-PARTY-NOTICES.md`.
Källorna till plattans ändrade kärna och U-Boot (för installationen i det inbyggda minnet) ligger i `device/`.
