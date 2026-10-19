"""Provar en spelfil utan skärm och utan Home Assistant: laddar den som panelen gör, ritar, trycker, låter tiden gå, sparar
och läser tillbaka. Körs av den som skriver ett spel (och av proven) innan filen läggs i GitHub-repot:

    python3 -m dashpanel.gamecheck games/mitt_spel.py                 # kontrollerar och skriver en rapport
    python3 -m dashpanel.gamecheck games/mitt_spel.py --png ut         # sparar ut-1.png (start) och ut-2.png (efter tryck)

Avslutskod 0 om inget fel hittades (varningar räknas inte), annars 1. Kräver bara Python 3 och Pillow.

Provet är inget bevis för att spelet är bra, bara att det går att ladda, rita och trycka på utan att något går sönder, att
det håller sig inom skärmens yta och att sparfilen går att läsa tillbaka."""
import argparse
import json
import os
import random
import shutil
import signal
import sys
import tempfile
import time

from PIL import Image, ImageChops

from . import gamelib, gamesdk as sdk
from .gfx import H, W
from .surface import NullSink, Surface

DEFAULT_TIMEOUT = 25
SLOW_DRAW = 1.0         # en ritning som tar längre än så här (på den här datorn) får en varning; dash är ca tio gånger långsammare


# ---------------------------------------------------------------- låtsastid
class _Handle(object):
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class FakeLoop(object):
    """Det spelen behöver av asyncio-loopen (time, call_later, call_soon) med tid som styrs av provet."""

    def __init__(self):
        self.t = 1000.0
        self._q = []
        self._seq = 0

    def time(self):
        return self.t

    def call_later(self, delay, fn, *args):
        h = _Handle()
        self._seq += 1
        self._q.append((self.t + max(0.0, delay), self._seq, h, fn, args))
        return h

    def call_soon(self, fn, *args):
        return self.call_later(0.0, fn, *args)

    def advance(self, secs, on_step=None):
        """Låter secs sekunder gå och kör de tidtagare som förfaller, i tur och ordning."""
        end = self.t + secs
        while True:
            due = [e for e in self._q if not e[2].cancelled and e[0] <= end]
            if not due:
                break
            due.sort(key=lambda e: (e[0], e[1]))
            e = due[0]
            self._q.remove(e)
            self.t = max(self.t, e[0])
            e[3](*e[4])
            if on_step is not None:
                on_step()
        self._q = [e for e in self._q if not e[2].cancelled]
        self.t = end

    def pending(self):
        return sum(1 for e in self._q if not e[2].cancelled)


