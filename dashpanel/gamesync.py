"""Hämtar spelen från GitHub (knappen Uppdatera spel i spelväljaren).

Spelen är filer i mappen games/ i GitHub-repot. Knappen hämtar den mappen (inget annat) och lägger filerna i spelmappen på
enheten (standard /var/lib/dash-panel/games/). Panelens egen kod uppdateras inte av det här, och den vanliga knappen
Uppdatera rör inte spelen: games/ ligger utanför det dash-update installerar (.gitattributes: export-ignore).

Två delar:
 - GameSync: det panelen använder. Startar hämtningen som en egen tillfällig systemd-tjänst (som knappen Uppdatera gör, så
   att git inte räknas in i panelens minnesgräns) och läser resultatet.
 - sync() och main(): det som körs i den tjänsten (python3 -m dashpanel.gamesync). Läser samma /etc/dash-update/config.ini
   som dash-update (repo_url, key, known_hosts), hämtar grenen games_ref (standard main) grunt med den skrivskyddade
   deploy keyn, kontrollerar varje spelfil och lägger dem på plats en i taget (atomiskt).

Regler för vad som händer med filerna:
 - nya och ändrade filer installeras, men bara om de klarar kontrollen (samma som spelväljaren gör: syntax, META, skyddsräcket).
   En fil som inte gör det hoppas över och rapporteras; en äldre fungerande version ligger då kvar;
 - spel som togs bort ur repot tas bort från enheten, men bara sådana som den här hämtningen själv lagt dit (de står i
   games-sync.json). Filer som lagts dit på annat sätt rörs aldrig;
 - ingen grens `games/`-mapp alls (fel gren, eller mappen borttagen) räknas som fel: då tas inget bort;
 - sparade resultat och rekord (game-data/) rörs aldrig, så ett spel som läggs tillbaka har kvar sina.
"""
import argparse
import asyncio
import configparser
import datetime
import fcntl
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time

from . import gamelib

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CONF_PATH = os.environ.get('DASH_UPDATE_CONFIG', '/etc/dash-update/config.ini')
UNIT = 'dash-games-sync'
RUN_DIR = '/run'
START_TIMEOUT = 15.0            # så länge systemd-run får ta på sig att starta tjänsten
RUN_TIMEOUT = 200.0             # så länge panelen väntar på resultatet (sekunder)
FETCH_TIMEOUT = 120             # så länge git får ta på sig att hämta
PREFIX = 'games/'

# samma värden och nycklar som dash-update (update/dash-update); games_ref är nytt
DEFAULTS = {
    'repo_url': 'https://github.com/blobba79/simple_ha_dash.git',
    'games_ref': 'main',
    'state_dir': '/var/lib/dash-update',
    'key': '/etc/dash-update/deploy_key',
    'known_hosts': '/etc/dash-update/known_hosts',
    'git': 'git',
}

RC_OK, RC_ERR, RC_BUSY = 0, 1, 3


class SyncError(Exception):
    def __init__(self, msg, code=RC_ERR):
        Exception.__init__(self, msg)
        self.code = code


# ================================================================ det som körs i tjänsten
def read_conf(path=None):
    d = dict(DEFAULTS)
    path = path or CONF_PATH
    cp = configparser.ConfigParser(interpolation=None)
    if os.path.exists(path):
        cp.read(path, encoding='utf-8')
        if cp.has_section('update'):
            d.update({k: v.strip() for k, v in cp.items('update') if v.strip()})
    return d


def _env(c):
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['LC_ALL'] = 'C'
    if c['repo_url'].startswith(('git@', 'ssh://')):
        if not os.path.exists(c['key']):
            raise SyncError('deploy key saknas (%s)' % c['key'])
        env['GIT_SSH_COMMAND'] = ' '.join([
            'ssh', '-i', shlex.quote(c['key']), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + shlex.quote(c['known_hosts']),
            '-o', 'ConnectTimeout=15'])
    return env


