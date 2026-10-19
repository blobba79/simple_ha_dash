# dash-update: uppdatera simple_ha_dash från GitHub

`dash-update` hämtar en ny version av panelen från det här repot, kontrollerar den, byter, startar om tjänsten och lägger tillbaka förra versionen av sig själv om den nya inte blir frisk. Källan är grenen **`main`** i det publika repot `simple_ha_dash`, hämtad över https (ingen nyckel behövs). Plattan installerar första gången med `simple-ha-dash install`, som använder `dash-update`.

## Så går en ny version till

1. Ändringen görs och provas.
2. Den checkas in och skjuts till `main`.
3. Plattorna installerar den när någon trycker **Uppdatera** eller kör `simple-ha-dash update` / `dash-update apply` (eller av timern om den slagits på).

Vill man ha pågående arbete åtskilt från det plattorna hämtar: lägg en gren (till exempel `release`) och sätt `ref = release` i `/etc/dash-update/config.ini` på plattorna.

## Uppdatera från panelens skärm

Knappen **Uppdatera** på panelens inställningssida (kugghjulet) kör `dash-update apply` som en egen tillfällig tjänst
(`systemd-run --unit=dash-update-manual`) och visar versionen, hur det går och resultatet på skärmen (se `README.md`,
"Uppdatera från skärmen"). Det är samma `apply` som över ssh, med samma kontroller och återställning; timern och
`auto_apply` rörs inte. Knappen läser bara `VERSION.json` och avslutskoden/loggen från körningen.

## Vad `apply` gör

1. Hämtar grenen grunt (`--depth 1`) till `/var/lib/dash-update/cache.git` (över https; vid en `git@`-adress med en skrivskyddad deploy key).
2. Packar upp bredvid (`/opt/dash-panel.new`).
3. **Kontrollerar innan något byts:** nödvändiga filer finns, all Python går att tolka, `dashpanel.app` går att importera. En version som inte klarar det avvisas, märks som dålig och körs aldrig.
4. **Tjänstefilen:** har `systemd/dash-panel.service` ändrats mot den installerade krävs `--with-unit` (avslutskod 5), och `systemd-analyze verify` måste godkänna den. Utan flaggan ändras ingenting.
5. Byter katalog (gamla blir `/opt/dash-panel.prev`) och kör `systemctl restart dash-panel`.
6. **Väntar på att tjänsten är frisk:** uppe och samma process i hela fönstret (`health_seconds`, standard 40 s). Startar den om av sig själv, faller bort eller aldrig kommer upp räknas det som misslyckat.
7. **Misslyckat:** förra versionen läggs tillbaka (och förra tjänstefilen, om den byttes), tjänsten startas om, den nya versionen märks dålig (`/var/lib/dash-update/bad.json`) och sparas som `/opt/dash-panel.failed` för felsökning. Samma version försöks inte igen; en ny incheckning på grenen tas emot som vanligt.

**Skydd mot tysta överskrivningar:** vid varje installation sparas en kontrollsumma av koden i `VERSION.json` (`tree_sha256`). Nästa `apply` kontrollerar att `/opt/dash-panel` fortfarande är exakt det som lades dit. Har någon i stället lagt ut kod med ett tgz-paket eller redigerat för hand nekas uppdateringen (avslutskod 6) i stället för att tyst skriva över; `status` visar "Lokala ändringar: JA". Lägg in ändringarna i repot, eller kör `apply --force` för att medvetet skriva över. `__pycache__`, `.pyc` och `VERSION`/`VERSION.json` räknas inte. (Första uppdateringen på en gammal installation utan `VERSION.json` har inget att jämföra med.)

Config (`/etc/dash-panel/…`), token, `state.json`, `settings.json`, spelen (`/var/lib/dash-panel/games/`) och deras sparfiler (`game-data/`) ligger utanför `/opt/dash-panel` och rörs aldrig. Spelen hämtas av knappen **Uppdatera spel** på panelen (mappen `games/`, `.gitattributes` har `games export-ignore` så att den inte följer med här); den läser samma `config.ini` (och `games_ref`, se `config.example.ini`) men har inget med `dash-update` att göra.

