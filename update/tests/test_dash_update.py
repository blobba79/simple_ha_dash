#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prov av dash-update mot ett lokalt git-repo och en låtsas-systemctl.

Körs var som helst (ingen dash, ingen GitHub, inget riktigt systemd):
    python3 -m unittest -v update/tests/test_dash_update.py     (från repots rot)
Varje prov bygger sin egen värld i en tillfällig katalog.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
import fcntl

HERE = os.path.dirname(os.path.abspath(__file__))
UPD = os.environ.get('DASH_UPDATE_BIN') or os.path.abspath(os.path.join(HERE, '..', 'dash-update'))

FAKE_SYSTEMCTL = r'''#!/usr/bin/env python3
import sys, os, json, random, time
app = os.environ['FAKE_APP']; st = os.environ['FAKE_STATE']; log = os.environ['FAKE_LOG']
args = sys.argv[1:]
open(log, 'a').write(' '.join(args) + '\n')
def load():
    try: return json.load(open(st))
    except Exception: return {}
def save(d): json.dump(d, open(st, 'w'))
cmd = args[0] if args else ''
if cmd == 'restart':
    try: src = open(app + '/dashpanel/app.py').read()
    except Exception: src = ''
    if 'RESTART_FAILS' in src:
        sys.stderr.write('Job failed\n'); sys.exit(1)
    mode = 'ok'
    for m in ('RUNTIME_CRASH', 'RUNTIME_FLAP', 'RUNTIME_LATE'):
        if m in src: mode = m
    save({'mode': mode, 'pid': random.randint(1000, 60000), 'shows': 0, 't0': time.time()})
elif cmd == 'show':
    s = load(); s['shows'] = s.get('shows', 0) + 1; save(s)
    mode = s.get('mode', 'ok'); pid = s.get('pid', 1)
    a, sub, p, res = 'active', 'running', pid, 'success'
    if mode == 'RUNTIME_CRASH': a, sub, p, res = 'failed', 'failed', 0, 'exit-code'
    elif mode == 'RUNTIME_FLAP': p = pid + s['shows']
    elif mode == 'RUNTIME_LATE' and time.time() - s.get('t0', 0) > 0.5: a, sub, p, res = 'failed', 'failed', 0, 'exit-code'
    vals = {'ActiveState': a, 'SubState': sub, 'MainPID': p, 'Result': res}
    for i, x in enumerate(args):
        if x == '-p': print('%s=%s' % (args[i + 1], vals[args[i + 1]]))
sys.exit(0)
'''

FAKE_ANALYZE = '''#!/usr/bin/env python3
import sys
f = sys.argv[-1]
if 'BAD_UNIT_SYNTAX' in open(f).read():
    sys.stderr.write('Unknown section\\n'); sys.exit(1)
'''


def tree(version, app_extra='', unit='UNIT v1\n', skip=()):
    files = {
        'dashpanel/__init__.py': '',
        'dashpanel/__main__.py': 'from .app import main\nmain()\n',
        'dashpanel/app.py': 'VERSION = %r\n' % version + app_extra,
        'systemd/dash-panel.service': unit,
        'tools/skript.py': '#!/usr/bin/env python3\nprint(1)\n',
    }
    for s in skip:
        files.pop(s, None)
    return files


def slurp(path, mode='r'):
    with open(path, mode) as f:
        return f.read()


