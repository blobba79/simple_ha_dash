"""Spel-SDK (API 1): allt en spelfil behöver av panelen.

Ett spel är en enda Python-fil i mappen games/ (se games/SKAPA-SPEL.md). Filen importerar bara det här:

    from dashpanel import gamesdk as sdk

och definierar META, en klass Game(sdk.GameBase) och (valfritt) draw_icon(im) och status(data). Panelen laddar filen,
ritar spelväljaren, öppnar spelet och skickar tryck. Det här är det enda stabila gränssnittet mot panelen: spelen ska
inte importera något annat ur dashpanel.

GameBase sköter det som alla spel annars skulle göra likadant: rubrikraden med Tillbaka-knappen och klockan,
tidtagare, att bara ritade rutor skickas till skärmen, tryck på knappar (press, glid ut, släpp), sparfilen (atomisk
skrivning, trasig fil läggs undan) och att ett fel i spelet inte tar ner panelen.

Skärmen är 1024x600. Rubrikraden (y 10-82) ritas av basklassen; spelet har AREA (y 84-600) för sig själv."""
import json
import os
import random
import traceback

from . import theme as T
from .gfx import H, W, bbox, blend, circle, fit, icon, rbox, rbox_mask, snap, text, text_width, wrap

API = 1

# ---------------------------------------------------------------- mått
HEAD_RECT = (0, 10, 700, 82)            # Tillbaka-knappen och rubriken
CLOCK_RECT = (846, 10, W, 82)           # klockan uppe till höger
BACK_Y = (16, 76)                       # Tillbaka-knappens övre och nedre kant
AREA = (0, 84, W, H)                    # det som spelet ritar i
ICON = 128                              # spelikonens sida (draw_icon får en bild av den storleken)
ICON_BG = (0x24, 0x24, 0x24)            # bakgrunden bilden är ifylld med
HIT_SLOP = 16                           # så långt fingret får glida från en knapp och ändå trycka på den
SAVE_DELAY = 8.0                        # högst så här länge väntar panelen med att skriva sparfilen
MAX_SAVE_BYTES = 200000                 # största tillåtna sparfil

# ---------------------------------------------------------------- färger (panelens tema)
BG = T.BG
CARD = T.CARD
CARD_BORDER = T.CARD_BORDER
TEXT = T.TEXT
MUTED = T.MUTED
FOOT = T.FOOT
BLUE = T.BLUE
BLUE_L = T.BLUE_L
BLUE_D = T.BLUE_D
BLUE_BG = T.BLUE_BG
GREEN = T.GREEN
GREEN_D = T.GREEN_D
GREEN_BORDER = T.GREEN_BORDER
RED = T.RED
RED_D = T.RED_D
RED_BORDER = T.RED_BORDER
WARN = T.WARN
WARN_D = T.WARN_D
WARN_BORDER = T.WARN_BORDER
YELLOW = T.YELLOW
ORANGE = T.ORANGE
BTN_BG = T.BTN_BG
SKELETON = T.SKELETON
STALE_TEXT = T.STALE_TEXT

# Ritfunktionerna (Pillow) kommer från panelens gfx och används som sdk.text, sdk.text_width, sdk.fit, sdk.wrap, sdk.rbox,
# sdk.bbox, sdk.rbox_mask, sdk.circle, sdk.blend, sdk.icon och sdk.snap (importerade överst).


# ---------------------------------------------------------------- små hjälpare
def inside(r, x, y, slop=0):
    """Ligger punkten (x, y) i rutan r = (x0, y0, x1, y1), med slop pixlar marginal?"""
    return r[0] - slop <= x < r[2] + slop and r[1] - slop <= y < r[3] + slop


def clip(r, area=(0, 0, W, H)):
    """r beskuren till area."""
    return (max(area[0], r[0]), max(area[1], r[1]), min(area[2], r[2]), min(area[3], r[3]))


def union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def meets(a, b):
    """Överlappar rutorna a och b?"""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def fill(img, r, color=T.BG):
    """Fyller rutan r med färgen color (standard bakgrunden)."""
    img.paste(color, (r[0], r[1], r[2], r[3]))


def centered(img, cx, baseline, s, weight, size, color):
    """Ritar texten s med mitten vid cx. weight är 300, 400 eller 500; baseline är textens baslinje (y)."""
    text(img, cx - text_width(s, weight, size) / 2.0, baseline, s, weight, size, color)


def thousands(n):
    """1234567 -> '1 234 567'."""
    return '{:,}'.format(int(n)).replace(',', ' ')


_BUTTON_KINDS = {
    'normal': (T.BTN_BG, T.CARD_BORDER, 1),
    'primary': (T.BLUE_D, T.BLUE, 2),
    'ok': (T.GREEN_D, T.GREEN_BORDER, 2),
    'warn': (T.WARN_D, T.WARN_BORDER, 2),
    'danger': (T.RED_D, T.RED_BORDER, 2),
}


