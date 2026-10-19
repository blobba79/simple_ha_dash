"""Manuell uppdatering från panelens inställningssida (knappen Uppdatera).

Knappen kör `dash-update apply` (uppdateraren som hämtar panelen från GitHub, se update/README.md) som en egen
tillfällig systemd-tjänst. Den lever därför kvar när uppdateraren startar om panelen mitt i uppdateringen. Resultatet
läses ur en fil som tjänsten skriver sist (avslutskoden) och ur uppdaterarens logg. Panelen minns i en liten fil
(`update.json`) att en uppdatering pågår, så att den nystartade panelen kan visa hur det gick.

Uppdateraren själv (timer, auto_apply, kontroller, återställning) rörs inte: allt det gäller som förut. Den här
modulen läser bara version och resultat och startar `dash-update apply` när någon trycker på knappen."""
import asyncio
import json
import os
import re
import time

from . import __version__

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
UPDATE_BIN = '/usr/local/sbin/dash-update'
UNIT = 'dash-update-manual'
RUN_DIR = '/run'
MARKER = '/var/lib/dash-panel/update.json'
START_TIMEOUT = 15.0            # så länge systemd-run får ta på sig att starta tjänsten
PENDING_MAX_AGE = 900.0         # en uppdatering som är äldre än så här räknas inte längre som pågående (sekunder)

# avslutskoder från dash-update (update/dash-update)
RC_OK, RC_ERR, RC_ROLLED_BACK, RC_BUSY, RC_CRITICAL, RC_NEEDS_OK, RC_DRIFT = 0, 1, 2, 3, 4, 5, 6

SEARCH_TITLE = 'Söker efter ny version …'
SEARCH_SUB = 'Finns en ny version installeras den och panelen startar om av sig själv.'
FAIL_TITLE = 'Det gick inte att uppdatera'


def read_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def version_label(info, long=False):
    """"Version 1.1 · 9efc105" (med long också datumet). info är VERSION.json från dash-update; saknas den visas bara
    versionsnumret (en panel som inte installerats med dash-update, till exempel i en provmiljö)."""
    parts = ['Version %s' % __version__]
    short = (info or {}).get('short') or ((info or {}).get('commit') or '')[:12]
    if short:
        parts.append(short[:7])
    date = ((info or {}).get('date') or '')[:10]
    if long and date:
        parts.append(date)
    return ' · '.join(parts)


def last_error_line(log_text):
    """Sista raden som säger vad som gick fel (FEL:, NEKAD:, avvisad ...), utan klockslag. None om ingen."""
    best = None
    for ln in (log_text or '').splitlines():
        ln = re.sub(r'^\d\d:\d\d:\d\d\s+', '', ln.strip())
        if re.match(r'(FEL:|NEKAD:|KRITISKT:|MISSLYCKAD|avvisad)', ln):
            best = ln
    if best is None:
        return None
    best = re.sub(r'^(FEL|NEKAD|KRITISKT):\s*', '', best)
    return best[:160]


