"""Spelbiblioteket: hittar spelfilerna i spelmappen, kontrollerar och laddar dem och ger spelväljaren det den visar.

Ett spel är en fil NAMN.py i spelmappen (standard /var/lib/dash-panel/games/). Filen kontrolleras innan den körs:
 - den måste vara Python 3.11 som går att tolka och inte vara större än MAX_SOURCE;
 - META (en dict med api, id, name, desc) läses ur källan utan att köra något; id måste vara samma som filnamnet;
 - ett skyddsräcke (inte en sandlåda!) stoppar filer som importerar något utanför listan över tillåtna moduler, anropar
   open/exec/eval/compile, kommer åt __builtins__/__class__ och liknande. Det är till för att fånga misstag och
   slarvigt genererad kod, inte för att stoppa den som medvetet vill göra något (spelen körs som root i panelens process).
 - filen körs sedan i en egen modul där bara de tillåtna importerna fungerar.
En fil som inte klarar det här visas nedtonad i väljaren med orsaken; den stoppar aldrig väljaren eller panelen.

Biblioteket minns laddade spel (på filens ändringstid och storlek) så att väljaren kan söka igenom mappen varje gång den
öppnas utan att ladda om något som inte ändrats."""
import ast
import builtins
import os
import re
import types

from PIL import Image

from . import gamesdk as sdk

GAMES_DIR = '/var/lib/dash-panel/games'
DATA_DIR = '/var/lib/dash-panel/game-data'
LEGACY_ROOT = '/var/lib/dash-panel/'
ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{1,31}$')
FILE_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{1,31}\.py$')
MAX_SOURCE = 400000
MAX_GAMES = 64
NAME_MAX = 24
DESC_MAX = 120

ALLOWED_MODULES = frozenset((
    'math', 'cmath', 'random', 'time', 'datetime', 'json', 'itertools', 'collections', 'collections.abc', 'functools',
    'heapq', 'bisect', 'string', 'enum', 'dataclasses', 'typing', 're', 'copy', 'textwrap', 'operator', 'fractions',
    'decimal', 'statistics', 'base64', 'zlib', 'struct', 'array', 'abc', 'numbers', '__future__'))
ALLOWED_PIL = frozenset(('Image', 'ImageDraw', 'ImageChops', 'ImageFilter', 'ImageOps'))
FORBIDDEN_NAMES = frozenset((
    'open', 'exec', 'eval', 'compile', 'input', 'breakpoint', 'globals', 'locals', 'vars', 'help', 'exit', 'quit',
    '__import__', '__builtins__', 'memoryview'))
ALLOWED_DUNDER = frozenset((
    '__init__', '__name__', '__doc__', '__len__', '__iter__', '__next__', '__contains__', '__getitem__', '__setitem__',
    '__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__', '__hash__', '__repr__', '__str__', '__call__',
    '__enter__', '__exit__', '__bool__', '__add__', '__sub__', '__mul__'))

ALLOWED_TEXT = ('math, random, time, datetime, json, itertools, collections, functools, heapq, bisect, string, enum, '
                'dataclasses, typing, re, copy, textwrap, operator, fractions, decimal, statistics, base64, zlib, '
                'struct, array, PIL.Image/ImageDraw/ImageChops/ImageFilter/ImageOps och dashpanel.gamesdk')


# ---------------------------------------------------------------- kontroll av källan
def import_allowed(name, fromlist=()):
    """Får ett spel göra `import name` / `from name import fromlist`?"""
    fromlist = tuple(fromlist or ())
    if name == 'PIL':
        return all(f in ALLOWED_PIL for f in fromlist)
    if name.startswith('PIL.'):
        return name.split('.')[1] in ALLOWED_PIL
    if name == 'dashpanel':
        return bool(fromlist) and all(f == 'gamesdk' for f in fromlist)
    if name == 'dashpanel.gamesdk':
        return True
    return name in ALLOWED_MODULES


def lint(tree):
    """Skyddsräcket: lista med meddelanden ('rad N: ...'), tom om allt är i sin ordning."""
    msgs = []
    for node in ast.walk(tree):
        ln = getattr(node, 'lineno', 0)
        if isinstance(node, ast.Import):
            for a in node.names:
                if not import_allowed(a.name):
                    msgs.append('rad %d: import av %s är inte tillåten' % (ln, a.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module or not import_allowed(node.module, [a.name for a in node.names]):
                msgs.append('rad %d: import från %s är inte tillåten' % (ln, '.' * node.level + (node.module or '')))
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                msgs.append('rad %d: %s får inte användas i ett spel' % (ln, node.id))
        elif isinstance(node, ast.Attribute):
            a = node.attr
            if a.startswith('__') and a.endswith('__') and a not in ALLOWED_DUNDER:
                msgs.append('rad %d: .%s får inte användas i ett spel' % (ln, a))
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith)):
            msgs.append('rad %d: async/await används inte i spel (panelen anropar spelet, inte tvärtom)' % ln)
        elif isinstance(node, (ast.Global,)):
            msgs.append('rad %d: global används inte (spara tillstånd i self)' % ln)
    return msgs


