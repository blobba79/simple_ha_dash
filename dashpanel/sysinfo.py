"""Skrivskyddad systeminfo (Wi-Fi-styrka) och omstart/avstängning/avslut för panelen. Ändrar inget i nät eller Wi-Fi."""
import asyncio

WIRELESS = '/proc/net/wireless'
DEFAULT_UNIT = 'dash-panel.service'
# {unit} byts mot tjänsten panelen själv kör i (own_unit)
POWER_CMDS = {'reboot': ['systemctl', 'reboot'],
              'poweroff': ['systemctl', 'poweroff'],
              'quit': ['systemctl', 'stop', '--no-block', '{unit}']}
POWER_TIMEOUT = 15.0


def wifi_dbm(path=WIRELESS):
    """Signalstyrka i dBm för första Wi-Fi-gränssnittet i /proc/net/wireless. None om det saknas, inte är
    anslutet eller nivån är okänd (0 eller utanför det rimliga)."""
    try:
        with open(path, encoding='ascii', errors='replace') as f:
            lines = f.read().splitlines()[2:]
    except OSError:
        return None
    for ln in lines:
        if ':' not in ln:
            continue
        parts = ln.split(':', 1)[1].split()          # status, link, level, noise, ...
        if len(parts) < 3:
            continue
        try:
            v = float(parts[2].rstrip('.'))
        except ValueError:
            continue
        if -120.0 <= v < 0.0:
            return v
    return None


def dbm_to_percent(dbm):
    """Samma tumregel som de flesta mobiler och datorer: -100 dBm = 0 %, -50 dBm eller bättre = 100 %.
    Visas som 1-100."""
    return max(1, min(100, int(round(2 * (dbm + 100.0)))))


class WifiMeter(object):
    """Läser signalstyrkan och jämnar ut den lite (annars hoppar siffran vid varje läsning)."""

    def __init__(self, read=wifi_dbm, alpha=0.5):
        self.read = read
        self.alpha = alpha
        self.avg = None

    def percent(self):
        v = self.read()
        if v is None:
            self.avg = None
            return None
        self.avg = v if self.avg is None else self.avg + self.alpha * (v - self.avg)
        return dbm_to_percent(self.avg)


def own_unit(cgroup='/proc/self/cgroup', default=DEFAULT_UNIT):
    """Namnet på systemd-tjänsten som den här processen kör i (ur cgroup-sökvägen), annars dash-panel.service.
    Så stoppar "Avsluta" rätt tjänst även när panelen körs som en tillfällig provtjänst."""
    try:
        with open(cgroup, encoding='ascii', errors='replace') as f:
            lines = f.read().splitlines()
    except OSError:
        return default
    for ln in lines:
        path = ln.split(':', 2)[-1]
        for part in reversed(path.split('/')):
            if part.endswith('.service') and len(part) > len('.service') and '@' not in part:
                return part
    return default


def power_command(kind, unit=None):
    """Kommandoraden för omstart/avstängning/avslut, eller None för okänd typ."""
    cmd = POWER_CMDS.get(kind)
    if not cmd:
        return None
    if any('{unit}' in a for a in cmd):
        u = unit or own_unit()
        return [a.replace('{unit}', u) for a in cmd]
    return list(cmd)


async def run_power(kind, log=None, unit=None):
    """Ber systemd starta om, stänga av eller (kind 'quit') stoppa panelens egen tjänst: vanlig, ren hantering, inte
    --force. True om kommandot togs emot."""
    cmd = power_command(kind, unit)
    if not cmd:
        return False
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                    stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), POWER_TIMEOUT)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            if log:
                log('%s tog för lång tid, avbröt' % ' '.join(cmd))
            return False
    except OSError as e:
        if log:
            log('kunde inte köra %s: %s' % (' '.join(cmd), e))
        return False
    if proc.returncode is not None and proc.returncode < 0 and kind == 'quit':
        return True         # dödad av en signal medan tjänsten stoppades: stoppet är redan igång
    if proc.returncode != 0:
        if log:
            log('%s misslyckades (%s): %s' % (' '.join(cmd), proc.returncode, (err or b'').decode('utf-8', 'replace').strip()[:200]))
        return False
    return True