class Updater(object):
    """Allt panelen behöver för knappen Uppdatera. Sökvägarna går att byta (prov); update_bin None = ingen uppdaterare."""

    def __init__(self, app_dir=APP_DIR, update_bin=UPDATE_BIN, run_dir=RUN_DIR, marker=MARKER,
                 systemd_run='systemd-run', unit=UNIT, now=time.time):
        self.app_dir = app_dir
        self.update_bin = update_bin
        self.run_dir = run_dir
        self.marker = marker if marker not in ('', 'none') else None
        self.systemd_run = systemd_run
        self.unit = unit
        self.now = now
        self._info = None

    # ------------------------------------------------------------ version
    @property
    def rc_file(self):
        return os.path.join(self.run_dir, '%s.rc' % self.unit)

    @property
    def log_file(self):
        return os.path.join(self.run_dir, '%s.log' % self.unit)

    def info(self):
        """Installerad version (VERSION.json), läses en gång: ändras bara när panelen startas om."""
        if self._info is None:
            self._info = read_json(os.path.join(self.app_dir, 'VERSION.json'), {}) or {}
        return self._info

    def reload(self):
        self._info = None

    def version_text(self, long=False):
        return version_label(self.info(), long)

    def available(self):
        return bool(self.update_bin) and os.path.isfile(self.update_bin)

    # ------------------------------------------------------------ pågående uppdatering
    def _remove(self, *paths):
        for p in paths:
            if not p:
                continue
            try:
                os.unlink(p)
            except OSError:
                pass

    def _write_marker(self):
        if not self.marker:
            return
        data = {'from': self.info().get('commit'), 'started': self.now()}
        try:
            os.makedirs(os.path.dirname(self.marker), exist_ok=True)
            tmp = self.marker + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.marker)
        except OSError:
            pass

    def pending(self):
        """Markeringen om en uppdatering som den här panelen startat och inte visat resultatet av, annars None."""
        if not self.marker:
            return None
        d = read_json(self.marker)
        if not isinstance(d, dict) or not isinstance(d.get('started'), (int, float)):
            if os.path.exists(self.marker):         # finns men är trasig: städa så att den inte väcker frågan igen
                self._remove(self.marker)
            return None
        if not (0 <= self.now() - d['started'] <= PENDING_MAX_AGE):
            self.clear()
            return None
        return d

    def clear(self):
        """Resultatet är visat: glöm markeringen och spåren efter körningen."""
        self._remove(self.marker, self.rc_file, self.log_file)

    async def start(self):
        """Startar `dash-update apply` som egen tjänst. Ger (läge, text): started, busy (en körning pågår redan),
        missing (ingen uppdaterare) eller error."""
        if not self.available():
            return 'missing', 'Uppdateraren (dash-update) finns inte på den här enheten.'
        self._remove(self.rc_file, self.log_file)
        self._write_marker()
        script = ('rc="$1"; rm -f "$rc"; "$2" apply >"$3" 2>&1; echo $? >"$rc.tmp"; mv "$rc.tmp" "$rc"')
        cmd = [self.systemd_run, '--quiet', '--collect', '--no-block', '--unit=%s' % self.unit,
               '--description=Uppdatering av simple_ha_dash (knappen Uppdatera)',
               '/bin/sh', '-c', script, 'sh', self.rc_file, self.update_bin, self.log_file]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                        stderr=asyncio.subprocess.PIPE)
            try:
                _, err = await asyncio.wait_for(proc.communicate(), START_TIMEOUT)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                self._remove(self.marker)
                return 'error', 'Det tog för lång tid att starta uppdateringen.'
        except OSError as e:
            self._remove(self.marker)
            return 'error', 'Kunde inte starta uppdateringen (%s).' % e
        if proc.returncode != 0:
            msg = (err or b'').decode('utf-8', 'replace').strip()
            if 'already' in msg.lower() or 'finns redan' in msg.lower():
                return 'busy', 'En uppdatering pågår redan.'
            self._remove(self.marker)
            return 'error', ('Kunde inte starta uppdateringen: %s' % msg[:100]) if msg else 'Kunde inte starta uppdateringen.'
        return 'started', ''

    # ------------------------------------------------------------ framsteg och resultat
    def finished(self):
        """Uppdateringens avslutskod när tjänsten är klar, annars None."""
        try:
            with open(self.rc_file, encoding='ascii') as f:
                txt = f.read().strip()
        except OSError:
            return None
        try:
            return int(txt)
        except ValueError:
            return None

    def _log_text(self):
        try:
            with open(self.log_file, encoding='utf-8', errors='replace') as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 8192))
                return f.read()
        except OSError:
            return ''

    def progress(self):
        """Hur långt uppdateringen har kommit enligt loggen: dict med title och sub för skärmen. Först söker den (hämtar
        grenen); när en ny version hittats står dess nummer och datum med."""
        log = self._log_text()
        m = None
        for m in re.finditer(r'ny version: ([0-9a-f]{7,40}) \((\d{4}-\d\d-\d\d)', log):
            pass
        if m:
            return {'title': 'Installerar ny version …',
                    'sub': 'Version %s (%s). Panelen startar om om en stund.' % (m.group(1)[:7], m.group(2))}
        return {'title': SEARCH_TITLE, 'sub': SEARCH_SUB}

    def outcome(self, rc):
        """Resultatet som dict (kind current/ok/rolled/failed, title, sub) för avslutskoden rc."""
        log = self._log_text()
        pend = read_json(self.marker, {}) if self.marker else {}
        before = (pend or {}).get('from')
        self.reload()
        now_commit = self.info().get('commit')
        if rc == RC_OK:
            if now_commit and before and now_commit != before:
                return {'kind': 'ok', 'title': 'Uppdaterad', 'sub': 'Nu körs %s.' % self.version_text(True)}
            if 'hoppar över' in log:
                return {'kind': 'failed', 'title': FAIL_TITLE,
                        'sub': 'Den senaste versionen har tidigare misslyckats på den här enheten och hoppas över.'}
            return {'kind': 'current', 'title': 'Du har senaste versionen', 'sub': self.version_text(True)}
        if rc == RC_ROLLED_BACK:
            return {'kind': 'rolled', 'title': 'Uppdateringen gick inte igenom',
                    'sub': 'Förra versionen lades tillbaka och panelen fungerar som förut.'}
        if rc == RC_BUSY:
            sub = 'En annan uppdatering pågår redan. Försök igen om en stund.'
        elif rc == RC_CRITICAL:
            sub = 'Något gick allvarligt fel. Titta i loggen: journalctl -t dash-update'
        elif rc == RC_NEEDS_OK:
            sub = 'Den nya versionen ändrar tjänstefilen och måste godkännas via ssh (dash-update apply --with-unit).'
        elif rc == RC_DRIFT:
            sub = ('Koden på enheten har ändrats för hand. Lägg in ändringen i GitHub-repot, '
                   'eller kör dash-update apply --force via ssh.')
        else:
            why = last_error_line(log)
            sub = why or 'Okänt fel (avslutskod %s). Titta i loggen: journalctl -t dash-update' % rc
        return {'kind': 'failed', 'title': FAIL_TITLE, 'sub': sub}

    def timeout_outcome(self):
        return {'kind': 'failed', 'title': FAIL_TITLE,
                'sub': 'Uppdateringen tog för lång tid. Titta i loggen: journalctl -t dash-update'}
