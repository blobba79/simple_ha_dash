# games/

Spelen till simple_ha_dash. **Ett spel är en enda Python-fil** (`<id>.py`) som innehåller reglerna, ritningen, ikonen som visas
i spelväljaren, raden om hur det står till och all data spelet behöver. Panelens egen kod (`dashpanel/`) innehåller inga spel.

| Fil | Spel |
|---|---|
| `blockpussel.py` | Blockpussel (8x8 rutnät, dra tre bitar åt gången, i stil med Block Blast) |
| `sudoku.py` | Sudoku (240 färdiga pussel, anteckningar, kontroll) |
| `patians.py` | Patians (klassisk solitär: bygg fyra högar i färg från ess till kung) |

## Lägga till, byta och ta bort spel
- Lägg filen här, skjut den till grenen `main` och tryck **Uppdatera spel** på panelen (spelikonen → knappen under korten). Spelet
  dyker upp i väljaren. Samma sak för att byta en fil. Ta bort ett spel: radera filen, skjut, tryck Uppdatera spel.
- Den vanliga knappen **Uppdatera** (inställningarna) rör inte spelen, och **Uppdatera spel** rör inte panelens kod. Mappen är
  `export-ignore` i `.gitattributes`, så den följer inte med det `dash-update` installerar.
- Filer som inte heter `<a-z, 0-9, _, ->.py` (som den här filen och `SKAPA-SPEL.md`) ignoreras. En spelfil som inte klarar kontrollen
  (syntax, `META`, tillåtna importer) hoppas över av Uppdatera spel och visas nedtonad med orsaken i väljaren.

## Skriva ett spel
**`SKAPA-SPEL.md`** beskriver allt som behövs: plattformen, mallen, `META`, hela SDK:t (`dashpanel/gamesdk.py`), ritning, tryck,
sparande, prestanda, vanliga fel, en checklista och tre färdiga exempel. Det är skrivet för att en AI ska kunna skapa ett kompatibelt
spel på egen hand med bara det dokumentet. Prova en fil innan den skjuts:

    python3 -m dashpanel.gamecheck games/<id>.py --png ut

`tools/make_sudoku_data.py` bygger om pusseltabellen i `sudoku.py` (mellan `# PUZZLES BEGIN` och `# PUZZLES END`).
