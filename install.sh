#!/bin/bash
# Installerar simple_ha_dash (tjänsten dash-panel) så att den startar vid uppstart. Kör som root, efter
#   git clone https://github.com/blobba79/simple_ha_dash.git /opt/dash-panel
#   /opt/dash-panel/install.sh            installerar och slår på (startar vid nästa uppstart)
#   /opt/dash-panel/install.sh --now      installerar, slår på och startar direkt
#   /opt/dash-panel/install.sh --remove   stänger av och tar bort tjänsten (filerna i /opt/dash-panel ligger kvar)
set -e
cd "$(dirname "$0")"
[ "$(id -u)" = 0 ] || { echo "Kör som root."; exit 1; }
UNIT=/etc/systemd/system/dash-panel.service
if [ "$1" = "--remove" ]; then
    systemctl disable --now dash-panel.service 2>/dev/null || true
    rm -f "$UNIT"
    systemctl daemon-reload
    echo "Tjänsten är borttagen. Konsolen är tillbaka."
    exit 0
fi
[ -s /etc/dash-panel/token ] || echo "OBS: /etc/dash-panel/token saknas eller är tom, panelen visar då 'Token saknas'."
[ -s /etc/dash-panel/config.json ] || echo "OBS: /etc/dash-panel/config.json saknas: använd redigeringssidan (http://<plattans adress>:8099)."
install -d -m 755 /etc/dash-panel
# spelen: panelen läser dem ur /var/lib/dash-panel/games (knappen Uppdatera spel hämtar nya versioner senare)
install -d -m 755 /var/lib/dash-panel/games
for g in games/*.py; do
    [ -e "$g" ] || continue
    [ -e "/var/lib/dash-panel/games/$(basename "$g")" ] || install -m 644 "$g" /var/lib/dash-panel/games/
done
install -m 644 systemd/dash-panel.service "$UNIT"
systemctl daemon-reload
systemctl enable dash-panel.service
if [ "$1" = "--now" ]; then
    systemctl restart dash-panel.service
    sleep 3
    systemctl --no-pager --lines=5 status dash-panel.service || true
fi
echo "Klart. Loggar: journalctl -u dash-panel -b"