class World:
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix='dashupd-')
        r = self.root
        self.remote = os.path.join(r, 'remote.git')
        self.work = os.path.join(r, 'work')
        self.app = os.path.join(r, 'opt', 'dash-panel')
        self.state = os.path.join(r, 'state')
        self.unit = os.path.join(r, 'etc', 'dash-panel.service')
        self.bin = os.path.join(r, 'bin')
        self.log = os.path.join(r, 'systemctl.log')
        self.fstate = os.path.join(r, 'fake-state.json')
        self.conf = os.path.join(r, 'config.ini')
        for d in (self.bin, os.path.dirname(self.app), os.path.dirname(self.unit)):
            os.makedirs(d, exist_ok=True)
        self.gitenv = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t',
                           GIT_COMMITTER_EMAIL='t@t', GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_SYSTEM='/dev/null')
        self.git('init', '-q', '--bare', self.remote, cwd=r)
        self.git('config', 'uploadpack.allowReachableSHA1InWant', 'true', cwd=self.remote)
        os.makedirs(self.work)
        self.git('init', '-q', '-b', 'release', cwd=self.work)
        self.git('remote', 'add', 'origin', 'file://' + self.remote, cwd=self.work)
        for name, body in (('systemctl', FAKE_SYSTEMCTL), ('systemd-analyze', FAKE_ANALYZE)):
            p = os.path.join(self.bin, name)
            with open(p, 'w') as f:
                f.write(body)
            os.chmod(p, 0o755)
        self.write_conf()
        # "Nuvarande dash": en gammal installation utan VERSION.json
        self.put(self.app, tree('v0'))
        with open(self.unit, 'w') as f:
            f.write('UNIT v1\n')

    def write_conf(self, **over):
        d = dict(repo_url='file://' + self.remote, ref='release', app_dir=self.app, state_dir=self.state,
                 unit_installed=self.unit, systemctl=os.path.join(self.bin, 'systemctl'),
                 systemd_analyze=os.path.join(self.bin, 'systemd-analyze'), health_seconds='1',
                 rollback_health_seconds='1', poll_seconds='0.1', key=os.path.join(self.root, 'nokey'),
                 known_hosts=os.path.join(self.root, 'nokh'))
        d.update(over)
        with open(self.conf, 'w') as f:
            f.write('[update]\n' + ''.join('%s = %s\n' % kv for kv in d.items()))

    def git(self, *a, cwd=None):
        p = subprocess.run(['git'] + list(a), cwd=cwd or self.work, env=self.gitenv, capture_output=True, text=True)
        assert p.returncode == 0, (a, p.stderr)
        return p.stdout.strip()

    @staticmethod
    def put(root, files):
        if os.path.isdir(root):
            shutil.rmtree(root)
        for rel, body in files.items():
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w') as f:
                f.write(body)

    def release(self, files, msg='ny version'):
        """Skapa en incheckning och skjut den till grenen release. Returnerar hela sha."""
        for item in os.listdir(self.work):
            if item != '.git':
                p = os.path.join(self.work, item)
                shutil.rmtree(p) if os.path.isdir(p) else os.unlink(p)
        self.put_into(self.work, files)
        self.git('add', '-A')
        self.git('commit', '-q', '-m', msg)
        self.git('push', '-q', '-f', 'origin', 'release')
        return self.git('rev-parse', 'HEAD')

    @staticmethod
    def put_into(root, files):
        for rel, body in files.items():
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w') as f:
                f.write(body)

    def run(self, *args, extra_env=None):
        env = dict(os.environ, DASH_UPDATE_CONFIG=self.conf, FAKE_APP=self.app, FAKE_STATE=self.fstate,
                   FAKE_LOG=self.log, GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_SYSTEM='/dev/null')
        env.update(extra_env or {})
        return subprocess.run([sys.executable, UPD] + list(args), env=env, capture_output=True, text=True, timeout=120)

    def calls(self, word):
        try:
            return sum(1 for ln in slurp(self.log).splitlines() if ln.startswith(word))
        except FileNotFoundError:
            return 0

    def installed(self):
        try:
            return json.loads(slurp(os.path.join(self.app, 'VERSION.json'))).get('commit')
        except Exception:
            return None

    def app_version(self):
        src = slurp(os.path.join(self.app, 'dashpanel', 'app.py'))
        return src.split('\n')[0].split('=')[1].strip().strip("'")

    def status(self):
        return json.loads(slurp(os.path.join(self.state, 'status.json')))

    def bad(self):
        try:
            return [b['commit'] for b in json.loads(slurp(os.path.join(self.state, 'bad.json')))]
        except FileNotFoundError:
            return []

    def snapshot(self):
        out = {}
        for root, _d, files in os.walk(self.app):
            for f in files:
                p = os.path.join(root, f)
                out[os.path.relpath(p, self.app)] = slurp(p, 'rb')
        return out

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class T(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.addCleanup(self.w.cleanup)

    # ------------------------------------------------------------ lyckade vägar
    def test_01_forsta_installation_fran_git(self):
        w = self.w
        sha = w.release(tree('c1'))
        p = w.run('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(w.app_version(), 'c1')
        self.assertEqual(w.installed(), sha)
        self.assertEqual(w.calls('restart'), 1)
        # gamla installationen sparad som .prev
        self.assertTrue(os.path.isdir(w.app + '.prev'))
        self.assertEqual(slurp(os.path.join(w.app + '.prev', 'dashpanel', 'app.py')).split('\n')[0], "VERSION = 'v0'")
        self.assertTrue(w.status()['last_result'].startswith('ok'))
        self.assertFalse(os.path.exists(w.app + '.new'))
        # bara root: inga rättigheter för grupp/övriga
        for root, dirs, files in os.walk(w.app):
            for n in dirs + files:
                m = os.stat(os.path.join(root, n)).st_mode
                self.assertEqual(m & 0o077, 0, os.path.join(root, n))
        # skriptet behåller sin körbara bit för ägaren men README-lika filer inte
        self.assertTrue(os.stat(os.path.join(w.app, 'dashpanel/app.py')).st_mode & stat.S_IRUSR)

    def test_02_check_apply_och_ingen_andring(self):
        w = self.w
        s1 = w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)
        p = w.run('check')
        self.assertEqual(p.returncode, 0)
        self.assertFalse(w.status()['update_available'])
        s2 = w.release(tree('c2'))
        w.run('check')
        self.assertTrue(w.status()['update_available'])
        self.assertEqual(w.status()['latest_commit'], s2)
        # check ändrar inget på panelen
        self.assertEqual(w.installed(), s1)
        self.assertEqual(w.calls('restart'), 1)
        self.assertEqual(w.run('apply').returncode, 0)
        self.assertEqual(w.app_version(), 'c2')
        self.assertEqual(json.loads(slurp(os.path.join(w.app + '.prev', 'VERSION.json')))['commit'], s1)
        self.assertEqual(w.calls('restart'), 2)
        # igen: ingen ändring, ingen omstart
        p = w.run('apply')
        self.assertEqual(p.returncode, 0)
        self.assertIn('redan på senaste', p.stdout)
        self.assertEqual(w.calls('restart'), 2)

    def test_03_dry_run_andrar_inget(self):
        w = self.w
        w.release(tree('c1'))
        before = w.snapshot()
        p = w.run('apply', '--dry-run')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(w.snapshot(), before)
        self.assertEqual(w.calls('restart'), 0)
        self.assertFalse(os.path.exists(w.app + '.new'))
        self.assertFalse(os.path.exists(w.app + '.prev'))

    def test_04_from_dir_utan_git(self):
        w = self.w
        w.write_conf(repo_url='file:///finns/inte')
        d = os.path.join(w.root, 'lokal')
        w.put(d, tree('lokal1'))
        p = w.run('apply', '--from-dir', d)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(w.app_version(), 'lokal1')
        self.assertTrue(w.installed().startswith('lokal-'))

    def test_05_commit_gar_tillbaka_till_aldre(self):
        w = self.w
        s1 = w.release(tree('c1'))
        w.release(tree('c2'))
        self.assertEqual(w.run('apply').returncode, 0)
        self.assertEqual(w.app_version(), 'c2')
        p = w.run('apply', '--commit', s1)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(w.app_version(), 'c1')
        self.assertEqual(w.installed(), s1)

    def test_06_manuell_rollback_byter_plats(self):
        w = self.w
        s1 = w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)
        s2 = w.release(tree('c2'))
        self.assertEqual(w.run('apply').returncode, 0)
        self.assertEqual(w.run('rollback').returncode, 0)
        self.assertEqual(w.installed(), s1)
        self.assertEqual(w.run('rollback').returncode, 0)
        self.assertEqual(w.installed(), s2)

    # ------------------------------------------------------------ avvisas före bytet
    def _rejected(self, files, word):
        w = self.w
        good = w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)
        before, restarts = w.snapshot(), w.calls('restart')
        bad = w.release(files)
        p = w.run('apply')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn(word, p.stdout)
        self.assertEqual(w.snapshot(), before, 'körande version får inte röras')
        self.assertEqual(w.calls('restart'), restarts, 'ingen omstart av en avvisad version')
        self.assertFalse(os.path.exists(w.app + '.new'))
        self.assertEqual(w.bad(), [bad])
        self.assertEqual(w.installed(), good)
        # försöks inte igen, och check säger inte "ny version"
        p = w.run('apply')
        self.assertEqual(p.returncode, 0)
        self.assertIn('hoppar över', p.stdout)
        w.run('check')
        self.assertFalse(w.status()['update_available'])
        self.assertTrue(w.status()['latest_is_bad'])
        # en ny, bra version tas emot som vanligt
        w.release(tree('c3'))
        self.assertEqual(w.run('apply').returncode, 0)
        self.assertEqual(w.app_version(), 'c3')

    def test_10_syntaxfel_avvisas(self):
        self._rejected(tree('c2', app_extra='def trasig(:\n    pass\n'), 'syntaxfel')

    def test_11_importfel_avvisas(self):
        self._rejected(tree('c2', app_extra='import finns_inte_alls_xyz\n'), 'import av')

    def test_12_saknad_fil_avvisas(self):
        self._rejected(tree('c2', skip=('dashpanel/__main__.py',)), 'saknas')

    def test_13_trasig_tjanstefil_avvisas(self):
        w = self.w
        w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)
        before = w.snapshot()
        w.release(tree('c2', unit='UNIT BAD_UNIT_SYNTAX\n'))
        p = w.run('apply', '--with-unit')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertEqual(w.snapshot(), before)
        self.assertEqual(slurp(w.unit), 'UNIT v1\n')

    # ------------------------------------------------------------ fel efter bytet: återställning
    def _rolls_back(self, marker):
        w = self.w
        good = w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)
        restarts = w.calls('restart')
        bad = w.release(tree('c2', app_extra='# %s\n' % marker))
        p = w.run('apply')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(w.app_version(), 'c1')
        self.assertEqual(w.installed(), good)
        self.assertEqual(w.bad(), [bad])
        self.assertEqual(w.calls('restart'), restarts + 2, 'en omstart till nya, en tillbaka')
        self.assertTrue(os.path.isdir(w.app + '.failed'), 'misslyckade versionen sparas för felsökning')
        self.assertIn('återställd', w.status()['last_result'])
        # tjänsten är frisk igen efter återställningen (sista show ser den gamla versionen)
        self.assertEqual(w.run('status', '--json').returncode, 0)
        # och samma version försöks inte igen
        p = w.run('apply')
        self.assertIn('hoppar över', p.stdout)
        self.assertEqual(w.calls('restart'), restarts + 2)

    def test_20_krasch_efter_bytet(self):
        self._rolls_back('RUNTIME_CRASH')

    def test_21_tjansten_startar_om_hela_tiden(self):
        self._rolls_back('RUNTIME_FLAP')

    def test_22_sen_krasch(self):
        self._rolls_back('RUNTIME_LATE')

    def test_23_omstartskommandot_misslyckas(self):
        self._rolls_back('RESTART_FAILS')

    # ------------------------------------------------------------ tjänstefilen
    def test_30_andrad_tjanstefil_kraver_godkannande(self):
        w = self.w
        w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)
        before, restarts = w.snapshot(), w.calls('restart')
        v2 = w.release(tree('c2', unit='UNIT v2\n'))
        p = w.run('apply')
        self.assertEqual(p.returncode, 5, p.stdout + p.stderr)
        self.assertEqual(w.snapshot(), before)
        self.assertEqual(w.calls('restart'), restarts)
        self.assertEqual(slurp(w.unit), 'UNIT v1\n')
        self.assertEqual(w.bad(), [], 'väntar på godkännande är inte ett fel')
        self.assertTrue(w.status()['last_result'].startswith('kräver godkännande'))
        # med godkännande
        p = w.run('apply', '--with-unit')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(slurp(w.unit), 'UNIT v2\n')
        self.assertEqual(w.installed(), v2)
        self.assertGreaterEqual(w.calls('daemon-reload'), 1)

    def test_31_tjanstefil_aterstalls_vid_misslyckande(self):
        w = self.w
        w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)
        w.release(tree('c2', unit='UNIT v2\n', app_extra='# RUNTIME_CRASH\n'))
        reloads = w.calls('daemon-reload')
        p = w.run('apply', '--with-unit')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(slurp(w.unit), 'UNIT v1\n', 'gamla tjänstefilen ska tillbaka')
        self.assertEqual(w.app_version(), 'c1')
        self.assertGreaterEqual(w.calls('daemon-reload'), reloads + 2)

    # ------------------------------------------------------------ lokala ändringar
    def test_45_lokala_andringar_nekas_utan_force(self):
        w = self.w
        w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)
        # någon lägger ut kod på annat sätt (tgz, handredigering)
        pth = os.path.join(w.app, 'dashpanel', 'app.py')
        with open(pth, 'a') as f:
            f.write('# handändring\n')
        before, restarts = w.snapshot(), w.calls('restart')
        w.release(tree('c2'))
        p = w.run('apply')
        self.assertEqual(p.returncode, 6, p.stdout + p.stderr)
        self.assertIn('NEKAD', p.stdout)
        self.assertEqual(w.snapshot(), before, 'den lokala ändringen får inte skrivas över')
        self.assertEqual(w.calls('restart'), restarts)
        self.assertTrue(json.loads(w.run('status', '--json').stdout)['local_changes'])
        self.assertIn('Lokala ändringar: JA', w.run('status').stdout)
        # med --force skrivs den över
        p = w.run('apply', '--force')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(w.app_version(), 'c2')
        self.assertFalse(json.loads(w.run('status', '--json').stdout)['local_changes'])

    def test_46_pycache_och_versionsfiler_ar_inga_lokala_andringar(self):
        w = self.w
        w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)
        os.makedirs(os.path.join(w.app, 'dashpanel', '__pycache__'))
        with open(os.path.join(w.app, 'dashpanel', '__pycache__', 'app.cpython-311.pyc'), 'wb') as f:
            f.write(b'\0\1\2')
        with open(os.path.join(w.app, 'dashpanel', 'skraeppyc.pyc'), 'wb') as f:
            f.write(b'\3')
        meta = os.path.join(w.app, 'VERSION.json')
        d = json.loads(slurp(meta))
        d['subject'] = 'ändrad text'
        with open(meta, 'w') as f:
            json.dump(d, f)
        self.assertFalse(json.loads(w.run('status', '--json').stdout)['local_changes'])
        w.release(tree('c2'))
        p = w.run('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(w.app_version(), 'c2')

    def test_47_gammal_installation_utan_versionsfil_nekas_inte(self):
        # som dash före första uppdateringen: ingen VERSION.json, alltså inget att jämföra med
        w = self.w
        self.assertIsNone(w.installed())
        w.release(tree('c1'))
        self.assertEqual(w.run('apply').returncode, 0)


    # ------------------------------------------------------------ övrigt
    def test_40_lasning_hindrar_parallell_korning(self):
        w = self.w
        w.release(tree('c1'))
        os.makedirs(w.state, exist_ok=True)
        f = open(os.path.join(w.state, 'lock'), 'w')
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            p = w.run('apply')
            self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        finally:
            f.close()
        self.assertEqual(w.run('apply').returncode, 0)

    def test_41_onåbar_kalla_ändrar_inget(self):
        w = self.w
        w.write_conf(repo_url='file:///finns/inte')
        before = w.snapshot()
        p = w.run('apply')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertEqual(w.snapshot(), before)
        self.assertEqual(w.bad(), [], 'ett nätfel är inte en dålig version')
        p = w.run('check')
        self.assertEqual(p.returncode, 1)
        self.assertTrue(w.status()['error'])

    def test_42_ssh_utan_nyckel_ger_tydligt_fel(self):
        w = self.w
        w.write_conf(repo_url='git@github.com:x/y.git')
        p = w.run('check')
        self.assertEqual(p.returncode, 1)
        self.assertIn('deploy key saknas', p.stdout)

    def test_43_auto_uppdaterar_bara_nar_det_ar_pa(self):
        w = self.w
        w.release(tree('c1'))
        self.assertEqual(w.run('auto').returncode, 0)
        self.assertIsNone(w.installed(), 'auto_apply = no: bara kontroll')
        self.assertTrue(w.status()['update_available'])
        w.write_conf(auto_apply='yes')
        self.assertEqual(w.run('auto').returncode, 0)
        self.assertEqual(w.app_version(), 'c1')

    def test_44_status_skriver_svenska_och_json(self):
        w = self.w
        w.release(tree('c1'))
        w.run('apply')
        p = w.run('status')
        self.assertEqual(p.returncode, 0)
        self.assertIn('Installerad:', p.stdout)
        j = json.loads(w.run('status', '--json').stdout)
        self.assertEqual(j['installed']['commit'], w.installed())


if __name__ == '__main__':
    unittest.main(verbosity=2)