## Kommandon (som root på dash)

```
dash-update status              # installerad version, om en ny finns, tjänstens läge
dash-update check               # kolla GitHub (ändrar inget på panelen)
dash-update apply               # installera senaste versionen på grenen
dash-update apply --dry-run     # hämta och kontrollera, byt inte
dash-update apply --with-unit   # tillåt att tjänstefilen byts
dash-update apply --commit <40 tecken>   # installera exakt en äldre/annan incheckning
dash-update apply --from-dir <katalog>   # installera från en lokal katalog (utan GitHub)
dash-update apply --force       # även om versionen redan är installerad eller märkt dålig
dash-update rollback            # tillbaka till .prev (en gång till går framåt igen)
dash-update keygen              # skapa deploy key, visa den publika delen
dash-update refresh-hostkeys    # hämta GitHubs värdnycklar på nytt
```

Avslutskoder: 0 klart eller ingen ändring, 1 fel före bytet (inget ändrat), 2 misslyckad uppdatering som återställdes, 3 en annan uppdatering pågår, 4 kritiskt (återställningen blev inte frisk, se `journalctl -u dash-panel`), 5 kräver `--with-unit`, 6 nekad: koden i `/opt/dash-panel` har ändrats utanför `dash-update`.

Loggen går till journalen: `journalctl -t dash-update`.

## Installation (engångs, på dash)

```
/opt/dash-panel/update/install-updater.sh          # timern av
/opt/dash-panel/update/install-updater.sh --timer  # timern på: kollar var 6:e timme
```

Dash-avbilden (r8 och senare) har redan `dash-update` och `simple-ha-dash`; det här behövs bara på äldre installationer.
Skriptet lägger `dash-update` i `/usr/local/sbin`, config i `/etc/dash-update/config.ini` (skrivs inte över), skapar en deploy key och hämtar GitHubs värdnycklar. Det rör inte panelen, nätet, skärmen, strömmen eller apt-skyddet.

Deploy key behövs bara för ett **privat** repo (`repo_url = git@github.com:...`): den privata delen skapas på plattan och lämnar aldrig enheten; den publika delen (som `keygen` skriver ut) läggs under repots *Settings → Deploy keys*, utan skrivrätt. Det publika repot hämtas över https utan nyckel.

Värdnycklar: `known_hosts` skrivs från `https://api.github.com/meta` (över TLS) och `StrictHostKeyChecking=yes` används. Byter GitHub nycklar nekar `dash-update` i stället för att gissa; då hjälper `dash-update refresh-hostkeys`.

## Automatik

`auto_apply = no` (standard) betyder att timern bara kollar och skriver resultatet till `/var/lib/dash-update/status.json`; du bestämmer själv med `dash-update apply`. Sätt `auto_apply = yes` i `/etc/dash-update/config.ini` för att timern ska installera själv.

## Säkerhet, ärligt

Panelen kör som root, så den som kan skriva till grenen som plattorna hämtar kan köra kod som root på dem när någon uppdaterar. Skydda GitHub-kontot med tvåfaktorsinloggning. Inget installeras av sig självt (`auto_apply = no`, timern av).

Uppdateraren kan inte rädda en enhet som hänger sig helt; då gäller som förut att dra ur strömmen. Ssh går inte via panelen, så en trasig panel stänger inte ute dig.

## Prov

```
python3 -m unittest -v update/tests/test_dash_update.py
```

24 prov mot ett lokalt git-repo och en låtsas-`systemctl`: lyckad installation och uppdatering, ingen ändring, `--dry-run`, `--from-dir`, `--commit` bakåt, manuell rollback, avvisning av syntaxfel/importfel/saknad fil/trasig tjänstefil, återställning efter krasch, omstartsstorm, sen krasch och misslyckat omstartskommando, tjänstefil som kräver godkännande och återställs, lås mot parallell körning, lokala ändringar som nekas (och som inte felaktigt räknas: `__pycache__`, `.pyc`, versionsfiler), onåbar källa, `auto`, `status`. Proven är kontrollerade genom sabotage: stängs hälsokontrollen eller kontrollen före bytet av faller proven.