def _git(c, cache, *args, timeout=60):
    cmd = [c['git'], '--git-dir', cache] + list(args)
    try:
        p = subprocess.run(cmd, env=_env(c), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SyncError('git tog för lång tid (%s)' % args[0])
    except FileNotFoundError:
        raise SyncError('programmet %s finns inte' % c['git'])
    if p.returncode != 0:
        err = (p.stderr or p.stdout).decode('utf-8', 'replace').strip()
        raise SyncError('git %s misslyckades: %s' % (args[0], err[-300:] or 'okänt fel'))
    return p.stdout


def fetch_listing(c, log=print):
    """Hämtar grenen games_ref grunt till en egen cache och ger (commit, [(namn, oid, storlek, läge)]) för filerna direkt
    i games/."""
    cache = os.path.join(c['state_dir'], 'games.git')
    os.makedirs(c['state_dir'], mode=0o700, exist_ok=True)
    if not os.path.isdir(cache):
        try:
            subprocess.run([c['git'], 'init', '--bare', '-q', cache], env=_env(c), capture_output=True, check=True,
                           timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            raise SyncError('kunde inte skapa git-cachen: %s' % e)
    ref = c['games_ref']
    ref = ref if ref.startswith('refs/') else 'refs/heads/' + ref
    log('hämtar %s från %s' % (ref, c['repo_url']))
    _git(c, cache, 'fetch', '-q', '--depth', '1', '--no-tags', c['repo_url'], ref, timeout=FETCH_TIMEOUT)
    sha = _git(c, cache, 'rev-parse', 'FETCH_HEAD^{commit}').decode().strip()
    raw = _git(c, cache, 'ls-tree', '-z', '-l', sha, '--', PREFIX)
    out = []
    for rec in raw.split(b'\0'):
        if not rec:
            continue
        meta, _, path = rec.partition(b'\t')
        parts = meta.split()
        if len(parts) < 4:
            continue
        mode, typ, oid, size = (p.decode() for p in parts[:4])
        name = path.decode('utf-8', 'replace')
        if not name.startswith(PREFIX) or '/' in name[len(PREFIX):]:
            continue                                   # undermappar hör inte till spelen
        out.append((name[len(PREFIX):], oid, int(size) if size.isdigit() else -1, mode, typ))
    return sha, out, cache


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _write_atomic(path, data, mode=0o644):
    tmp = os.path.join(os.path.dirname(path), '.' + os.path.basename(path) + '.tmp')
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def _load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def sync(games_dir, manifest_path, c, log=print, legacy_root=gamelib.LEGACY_ROOT):
    """Hämtar spelen och lägger dem i games_dir. Ger ett resultat (dict) och kastar SyncError vid fel som gör att inget
    ändras. Resultat: ok, commit, added, updated, removed, unchanged (antal) och skipped (lista med [fil, orsak])."""
    sha, entries, cache = fetch_listing(c, log)
    if not entries:
        raise SyncError('mappen games/ finns inte på grenen %s (eller är tom)' % c['games_ref'])
    os.makedirs(games_dir, exist_ok=True)
    manifest = _load_json(manifest_path)
    mine = manifest.get('files') if isinstance(manifest.get('files'), dict) else {}
    added, updated, removed, skipped = [], [], [], []
    unchanged = 0
    in_repo = set()
    taken = 0
    for name, oid, size, mode, typ in sorted(entries):
        if not name.endswith('.py'):
            continue                                   # README.md, SKAPA-SPEL.md och annat som inte är spel
        stem = name[:-3]
        in_repo.add(name)
        if not gamelib.FILE_RE.match(name):
            skipped.append([name, 'filnamnet måste vara a-z, 0-9, _ och - (2-32 tecken) och sluta på .py'])
            continue
        if typ != 'blob' or mode not in ('100644', '100755'):
            skipped.append([name, 'inte en vanlig fil'])
            continue
        if size > gamelib.MAX_SOURCE:
            skipped.append([name, 'filen är för stor'])
            continue
        if taken >= gamelib.MAX_GAMES:
            skipped.append([name, 'för många spel (högst %d)' % gamelib.MAX_GAMES])
            continue
        data = _git(c, cache, 'cat-file', 'blob', oid, timeout=60)
        try:
            source = data.decode('utf-8')
        except UnicodeDecodeError:
            skipped.append([name, 'filen är inte UTF-8-text'])
            continue
        _tree, _meta, errs = gamelib.static_check(source, stem, legacy_root)
        if errs:
            skipped.append([name, errs[0]])
            continue
        taken += 1
        path = os.path.join(games_dir, name)
        try:
            with open(path, 'rb') as f:
                have = f.read()
        except OSError:
            have = None
        if have == data:
            unchanged += 1
        else:
            _write_atomic(path, data)
            (updated if have is not None else added).append(stem)
        mine[name] = _sha(data)
    for name in sorted(list(mine)):
        if name not in in_repo:                         # borttaget ur repot: bort från enheten (bara det vi lagt dit)
            try:
                os.unlink(os.path.join(games_dir, name))
            except FileNotFoundError:
                pass
            except OSError as e:
                skipped.append([name, 'kunde inte tas bort: %s' % e])
                continue
            removed.append(name[:-3])
            del mine[name]
    try:
        _write_atomic(manifest_path, json.dumps({
            'commit': sha, 'time': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'files': mine}, indent=1).encode('utf-8'), 0o600)
    except OSError as e:
        log('kunde inte skriva %s: %s' % (manifest_path, e))
    return {'ok': True, 'commit': sha, 'added': added, 'updated': updated, 'removed': removed,
            'unchanged': unchanged, 'skipped': skipped}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Hämtar spelen från GitHub (körs av knappen Uppdatera spel)')
    ap.add_argument('--games-dir', default=gamelib.GAMES_DIR)
    ap.add_argument('--manifest', default=None)
    ap.add_argument('--out', default=None, help='skriv resultatet (JSON) hit')
    ap.add_argument('--config', default=None)
    ap.add_argument('--legacy-root', default=gamelib.LEGACY_ROOT)
    args = ap.parse_args(argv)
    manifest = args.manifest or os.path.join(os.path.dirname(args.games_dir.rstrip('/')), 'games-sync.json')
    c = read_conf(args.config)

    def log(msg):
        print(time.strftime('%H:%M:%S ') + msg, flush=True)

    code = RC_OK
    lock = None
    try:
        os.makedirs(c['state_dir'], mode=0o700, exist_ok=True)
        lock = open(os.path.join(c['state_dir'], 'games.lock'), 'w')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SyncError('en hämtning pågår redan', RC_BUSY)
        res = sync(args.games_dir, manifest, c, log, args.legacy_root)
        log('klart: %d nya, %d uppdaterade, %d borttagna, %d oförändrade, %d överhoppade (%s)' % (
            len(res['added']), len(res['updated']), len(res['removed']), res['unchanged'], len(res['skipped']),
            res['commit'][:7]))
        for name, why in res['skipped']:
            log('hoppade över %s: %s' % (name, why))
    except SyncError as e:
        res = {'ok': False, 'error': str(e)}
        code = e.code
        log('FEL: %s' % e)
    except Exception as e:                              # allt annat: ett läsbart fel, inte en traceback i rutan
        res = {'ok': False, 'error': '%s: %s' % (type(e).__name__, e)}
        code = RC_ERR
        log('FEL: %s' % res['error'])
    finally:
        if lock is not None:
            lock.close()
    if args.out:
        try:
            _write_atomic(args.out, json.dumps(res).encode('utf-8'), 0o644)
        except OSError as e:
            log('kunde inte skriva resultatet: %s' % e)
    return code


# ================================================================ det panelen använder
def summary(res):
    """Resultatet som (text, art) för spelväljaren: art är ok, same, warn eller fail."""
    if not isinstance(res, dict) or not res.get('ok'):
        why = (res or {}).get('error') if isinstance(res, dict) else None
        return 'Det gick inte: %s' % (why or 'okänt fel'), 'fail'
    parts = []
    for key, one, many in (('added', 'nytt', 'nya'), ('updated', 'uppdaterat', 'uppdaterade'),
                           ('removed', 'borttaget', 'borttagna')):
        n = len(res.get(key) or [])
        if n:
            parts.append('%d %s' % (n, one if n == 1 else many))
    skipped = res.get('skipped') or []
    text = ('Klart: ' + ', '.join(parts) + '.') if parts else 'Spelen är redan aktuella.'
    kind = 'ok' if parts else 'same'
    if skipped:
        names = ', '.join(s[0] for s in skipped[:2]) + (' m.fl.' if len(skipped) > 2 else '')
        text += ' %d %s över (%s).' % (len(skipped), 'fil hoppades' if len(skipped) == 1 else 'filer hoppades', names)
        kind = 'warn'
    return text, kind


class GameSync(object):
    """Startar hämtningen som egen tillfällig tjänst och läser resultatet. Sökvägarna går att byta (prov)."""

    def __init__(self, games_dir=gamelib.GAMES_DIR, app_dir=APP_DIR, run_dir=RUN_DIR, systemd_run='systemd-run',
                 unit=UNIT, python=None, config=None, manifest=None, legacy_root=gamelib.LEGACY_ROOT):
        self.games_dir = games_dir
        self.app_dir = app_dir
        self.run_dir = run_dir
        self.systemd_run = systemd_run
        self.unit = unit
        self.python = python or sys.executable or 'python3'
        self.config = config
        self.manifest = manifest
        self.legacy_root = legacy_root

    @property
    def rc_file(self):
        return os.path.join(self.run_dir, '%s.rc' % self.unit)

    @property
    def log_file(self):
        return os.path.join(self.run_dir, '%s.log' % self.unit)

    @property
    def out_file(self):
        return os.path.join(self.run_dir, '%s.json' % self.unit)

    def available(self):
        if not self.games_dir:
            return False
        if os.path.isabs(self.systemd_run):
            return os.path.isfile(self.systemd_run)
        return _which(self.systemd_run)

    def clear(self):
        for p in (self.rc_file, self.log_file, self.out_file):
            try:
                os.unlink(p)
            except OSError:
                pass

    async def start(self):
        """Startar hämtningen. Ger (läge, text): started, busy (en hämtning pågår redan), missing eller error."""
        if not self.available():
            return 'missing', 'Det går inte att hämta spel från den här enheten.'
        self.clear()
        script = ('app="$1"; rc="$2"; log="$3"; shift 3; '
                  'cd "$app" && "$@" >"$log" 2>&1; echo $? >"$rc.tmp"; mv "$rc.tmp" "$rc"')
        worker = [self.python, '-m', 'dashpanel.gamesync', '--games-dir', self.games_dir, '--out', self.out_file,
                  '--legacy-root', self.legacy_root]
        if self.config:
            worker += ['--config', self.config]
        if self.manifest:
            worker += ['--manifest', self.manifest]
        cmd = [self.systemd_run, '--quiet', '--collect', '--no-block', '--unit=%s' % self.unit,
               '--description=Hämtar spel från GitHub (knappen Uppdatera spel)',
               '/bin/sh', '-c', script, 'sh', self.app_dir, self.rc_file, self.log_file] + worker
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
                return 'error', 'Det tog för lång tid att starta hämtningen.'
        except OSError as e:
            return 'error', 'Kunde inte starta hämtningen (%s).' % e
        if proc.returncode != 0:
            msg = (err or b'').decode('utf-8', 'replace').strip()
            if 'already' in msg.lower() or 'finns redan' in msg.lower():
                return 'busy', 'En hämtning pågår redan.'
            return 'error', ('Kunde inte starta hämtningen: %s' % msg[:100]) if msg else 'Kunde inte starta hämtningen.'
        return 'started', ''

    def finished(self):
        """Avslutskoden när hämtningen är klar, annars None."""
        try:
            with open(self.rc_file, encoding='ascii') as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def outcome(self, rc):
        """Resultatet som (text, art) för avslutskoden rc."""
        res = _load_json(self.out_file)
        if res:
            return summary(res)
        if rc == RC_BUSY:
            return 'En hämtning pågår redan.', 'fail'
        try:
            with open(self.log_file, encoding='utf-8', errors='replace') as f:
                last = [ln.strip() for ln in f.read().splitlines() if ln.strip()][-1]
        except (OSError, IndexError):
            last = ''
        return 'Det gick inte (avslutskod %s)%s' % (rc, ': ' + last[:100] if last else '.'), 'fail'

    def timeout_outcome(self):
        return 'Hämtningen tog för lång tid.', 'fail'


def _which(name):
    for d in os.environ.get('PATH', '').split(os.pathsep):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return True
    return False


if __name__ == '__main__':
    sys.exit(main())
