#!/bin/bash
# Självprov av dash-update mot RIKTIGT systemd, men med en låtsastjänst (dash-update-selftest.service)
# och ett lokalt git-repo. Rör inte dash-panel, nätet, skärmen eller strömmen. Kör som root på dash:
#   bash /opt/dash-panel/update/tests/selftest-on-dash.sh
# Provar: lyckad installation, lyckad uppdatering, kraschande version -> automatisk återställning,
# avvisad version (syntaxfel). Städar efter sig. Avslutskod 0 = allt som väntat.
set -u
DU=${DU:-/usr/local/sbin/dash-update}
W=/var/tmp/dash-selftest
APP=/opt/dash-selftest
UNIT=dash-update-selftest.service
FAIL=0
ok()  { echo "  OK   $*"; }
bad() { echo "  FEL  $*"; FAIL=1; }
cleanup() {
    systemctl stop "$UNIT" 2>/dev/null
    rm -f /run/systemd/system/"$UNIT"
    systemctl daemon-reload
    rm -rf "$W" "$APP" "$APP.new" "$APP.prev" "$APP.failed" /run/dash-selftest-unit
}
[ "$(id -u)" = 0 ] || { echo "Kör som root."; exit 1; }
cleanup
mkdir -p "$W/state" "$W/work" /run/dash-selftest-unit

cat > /run/systemd/system/"$UNIT" <<EOF
[Unit]
Description=Låtsastjänst för dash-update-självprov (ingen koppling till dash-panel)
[Service]
Type=simple
WorkingDirectory=$APP
ExecStart=/usr/bin/python3 -m dashpanel
Restart=always
RestartSec=1
StartLimitIntervalSec=30
StartLimitBurst=5
EOF
systemctl daemon-reload

git init -q --bare "$W/remote.git"
git -C "$W/work" init -q -b release
git -C "$W/work" config user.email t@t; git -C "$W/work" config user.name t
git -C "$W/work" remote add origin "file://$W/remote.git"

mkver() {   # mkver <namn> <app.py-innehåll>
    rm -rf "$W/work/dashpanel"; mkdir -p "$W/work/dashpanel"
    printf '' > "$W/work/dashpanel/__init__.py"
    printf 'from .app import main\nmain()\n' > "$W/work/dashpanel/__main__.py"
    printf '%s\n' "$2" > "$W/work/dashpanel/app.py"
    git -C "$W/work" add -A; git -C "$W/work" commit -q -m "$1"
    git -C "$W/work" push -q -f origin release
}
GOOD='import time
VERSION = "NAMN"
def main():
    while True:
        time.sleep(1)'
CRASH='import sys, time
VERSION = "NAMN"
def main():
    time.sleep(2)
    sys.exit(1)'

cat > "$W/config.ini" <<EOF
[update]
repo_url = file://$W/remote.git
ref = release
app_dir = $APP
unit = $UNIT
unit_installed = /run/dash-selftest-unit/none
unit_in_tree = systemd/none
required = dashpanel/__main__.py,dashpanel/app.py
state_dir = $W/state
health_seconds = 8
rollback_health_seconds = 5
poll_seconds = 0.5
EOF
export DASH_UPDATE_CONFIG="$W/config.ini"
ver() { sed -n 's/^VERSION = "\(.*\)"/\1/p' "$APP/dashpanel/app.py" 2>/dev/null; }

echo "1. första installationen (bra version v1)"
mkver v1 "${GOOD//NAMN/v1}"
"$DU" apply >"$W/o1" 2>&1; rc=$?
[ $rc = 0 ] && [ "$(ver)" = v1 ] && systemctl is-active --quiet "$UNIT" && ok "v1 installerad och uppe" || { bad "v1 (rc=$rc, version '$(ver)')"; cat "$W/o1"; }

echo "2. uppdatering till v2"
mkver v2 "${GOOD//NAMN/v2}"
"$DU" apply >"$W/o2" 2>&1; rc=$?
[ $rc = 0 ] && [ "$(ver)" = v2 ] && systemctl is-active --quiet "$UNIT" && ok "v2 installerad och uppe" || { bad "v2 (rc=$rc, version '$(ver)')"; cat "$W/o2"; }

echo "2b. manuell rollback tur och retur"
"$DU" rollback >"$W/o2b" 2>&1; rc=$?
[ $rc = 0 ] && [ "$(ver)" = v1 ] && ok "rollback gav v1" || { bad "rollback (rc=$rc, version '$(ver)')"; cat "$W/o2b"; }
"$DU" rollback >"$W/o2c" 2>&1; rc=$?
[ $rc = 0 ] && [ "$(ver)" = v2 ] && systemctl is-active --quiet "$UNIT" && ok "rollback igen gav v2, tjänsten uppe" || { bad "rollback 2 (rc=$rc, version '$(ver)')"; cat "$W/o2c"; }

echo "3. kraschande version v3 ska återställas till v2"
mkver v3 "${CRASH//NAMN/v3}"
"$DU" apply >"$W/o3" 2>&1; rc=$?
sleep 2
[ $rc = 2 ] && [ "$(ver)" = v2 ] && systemctl is-active --quiet "$UNIT" && ok "återställd till v2, tjänsten uppe (avslutskod 2)" || { bad "v3 (rc=$rc, version '$(ver)')"; cat "$W/o3"; }
[ -d "$APP.failed" ] && ok "misslyckade versionen sparad som .failed" || bad ".failed saknas"
"$DU" status --json | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if len(d['bad'])==1 else 1)" && ok "v3 märkt som dålig" || bad "v3 inte märkt dålig"

echo "4. syntaxfel avvisas före bytet"
mkver v4 "def trasig(:"
"$DU" apply >"$W/o4" 2>&1; rc=$?
[ $rc = 1 ] && [ "$(ver)" = v2 ] && ok "v4 avvisad, v2 kvar (avslutskod 1)" || { bad "v4 (rc=$rc, version '$(ver)')"; cat "$W/o4"; }

cleanup
systemctl is-active --quiet dash-panel && ok "dash-panel orörd och uppe" || echo "  (dash-panel körs inte här; inget som provet rört)"
[ $FAIL = 0 ] && echo "ALLT OK" || echo "NÅGOT FEL"
exit $FAIL
