# Tredjepartskomponenter

Koden i det här repot är MIT-licensierad (`LICENSE`). Följande delar kommer från andra och har egna licenser:

| Vad | Var | Licens | Källa |
|---|---|---|---|
| Typsnittet Roboto (Light, Regular, Medium; latin-delmängd, omvandlad till TTF) | `assets/fonts/*.ttf` | SIL Open Font License 1.1, `assets/fonts/OFL.txt` | The Roboto Project Authors, via npm-paketet `@fontsource/roboto` 5.3.0 |
| Ikoner ur Material Design Icons (vektorbanor och förrenderade PNG) | `assets/icons.json`, `assets/icons/*.png` | Apache License 2.0, `assets/LICENSE-icons-Apache-2.0.txt` | Pictogrammers, https://pictogrammers.com/library/mdi/ |
| QR-kodbiblioteket qrcodegen | `dashpanel/qrcodegen.py` | MIT (licenstexten i filens huvud) | Project Nayuki, https://www.nayuki.io/page/qr-code-generator-library |

Ikonerna är rasteriserade till PNG i de storlekar panelen använder; inga varumärkesikoner (kategorin Brand / Logos) används.

## Plattans programvara (inte i det här repot)
Dash-avbilden som panelen körs på bygger på Armbian/Debian (respektive pakets licens). För installationen i plattans inbyggda
minne används en ändrad Linux-kärna 6.12.82 och U-Boot 2024.01 (båda GPL-2.0); ändringarna, inställningarna och
byggbeskrivningen finns i `device/`.