class Env(object):
    """En spelinstans med låtsastid, ritYta och räknare för det spelet ber panelen om."""

    def __init__(self, info, lib, seed=1, hooks=None):
        self.loop = FakeLoop()
        self.surface = Surface(NullSink())
        self.refreshes = 0
        self.logs = []
        self.exited = 0
        h = {'refresh': self._refresh, 'clock': lambda: '12:34', 'log': lambda *a: self.logs.append(' '.join(str(x) for x in a)),
             'exit': self._exit}
        h.update(hooks or {})
        self.hooks = h
        self.game = lib.make_game(info, self.surface, self.loop, h, random.Random(seed))

    def _refresh(self, urgent=False):
        self.refreshes += 1

    def _exit(self):
        self.exited += 1

    def frame(self, gen=1):
        self.game.draw(gen)
        self.surface.flush()
        return self.surface.img

    def tap(self, x, y, hold=0.05):
        self.game.on_touch('down', x, y)
        self.loop.advance(hold)
        self.game.on_touch('up', x, y)

    def drag(self, x0, y0, x1, y1, steps=6):
        self.game.on_touch('down', x0, y0)
        for k in range(1, steps + 1):
            self.game.on_touch('move', x0 + (x1 - x0) * k // steps, y0 + (y1 - y0) * k // steps)
        self.game.on_touch('up', x1, y1)


# ---------------------------------------------------------------- rapport
class Report(object):
    def __init__(self, name):
        self.name = name
        self.errors = []
        self.warnings = []
        self.notes = []
        self.max_draw = 0.0

    @property
    def ok(self):
        return not self.errors

    def err(self, s):
        self.errors.append(s)

    def warn(self, s):
        self.warnings.append(s)

    def note(self, s):
        self.notes.append(s)

    def text(self):
        out = ['%s: %s' % (self.name, 'OK' if self.ok else 'FEL')]
        out += ['  fel:      ' + e for e in self.errors]
        out += ['  varning:  ' + w for w in self.warnings]
        out += ['  ' + n for n in self.notes]
        return '\n'.join(out)


class _Timeout(Exception):
    pass


def _alarm(seconds):
    if hasattr(signal, 'SIGALRM') and seconds:
        def handler(signum, frame):
            raise _Timeout()
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(int(seconds))


def _alarm_off():
    if hasattr(signal, 'SIGALRM'):
        signal.alarm(0)


def _targets_of(game, rep):
    """Spelets targets() kontrollerade: lista av (namn, ruta)."""
    try:
        ts = list(game.targets() or ())
    except Exception as e:
        rep.err('targets() kastade %s: %s' % (type(e).__name__, e))
        return []
    out = []
    for t in ts:
        if not (isinstance(t, (tuple, list)) and len(t) in (2, 3) and isinstance(t[0], str)
                and isinstance(t[1], (tuple, list)) and len(t[1]) == 4 and all(isinstance(v, int) for v in t[1])):
            rep.err('targets() ska ge (namn, (x0, y0, x1, y1)) med heltal, fick %r' % (t,))
            continue
        r = tuple(t[1])
        if r[2] <= r[0] or r[3] <= r[1]:
            rep.err('knappen %s har en tom ruta %r' % (t[0], r))
        elif r[0] < 0 or r[1] < sdk.AREA[1] or r[2] > W or r[3] > H:
            rep.err('knappen %s ligger utanför spelytan (x 0-%d, y %d-%d): %r' % (t[0], W, sdk.AREA[1], H, r))
        out.append((t[0], r))
    return out


def check_file(path, effort=1.0, timeout=DEFAULT_TIMEOUT, png=None, legacy_root=gamelib.LEGACY_ROOT):
    """Kontrollerar spelfilen path. effort 1.0 = hela provet, mindre = färre slumptryck. Ger en Report."""
    stem = os.path.basename(path)
    stem = stem[:-3] if stem.endswith('.py') else stem
    rep = Report(os.path.basename(path))
    tmp = tempfile.mkdtemp(prefix='gamecheck-')
    try:
        _alarm(timeout)
        try:
            _check(path, stem, rep, effort, tmp, png, legacy_root)
        except _Timeout:
            rep.err('spelet tog för lång tid (över %d s): en ändlös slinga?' % timeout)
        except Exception as e:
            import traceback
            tb = traceback.extract_tb(sys.exc_info()[2])
            where = ''
            for fr in reversed(tb):
                if fr.filename.endswith(stem + '.py'):
                    where = ' (rad %d i %s.py)' % (fr.lineno, stem)
                    break
            rep.err('oväntat fel: %s: %s%s' % (type(e).__name__, e, where))
        finally:
            _alarm_off()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rep


def _check(path, stem, rep, effort, tmp, png, legacy_root):
    try:
        st = os.stat(path)
    except OSError as e:
        rep.err('filen kan inte läsas: %s' % e)
        return
    if not gamelib.FILE_RE.match(stem + '.py'):
        rep.err('filnamnet ska vara 2-32 tecken av a-z, 0-9, _ och -, plus .py (nu %s)' % os.path.basename(path))
    info = gamelib.load_game(stem, path, (st.st_mtime_ns, st.st_size), legacy_root)
    if info.error:
        rep.err(info.error)
        # visa alla fel i källan, inte bara det första
        try:
            with open(path, encoding='utf-8') as f:
                _, _, errs = gamelib.static_check(f.read(), stem, legacy_root)
            for e in errs[1:]:
                rep.err(e)
        except (OSError, UnicodeDecodeError):
            pass
        return
    rep.note('spel: %s (%s) version %s, API %s' % (info.name, info.id, info.version, info.meta.get('api')))
    lib = gamelib.Library(None, os.path.join(tmp, 'data'), legacy_root=legacy_root)
    logs = []
    lib.log = lambda *a: logs.append(' '.join(str(x) for x in a))
    lib.legacy_path = lambda info: None     # provet läser aldrig enhetens riktiga äldre sparfiler (/var/lib/dash-panel/*.json)

    # --- ikon och status
    icon = lib.icon(info)
    if not ImageChops.difference(icon, Image.new('RGB', icon.size, sdk.ICON_BG)).getbbox():
        rep.warn('ikonen är tom (draw_icon ritar ingenting eller saknas)')
    if getattr(info.mod, 'draw_icon', None) is None:
        rep.warn('draw_icon(im) saknas: spelet får en standardikon')
    for line in logs:
        rep.warn(line)
    del logs[:]
    if callable(getattr(info.mod, 'status', None)):
        res = lib.status(info)
        for line in logs:
            rep.err(line)
        rep.note('status utan sparfil: %r' % (res,))

    # --- skapa, öppna och rita
    env = Env(info, lib)
    g = env.game
    g.open()
    t0 = time.perf_counter()
    img = env.frame(1)
    dt = time.perf_counter() - t0
    rep.max_draw = dt
    area = img.crop(sdk.AREA)
    if not ImageChops.difference(area, Image.new('RGB', area.size, sdk.BG)).getbbox():
        rep.warn('inget ritas i spelytan vid start (paint() ritar ingenting?)')
    if png:
        img.save('%s-1.png' % png)
    # rubrikraden (y < 84) ska bara ritas av panelen
    base = _blank_frame(info, lib)
    top_a = img.crop((0, 0, W, sdk.AREA[1]))
    if ImageChops.difference(top_a, base.crop((0, 0, W, sdk.AREA[1]))).getbbox():
        rep.err('spelet ritar ovanför y=%d (rubrikraden är panelens)' % sdk.AREA[1])

    # --- knappar
    ts = _targets_of(g, rep)
    names = [t[0] for t in ts]
    if len(set(names)) != len(names):
        rep.warn('flera knappar har samma namn: %s' % sorted(set(n for n in names if names.count(n) > 1)))
    rep.note('knappar vid start: %d' % len(ts))
    for name, r in ts[:12]:
        cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
        env.tap(cx, cy)
        t0 = time.perf_counter()
        env.frame(1)
        rep.max_draw = max(rep.max_draw, time.perf_counter() - t0)
        env.loop.advance(1.0)
        env.frame(1)
        if env.exited:
            rep.err('ett tryck på knappen %s lämnade spelet (exit() ska bara komma från Tillbaka-knappen)' % name)
            env.exited = 0
    if png:
        env.frame(2).save('%s-2.png' % png)

    # --- slumptryck, drag och tid
    rnd = random.Random(7)
    n = max(3, int(30 * effort))
    for k in range(n):
        x, y = rnd.randrange(0, W), rnd.randrange(sdk.AREA[1], H)
        if k % 5 == 4:
            env.drag(x, y, rnd.randrange(0, W), rnd.randrange(sdk.AREA[1], H))
        else:
            env.tap(x, y)
        t0 = time.perf_counter()
        env.frame(1)
        rep.max_draw = max(rep.max_draw, time.perf_counter() - t0)
        if k % 7 == 0:
            env.loop.advance(rnd.choice((0.2, 1.5, 9.0)), on_step=lambda: env.frame(1))
    env.loop.advance(60.0, on_step=lambda: env.frame(1))
    env.frame(3)                  # ny gen: hela skärmen ritas om
    # mitt i en tryckning ska ett nytt gen inte ställa till något
    g.on_touch('down', 500, 300)
    env.frame(4)
    g.on_touch('up', 500, 300)
    env.frame(4)
    if env.exited:
        env.exited = 0

    # --- Tillbaka-knappen
    env.tap(60, 46)
    if not env.exited:
        rep.err('Tillbaka-knappen (uppe till vänster) anropade inte exit()')
    env.exited = 0

    # --- spara och läsa tillbaka
    try:
        st1 = g.state()
    except Exception as e:
        rep.err('state() kastade %s: %s' % (type(e).__name__, e))
        st1 = None
    if st1 is not None:
        if not isinstance(st1, dict):
            rep.err('state() ska ge en dict eller None, fick %s' % type(st1).__name__)
        else:
            try:
                blob = json.dumps(st1, allow_nan=False)
            except (TypeError, ValueError) as e:
                rep.err('state() innehåller något som inte går att spara som JSON: %s' % e)
                blob = None
            if blob is not None:
                if len(blob) > sdk.MAX_SAVE_BYTES:
                    rep.err('sparfilen blir för stor (%d tecken, högst %d)' % (len(blob), sdk.MAX_SAVE_BYTES))
                else:
                    g.save_now(force=True)
                    sp = lib.save_path(info.id)
                    if not (sp and os.path.exists(sp)):
                        rep.err('sparfilen skrevs inte')
                    else:
                        env2 = Env(info, lib, seed=2)
                        env2.game.open()
                        env2.frame(1)
                        st2 = env2.game.state()
                        if json.loads(blob) != json.loads(json.dumps(st2)):
                            rep.warn('state() är inte lika efter att sparfilen lästs in igen')
                        if env2.logs:
                            rep.err('sparfilen kunde inte läsas tillbaka: ' + env2.logs[0].splitlines()[0])
                        stt = lib.status(info)
                        if callable(getattr(info.mod, 'status', None)):
                            rep.note('status med sparfil: %r' % (stt,))
                        env2.game.close()
                        env2.game.stop()
                        # en trasig sparfil ska ge ett nytt spel, inte ett fel
                        with open(sp, 'w') as f:
                            f.write('{"sdk":1,"game":"%s","data":{"trasig":[1,2' % info.id)
                        env3 = Env(info, lib, seed=3)
                        env3.game.open()
                        env3.frame(1)
                        env3.game.close()
                        # en sparfil med fel innehåll ska läggas undan, inte krascha
                        with open(sp, 'w') as f:
                            json.dump({'sdk': 1, 'game': info.id, 'data': {'x': 'y', 'board': 7, 'cur': None}}, f)
                        env4 = Env(info, lib, seed=4)
                        env4.game.open()
                        env4.frame(1)
                        env4.game.close()
    else:
        rep.note('spelet sparar ingenting (state() ger None)')

    # --- stäng och öppna igen, stoppa
    g.close()
    g.open()
    env.frame(5)
    g.close()
    g.stop()
    if env.loop.pending():
        rep.warn('%d tidtagare ligger kvar efter stop()' % env.loop.pending())
    if env.logs:
        for line in env.logs[:3]:
            rep.warn('spelet loggade: ' + line.splitlines()[0][:120])
    if rep.max_draw > SLOW_DRAW:
        rep.warn('en ritning tog %.2f s här; dash är ca tio gånger långsammare: rita bara det som ändrats '
                 '(invalidate(rect)) och förrendera tunga delar' % rep.max_draw)
    rep.note('längsta ritning här: %.0f ms (dash: räkna med ungefär tio gånger så mycket)' % (rep.max_draw * 1000))


def _blank_frame(info, lib):
    """Samma rubrikrad som spelet, utan att spelet ritar något: basklassens egen ritning med spelets titel."""
    class Blank(sdk.GameBase):
        pass
    env_loop = FakeLoop()
    surf = Surface(NullSink())
    ctx = sdk.GameContext(env_loop, surf, info.meta, None, None, {'clock': lambda: '12:34'})
    b = Blank(ctx)
    b.open()
    b.draw(1)
    return surf.img


def main(argv=None):
    ap = argparse.ArgumentParser(description='Provar en spelfil för simple_ha_dash.')
    ap.add_argument('files', nargs='+', help='spelfil(er), till exempel games/mitt_spel.py')
    ap.add_argument('--png', metavar='PREFIX', help='spara skärmbilder: PREFIX-1.png (start) och PREFIX-2.png (efter tryck)')
    ap.add_argument('--quick', action='store_true', help='färre slumptryck')
    ap.add_argument('--json', action='store_true', help='skriv resultatet som JSON')
    a = ap.parse_args(argv)
    reps = []
    for i, p in enumerate(a.files):
        png = a.png if (a.png and len(a.files) == 1) else (('%s-%d' % (a.png, i)) if a.png else None)
        reps.append(check_file(p, effort=0.3 if a.quick else 1.0, png=png))
    if a.json:
        print(json.dumps([{'file': r.name, 'ok': r.ok, 'errors': r.errors, 'warnings': r.warnings,
                           'notes': r.notes} for r in reps], ensure_ascii=False))
    else:
        for r in reps:
            print(r.text())
    return 0 if all(r.ok for r in reps) else 1


if __name__ == '__main__':
    sys.exit(main())
