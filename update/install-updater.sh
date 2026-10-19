#!/bin/bash
# Installerar dash-update på dash. Kör som root:
#   /opt/dash-panel/update/install-updater.sh            installerar (timern förblir av)
#   /opt/dash-panel/update/install-updater.sh --timer    installerar och slår på timern (kollar var 6:e timme)
# Rör inte panelen, nätet, skärmen eller strömmen. Kan köras om (idempotent); config.ini skrivs inte över.
set -e
cd "$(dirname "$0")"
[ "$(id -u)" = 0 ] || { echo "Kör som root."; exit 1; }
install -d -m 755 /usr/local/sbin
install -m 755 dash-update /usr/local/sbin/dash-update
install -d -m 700 /etc/dash-update /var/lib/dash-update
[ -e /etc/dash-update/config.ini ] || install -m 600 config.example.ini /etc/dash-update/config.ini
install -m 644 systemd/dash-update.service systemd/dash-update.timer /etc/systemd/system/
systemctl daemon-reload
/usr/local/sbin/dash-update keygen
if [ "$1" = "--timer" ]; then
    systemctl enable --now dash-update.timer
    echo "Timern är påslagen (kollar var 6:e timme; installerar bara om auto_apply = yes i /etc/dash-update/config.ini)."
else
    echo "Timern är av. Slå på med: systemctl enable --now dash-update.timer"
fi
echo "Klart. Visa läget: dash-update status"