def parse_meta(tree):
    """META ur källan (en bokstavlig dict) utan att köra koden, eller None."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'META' for t in node.targets):
            try:
                v = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                return None
            return v if isinstance(v, dict) else None
    return None


def check_meta(meta, stem, legacy_root=LEGACY_ROOT):
    """Fel i META som lista med meddelanden."""
    errs = []
    if meta is None:
        return ['META saknas, eller är inte en dict med bara bokstavliga värden']
    api = meta.get('api')
    if not isinstance(api, int) or isinstance(api, bool) or api < 1:
        errs.append("META['api'] måste vara ett heltal (nu %d)" % sdk.API)
    elif api > sdk.API:
        errs.append('kräver nyare panel (spelet är skrivet för API %d, panelen kan API %d)' % (api, sdk.API))
    gid = meta.get('id')
    if not isinstance(gid, str) or not ID_RE.match(gid):
        errs.append("META['id'] måste vara 2-32 tecken av a-z, 0-9, _ och -")
    elif gid != stem:
        errs.append("META['id'] (%s) måste vara samma som filnamnet (%s.py)" % (gid, stem))
    name = meta.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > NAME_MAX:
        errs.append("META['name'] måste vara text på 1-%d tecken" % NAME_MAX)
    desc = meta.get('desc')
    if not isinstance(desc, str) or not desc.strip() or len(desc) > DESC_MAX:
        errs.append("META['desc'] måste vara text på 1-%d tecken" % DESC_MAX)
    ver = meta.get('version', 1)
    if not isinstance(ver, int) or isinstance(ver, bool):
        errs.append("META['version'] måste vara ett heltal")
    leg = meta.get('legacy_save')
    if leg is not None and not (isinstance(leg, str) and leg.startswith(legacy_root) and leg.endswith('.json')
                                and '..' not in leg):
        errs.append("META['legacy_save'] måste vara en .json-fil under %s" % legacy_root)
    return errs


def _has_game_class(tree):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'Game':
            return True
    return False


def static_check(source, stem, legacy_root=LEGACY_ROOT):
    """Kontrollerar en spelfil utan att köra den. Ger (träd, meta, fel) där fel är en lista med meddelanden; träd är
    None om filen inte går att tolka."""
    if len(source) > MAX_SOURCE:
        return None, None, ['filen är för stor (%d tecken, högst %d)' % (len(source), MAX_SOURCE)]
    try:
        tree = ast.parse(source, filename=stem + '.py')
    except SyntaxError as e:
        return None, None, ['syntaxfel på rad %s: %s' % (e.lineno, e.msg)]
    except ValueError as e:
        return None, None, ['kan inte tolkas: %s' % e]
    meta = parse_meta(tree)
    errs = check_meta(meta, stem, legacy_root)
    errs += lint(tree)
    if not _has_game_class(tree):
        errs.append('klassen Game saknas (class Game(sdk.GameBase))')
    return tree, meta, errs


# ---------------------------------------------------------------- körning
def _make_builtins():
    b = dict(vars(builtins))
    for n in FORBIDDEN_NAMES:
        b.pop(n, None)
    real = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if level or not import_allowed(name, fromlist):
            raise ImportError('importen av %r är inte tillåten i ett spel' % (name,))
        return real(name, globals, locals, fromlist, 0)

    b['__import__'] = guarded
    return b


_BUILTINS = _make_builtins()


def exec_module(tree, stem):
    """Kör det kontrollerade trädet i en egen modul. Ger modulen."""
    mod = types.ModuleType('dashgame_' + stem.replace('-', '_'))
    mod.__dict__['__builtins__'] = _BUILTINS
    mod.__dict__['__file__'] = stem + '.py'
    exec(compile(tree, stem + '.py', 'exec'), mod.__dict__)
    return mod


class GameInfo(object):
    """Ett spel i biblioteket. error är None om det går att öppna, annars orsaken (kort, på svenska)."""

    def __init__(self, stem, path, key):
        self.id = stem
        self.path = path
        self.key = key
        self.name = stem
        self.desc = ''
        self.version = 1
        self.meta = {}
        self.mod = None
        self.cls = None
        self.error = None
        self._icons = {}


def load_game(stem, path, key, legacy_root=LEGACY_ROOT):
    """Laddar spelfilen path. Ger alltid ett GameInfo; fel hamnar i .error."""
    info = GameInfo(stem, path, key)
    try:
        with open(path, 'rb') as f:
            raw = f.read(MAX_SOURCE + 1)
        try:
            source = raw.decode('utf-8')
        except UnicodeDecodeError:
            info.error = 'filen är inte UTF-8-text'
            return info
        tree, meta, errs = static_check(source, stem, legacy_root)
        if isinstance(meta, dict):
            if isinstance(meta.get('name'), str) and meta['name'].strip():
                info.name = meta['name'].strip()[:NAME_MAX]
            if isinstance(meta.get('desc'), str):
                info.desc = meta['desc'].strip()[:DESC_MAX]
        if errs:
            info.error = errs[0] + (' (+%d fler)' % (len(errs) - 1) if len(errs) > 1 else '')
            return info
        info.meta = dict(meta)
        info.version = meta.get('version', 1)
        mod = exec_module(tree, stem)
        cls = getattr(mod, 'Game', None)
        if not (isinstance(cls, type) and issubclass(cls, sdk.GameBase)):
            info.error = 'Game måste ärva från sdk.GameBase'
            return info
        info.mod, info.cls = mod, cls
    except Exception as e:      # ett spel som inte går att köra ska aldrig stoppa väljaren
        info.error = ('%s: %s' % (type(e).__name__, e))[:140]
        info.mod = info.cls = None
    return info


class Library(object):
    """Spelmappen och spelen i den. games_dir/data_dir None eller 'none' = inga filer (provmiljö utan spel)."""

    def __init__(self, games_dir=GAMES_DIR, data_dir=DATA_DIR, log=None, legacy_root=LEGACY_ROOT):
        self.games_dir = games_dir if games_dir not in (None, '', 'none') else None
        self.data_dir = data_dir if data_dir not in (None, '', 'none') else None
        self.log = log or (lambda *a: None)
        self.legacy_root = legacy_root
        self._cache = {}
        self._list = []

    # ------------------------------------------------------------ sökning
    def scan(self):
        """Söker igenom mappen och ger alla spelfiler som GameInfo, sorterade på namn. Bara nya och ändrade filer
        laddas om."""
        found = {}
        if self.games_dir:
            try:
                names = sorted(os.listdir(self.games_dir))
            except OSError:
                names = []
            for fn in names:
                if not FILE_RE.match(fn):
                    continue
                path = os.path.join(self.games_dir, fn)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                if not os.path.isfile(path):
                    continue
                if len(found) >= MAX_GAMES:
                    self.log('för många spelfiler: %s hoppas över' % fn)
                    continue
                key = (st.st_mtime_ns, st.st_size)
                old = self._cache.get(fn)
                if old is not None and old.key == key:
                    found[fn] = old
                    continue
                info = load_game(fn[:-3], path, key, self.legacy_root)
                if info.error:
                    self.log('spelet %s kan inte öppnas: %s' % (fn, info.error))
                found[fn] = info
        self._cache = found
        self._list = sorted(found.values(), key=lambda i: (i.name.casefold(), i.id))
        return list(self._list)

    def games(self):
        return list(self._list)

    def get(self, gid):
        for i in self._list:
            if i.id == gid:
                return i
        return None

    # ------------------------------------------------------------ vad väljaren visar
    def save_path(self, gid):
        return os.path.join(self.data_dir, gid + '.json') if self.data_dir else None

    def legacy_path(self, info):
        return info.meta.get('legacy_save') if info.meta else None

    def icon(self, info, bg=sdk.ICON_BG):
        """Spelets ikon (128x128) på bakgrunden bg, ritad en gång per bakgrund. Ett spel utan draw_icon, eller med en
        som går fel, får en enkel standardikon."""
        hit = info._icons.get(bg)
        if hit is not None:
            return hit
        im = Image.new('RGB', (sdk.ICON, sdk.ICON), bg)
        fn = getattr(info.mod, 'draw_icon', None) if info.mod is not None else None
        try:
            if not callable(fn):
                raise LookupError
            fn(im)
        except LookupError:
            im = Image.new('RGB', (sdk.ICON, sdk.ICON), bg)
            sdk.default_icon(im, info.name)
        except Exception as e:
            self.log('ikonen i %s gick inte att rita: %r' % (info.id, e))
            im = Image.new('RGB', (sdk.ICON, sdk.ICON), bg)
            sdk.default_icon(im, info.name)
        if im.size != (sdk.ICON, sdk.ICON) or im.mode != 'RGB':
            im = im.convert('RGB').resize((sdk.ICON, sdk.ICON))
        info._icons[bg] = im
        return im

    def status(self, info):
        """Raden under spelets namn i väljaren: (text, aktiv) eller None. Läser sparfilen utan att starta spelet och
        frågar spelets status(data)."""
        fn = getattr(info.mod, 'status', None) if info.mod is not None else None
        if not callable(fn) or info.error:
            return None
        try:
            data = sdk.read_save(self.save_path(info.id), info.id, self.legacy_path(info) if self.data_dir else None)
            res = fn(data)
            if res is None:
                return None
            text, active = res
            if not isinstance(text, str) or not text:
                return None
            return text[:60], bool(active)
        except Exception as e:
            self.log('statusraden i %s gick inte att läsa: %r' % (info.id, e))
            return None

    # ------------------------------------------------------------ öppna
    def make_game(self, info, surface, loop, hooks=None, rng=None):
        """Skapar en ny spelinstans. Kastar ett fel om spelet inte går att skapa."""
        if info.error or info.cls is None:
            raise RuntimeError('spelet %s kan inte öppnas: %s' % (info.id, info.error))
        ctx = sdk.GameContext(loop, surface, info.meta, self.save_path(info.id),
                              self.legacy_path(info) if self.data_dir else None, hooks, rng)
        scr = info.cls(ctx)
        scr._lib_key = info.key
        return scr