def button(img, rect, label, kind='normal', pressed=False, enabled=True, size=24, icon_name=None, icon_color=None):
    """Ritar en knapp i panelens stil. kind: normal, primary (blå), ok (grön), warn (orange) eller danger (röd).
    icon_name: ikon ur panelens uppsättning, 40 px (CloudDownload, Power, Restart, ExitToApp)."""
    x0, y0, x1, y1 = rect
    fl, border, bw = _BUTTON_KINDS[kind]
    if not enabled:
        fl, border = blend(fl, T.BG, 0.5), blend(border, T.BG, 0.5)
    elif pressed:
        fl = blend(fl, (255, 255, 255), 0.09)
    bbox(img, x0, y0, x1, y1, min(20, (y1 - y0) // 2), fl, border, bw)
    color = T.TEXT if enabled else T.STALE_TEXT
    base = y0 + (y1 - y0) // 2 + size // 3
    if icon_name:
        icon(img, icon_name, 40, x0 + 22, y0 + (y1 - y0 - 40) // 2, icon_color or color)
        text(img, x0 + 78, base, label, 500, size, color)
    else:
        centered(img, (x0 + x1) // 2, base, label, 500, size, color)


def paint_head(img, title, pressed=False, label='Tillbaka'):
    """Ritar rubrikraden: Tillbaka-knappen och rubriken. Ger knappens ruta. (GameBase gör det åt spelet.)"""
    fill(img, HEAD_RECT)
    w = 78 + text_width(label, 500, 21)
    fl = blend(T.CARD, (255, 255, 255), 0.07) if pressed else T.CARD
    bbox(img, 16, BACK_Y[0], snap(16 + w), BACK_Y[1], 18, fl, T.CARD_BORDER, 2)
    icon(img, 'ChevronLeft', 32, 30, 30, T.TEXT)
    text(img, 68, 53, label, 500, 21, T.TEXT)
    text(img, 16 + w + 16, 56, title, 400, 30, T.TEXT)
    return (16, BACK_Y[0], snap(16 + w), BACK_Y[1])


def paint_clock(img, clock):
    fill(img, CLOCK_RECT)
    if clock:
        text(img, 1008, 58, clock, 300, 36, T.TEXT, anchor='rs')


def default_icon(im, name='?'):
    """Ikonen som visas om spelet inte har draw_icon: spelets första bokstav i en rundad ruta."""
    rbox(im, 14, 14, ICON - 14, ICON - 14, 22, T.BLUE_D)
    centered(im, ICON // 2, ICON // 2 + 24, (name or '?')[:1].upper(), 500, 72, T.BLUE_L)


# ---------------------------------------------------------------- sparfil
def read_save(path, game_id, legacy_path=None):
    """Spelets sparade data (en dict) eller None. Finns ingen ny sparfil läses legacy_path (en äldre sparfil som
    spelet tar över)."""
    if path and os.path.exists(path):
        try:
            if os.path.getsize(path) > MAX_SAVE_BYTES:
                return None
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
        except (OSError, ValueError):
            return None
        if isinstance(d, dict) and d.get('sdk') == 1 and d.get('game') == game_id and isinstance(d.get('data'), dict):
            return d['data']
        return None
    if legacy_path and os.path.exists(legacy_path):
        try:
            if os.path.getsize(legacy_path) > MAX_SAVE_BYTES:
                return None
            with open(legacy_path, encoding='utf-8') as f:
                d = json.load(f)
        except (OSError, ValueError):
            return None
        return d if isinstance(d, dict) else None
    return None


def write_save(path, game_id, data):
    """Skriver sparfilen atomiskt (fsync + rename). Ger True om det lyckades."""
    if not path:
        return True
    try:
        blob = json.dumps({'sdk': 1, 'game': game_id, 'data': data}, separators=(',', ':'), allow_nan=False)
        if len(blob) > MAX_SAVE_BYTES:
            return False
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(blob)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except (OSError, TypeError, ValueError):
        return False


# ---------------------------------------------------------------- spelets omgivning
class GameContext(object):
    """Det panelen ger ett spel när det skapas: tidsloop, ritytan, metadata, sparfil och krokar (refresh, clock, log,
    exit, fail). Spelet rör den inte själv; GameBase använder den."""

    def __init__(self, loop, surface, meta, save_path=None, legacy_path=None, hooks=None, rng=None):
        self.loop = loop
        self.surface = surface
        self.meta = dict(meta)
        self.save_path = save_path if save_path not in (None, '', 'none') else None
        self.legacy_path = legacy_path
        self.hooks = hooks or {}
        self.rng = rng


def merge_rects(rects):
    """Slår ihop överlappande rutor; fler än sex blir en enda."""
    out = [r for r in rects if r[2] > r[0] and r[3] > r[1]]
    changed = True
    while changed and len(out) > 1:
        changed = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                if meets(out[i], out[j]):
                    out[i] = union(out[i], out[j])
                    del out[j]
                    changed = True
                    break
            if changed:
                break
    if len(out) > 6:
        u = None
        for r in out:
            u = union(u, r)
        return [u]
    return out


class GameBase(object):
    """Basklassen för ett spel. Skriv `class Game(sdk.GameBase)` och överskugga det du behöver:

    setup()              nytt spel: sätt allt tillstånd (anropas också om sparfilen var trasig)
    restore(data)        läs sparad data (dict) in i spelet; kasta ett fel, eller ge False, om den är konstig
    state()              ge det som ska sparas (en dict med JSON-vänliga värden) eller None
    paint(img, rect)     rita det som ligger i rutan rect (rutan är redan rensad till bakgrundsfärgen)
    targets()            lista (namn, ruta) eller (namn, ruta, slop) med knappar; första träffen vinner
    on_tap(name)         en knapp i targets() trycktes (tryck och släpp på knappen)
    on_down/on_move/on_up(x, y)   tryck som inte började på en knapp (för dragspel och rutnät)
    on_open() / on_close()        spelet visas / lämnas

    Tjänster: invalidate(rect=None), save_soon(), save_now(), later(namn, sek, fn), cancel(namn), now(), log(...),
    exit(), self.rng, self.pressed (namnet på knappen som trycks ner), self.clock."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.loop = ctx.loop
        self.s = ctx.surface
        self.meta = ctx.meta
        self.hooks = ctx.hooks
        self.rng = ctx.rng or random.Random()
        self.title = self.meta.get('name', '')
        self.pressed = None
        self.touch = None
        self._gen = None
        self._keys = {}
        self._inval = []
        self._timers = {}
        self._save_dirty = False
        self._quarantined = False
        self._back_rect = (16, BACK_Y[0], 16 + 78 + 80, BACK_Y[1])
        self._back_down = False
        self._clock = ''
        self._opened = False
        self.setup()
        self._load_save()

    # ------------------------------------------------------------ för spelet att överskugga
    def setup(self):
        pass

    def restore(self, data):
        pass

    def state(self):
        return None

    def paint(self, img, rect):
        pass

    def targets(self):
        return ()

    def on_tap(self, name):
        pass

    def on_down(self, x, y):
        pass

    def on_move(self, x, y):
        pass

    def on_up(self, x, y):
        pass

    def on_open(self):
        pass

    def on_close(self):
        pass

    # ------------------------------------------------------------ tjänster
    @property
    def clock(self):
        fn = self.hooks.get('clock')
        return fn() if fn is not None else ''

    def now(self):
        """Tiden i sekunder (monoton): för att mäta hur lång tid något tar."""
        return self.loop.time()

    def log(self, *a):
        fn = self.hooks.get('log')
        if fn is not None:
            fn(*a)

    def refresh(self, urgent=False):
        """Be panelen rita om skärmen (urgent: direkt, annars inom en kort stund)."""
        fn = self.hooks.get('refresh')
        if fn is not None:
            fn(urgent)

    def invalidate(self, rect=None, urgent=True):
        """Något i rutan rect (eller hela AREA) har ändrats: paint(img, rect) anropas snart för den rutan."""
        r = AREA if rect is None else clip(rect, AREA)
        if r[2] > r[0] and r[3] > r[1]:
            self._inval.append(r)
        self.refresh(urgent)

    def exit(self):
        """Lämna spelet (tillbaka till spelväljaren)."""
        fn = self.hooks.get('exit')
        if fn is not None:
            fn()

    def later(self, name, delay, fn):
        """Anropar fn() om delay sekunder. Samma namn igen ersätter den väntande. Ett fel i fn tar inte ner panelen."""
        self.cancel(name)

        def run():
            self._timers.pop(name, None)
            try:
                fn()
            except Exception:
                self._fail()

        self._timers[name] = self.loop.call_later(delay, run)

    def cancel(self, name):
        h = self._timers.pop(name, None)
        if h is not None:
            h.cancel()

    def _fail(self):
        fn = self.hooks.get('fail')
        if fn is None:
            raise
        fn()

    # ------------------------------------------------------------ spara
    def save_soon(self):
        """Tillståndet har ändrats: spara inom några sekunder (och alltid när spelet lämnas)."""
        self._save_dirty = True
        if 'save' not in self._timers:
            self._timers['save'] = self.loop.call_later(SAVE_DELAY, self._save_tick)

    def _save_tick(self):
        self._timers.pop('save', None)
        self.save_now()

    def save_now(self, force=False):
        """Sparar direkt om något ändrats (eller alltid med force=True)."""
        h = self._timers.pop('save', None)
        if h is not None:
            h.cancel()
        if self._quarantined:
            return True
        if force:
            self._save_dirty = True
        if not self._save_dirty:
            return True
        self._save_dirty = False
        path = self.ctx.save_path
        if not path:
            return True
        data = self.state()
        if data is None:
            return True
        ok = write_save(path, self.meta.get('id', ''), data)
        if not ok:
            self.log('kunde inte spara spelet (%s)' % path)
        return ok

    def _load_save(self):
        data = read_save(self.ctx.save_path, self.meta.get('id', ''), self.ctx.legacy_path)
        if data is None:
            return
        try:
            ok = self.restore(data)
        except Exception:
            ok = False
            self.log('sparfilen kunde inte läsas, börjar om:\n' + traceback.format_exc())
        if ok is False:
            self._set_aside()
            self.setup()

    def _set_aside(self):
        path = self.ctx.save_path
        if path:
            try:
                os.replace(path, path + '.broken')
            except OSError:
                pass

    # ------------------------------------------------------------ panelens anrop
    def open(self):
        self._opened = True
        self.touch = None
        self.pressed = None
        self._back_down = False
        self._gen = None
        self.on_open()

    def close(self):
        self._opened = False
        for name in list(self._timers):
            if name != 'save':
                self.cancel(name)
        self.touch = None
        self.pressed = None
        self._back_down = False
        self.on_close()
        self.save_now()

    def stop(self):
        for name in list(self._timers):
            self.cancel(name)
        self.save_now()

    def quarantine(self):
        """Efter ett fel i spelet: lägg undan sparfilen och spara inget mer från det här spelet."""
        for name in list(self._timers):
            self.cancel(name)
        self._save_dirty = False
        self._quarantined = True
        self._set_aside()

    # ------------------------------------------------------------ tryck
    def on_touch(self, kind, x, y):
        if kind == 'down':
            self._t_down(x, y)
        elif kind == 'move':
            self._t_move(x, y)
        else:
            self._t_up(x, y)

    def _t_down(self, x, y):
        self.touch = None
        if inside(self._back_rect, x, y, 8):
            self.touch = {'t': 'back', 'inside': True, 'rect': self._back_rect, 'slop': HIT_SLOP}
            self._back_down = True
            self.refresh(True)
            return
        for t in self.targets() or ():
            name, rect = t[0], t[1]
            if inside(rect, x, y):
                self.touch = {'t': name, 'inside': True, 'rect': rect, 'slop': t[2] if len(t) > 2 else HIT_SLOP}
                self.pressed = name
                self.invalidate(rect)
                return
        self.touch = {'t': None}
        self.on_down(x, y)

    def _t_move(self, x, y):
        tc = self.touch
        if tc is None:
            return
        if tc['t'] is None:
            self.on_move(x, y)
            return
        inn = inside(tc['rect'], x, y, tc['slop'])
        if inn == tc['inside']:
            return
        tc['inside'] = inn
        if tc['t'] == 'back':
            self._back_down = inn
            self.refresh(True)
        else:
            self.pressed = tc['t'] if inn else None
            self.invalidate(tc['rect'])

    def _t_up(self, x, y):
        tc, self.touch = self.touch, None
        if tc is None:
            return
        if tc['t'] is None:
            self.on_up(x, y)
            return
        fired = tc['inside'] and inside(tc['rect'], x, y, tc['slop'])
        if tc['t'] == 'back':
            self._back_down = False
            if fired:
                self.exit()
            else:
                self.refresh(True)
            return
        was = self.pressed
        self.pressed = None
        if fired:
            self.invalidate(tc['rect'])
            self.on_tap(tc['t'])
        elif was is not None:
            self.invalidate(tc['rect'])

    # ------------------------------------------------------------ ritning
    def draw(self, gen):
        """Panelen anropar draw(gen) när något ska ritas. gen ändras när hela skärmen ska ritas om."""
        img = self.s.img
        if gen != self._gen:
            self._gen = gen
            self._keys = {}
            self._inval = [AREA]
        self.draw_chrome(img)
        rects, self._inval = merge_rects(self._inval), []
        for r in rects:
            fill(img, r)
            self.paint(img, r)
            self.s.mark(r)

    def draw_chrome(self, img):
        """Rubrikraden och klockan (ritas bara när de ändrats)."""
        self._clock = self.clock
        for name, rect, key, fn in (
                ('head', HEAD_RECT, (self._back_down, self.title), self._paint_head),
                ('clock', CLOCK_RECT, (self._clock,), self._paint_clock)):
            if self._keys.get(name) != key:
                self._keys[name] = key
                fn(img)
                self.s.mark(rect)

    def _paint_head(self, img):
        self._back_rect = paint_head(img, self.title, self._back_down)

    def _paint_clock(self, img):
        paint_clock(img, self._clock)
