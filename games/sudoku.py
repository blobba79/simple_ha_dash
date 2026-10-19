"""Sudoku (en spelfil för dash-panelen, se games/SKAPA-SPEL.md).

Ett rutnät på 9x9 med nio "brunnar" om 3x3 rutor. Varje rad, kolumn och 3x3-ruta ska innehålla 1-9 en gång. De givna
siffrorna är låsta. Trycker man på en tom ruta visas en liten ruta (popup) med siffrorna 1-9, Radera och OK till höger.
Man kan välja upp till fyra siffror i en ruta: en siffra är svaret, två till fyra är små anteckningar. Samma siffra två
gånger i en rad, kolumn eller ruta blir röd. Kontrollera visar vilka svar som är fel; är rutnätet rätt ifyllt är sudokut klart.

Filen har tre delar: Rules (reglerna: ingen ritning), Game (skärmen) och pusseltabellen längst ned (240 pussel, gjorda av
tools/make_sudoku_data.py: varje pussel har exakt en lösning och går att lösa utan att gissa; vid varje nytt spel slumpas
ett pussel om med symmetrier som bevarar det, så att de sällan känns igen).

Sparfilen har samma format som den äldre sudoku.json (spelet tar över den om den finns)."""
import random

from PIL import Image

from dashpanel import gamesdk as sdk

META = {
    'api': 1,
    'id': 'sudoku',
    'name': 'Sudoku',
    'desc': 'Fyll rutnätet med siffrorna 1-9. Tryck på en tom ruta för att välja siffra.',
    'version': 1,
    'legacy_save': '/var/lib/dash-panel/sudoku.json',
}

T = sdk                         # färgerna heter likadant i sdk som i panelens tema
text, bbox, rbox, rbox_mask, blend, icon, wrap = sdk.text, sdk.bbox, sdk.rbox, sdk.rbox_mask, sdk.blend, sdk.icon, sdk.wrap
HEAD_RECT, CLOCK_RECT = sdk.HEAD_RECT, sdk.CLOCK_RECT
centered, clear, inside, thousands = sdk.centered, sdk.fill, sdk.inside, sdk.thousands
paint_head, paint_clock = sdk.paint_head, sdk.paint_clock


# ================================================================ reglerna
N = 9
CELLS = 81
MAX_DIGITS = 4              # så många siffror får stå i en ruta (en = svaret, flera = anteckningar)
SAVE_VERSION = 1            # (fältet 'notes' tillkom senare men är valfritt: äldre filer läses och nya läses av äldre kod)

ROW = [i // 9 for i in range(CELLS)]
COL = [i % 9 for i in range(CELLS)]
BOX = [(i // 27) * 3 + (i % 9) // 3 for i in range(CELLS)]
UNITS = ([[r * 9 + c for c in range(9)] for r in range(9)]
         + [[r * 9 + c for r in range(9)] for c in range(9)]
         + [[(br * 3 + r) * 9 + bc * 3 + c for r in range(3) for c in range(3)] for br in range(3) for bc in range(3)])
PEERS = []
for _i in range(CELLS):
    _p = set()
    for _u in UNITS:
        if _i in _u:
            _p.update(_u)
    _p.discard(_i)
    PEERS.append(tuple(sorted(_p)))


def _digits81(s):
    """81 siffror 0-9 ur en sträng, eller None."""
    if not isinstance(s, str) or len(s) != CELLS or any(ch not in '0123456789' for ch in s):
        return None
    return [int(ch) for ch in s]


def _full_grid_ok(g):
    return all(sorted(g[i] for i in u) == list(range(1, 10)) for u in UNITS)


def _axis_perm(rng):
    """Ny ordning av de nio raderna (eller kolumnerna): grupperna om tre byter plats och inom varje grupp byter de
    tre plats."""
    groups = [0, 1, 2]
    rng.shuffle(groups)
    out = []
    for g in groups:
        inner = [0, 1, 2]
        rng.shuffle(inner)
        out.extend(g * 3 + k for k in inner)
    return out


def transform(puzzle, solution, rng):
    """(pussel, lösning) omslumpade med symmetrier. Pusslet har fortfarande exakt en lösning, den nya lösningen."""
    digit = list(range(1, 10))
    rng.shuffle(digit)
    rows, cols = _axis_perm(rng), _axis_perm(rng)
    flip = rng.random() < 0.5
    p2, s2 = [0] * CELLS, [0] * CELLS
    for r in range(9):
        for c in range(9):
            src = (cols[c] * 9 + rows[r]) if flip else (rows[r] * 9 + cols[c])
            d = puzzle[src]
            p2[r * 9 + c] = digit[d - 1] if d else 0
            s2[r * 9 + c] = digit[solution[src] - 1]
    return p2, s2


def _notes_ok(raw, given, cur):
    """Anteckningarna ur en sparfil (ett uppslag 'ruta' -> 'siffror') som lista med 81 tuplar, eller None om något är
    fel: ruta utanför brädet, given eller ifylld ruta, färre än två eller fler än fyra siffror, siffror som inte är
    1-9 i stigande ordning utan upprepning."""
    if raw is None:
        return [()] * CELLS
    if not isinstance(raw, dict):
        return None
    notes = [()] * CELLS
    for k, v in raw.items():
        if not isinstance(k, str) or not k.isdigit() or str(int(k)) != k or not isinstance(v, str):
            return None
        i = int(k)
        if i >= CELLS or given[i] or cur[i]:
            return None
        if not (2 <= len(v) <= MAX_DIGITS) or any(ch not in '123456789' for ch in v):
            return None
        ds = tuple(int(ch) for ch in v)
        if list(ds) != sorted(set(ds)):
            return None
        notes[i] = ds
    return notes


class Rules(object):
    """Ett sudoku: givna siffror, spelarens siffror och anteckningar och (för kontrollen) den rätta lösningen."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.given = [0] * CELLS
        self.cur = [0] * CELLS
        self.notes = [()] * CELLS   # anteckningarna (2-4 siffror, stigande) i rutor utan svar
        self.sol = [0] * CELLS
        self.moves = 0
        self.done = False
        self.solved = 0             # antal klarade sudokun (sparas, nollställs inte av nytt spel)
        self.new()

    def new(self):
        entry = PUZZLES[self.rng.randrange(len(PUZZLES))]
        puz_s, sol_s = entry.split(':')
        puz, sol = transform([int(ch) for ch in puz_s], [int(ch) for ch in sol_s], self.rng)
        self.given = puz
        self.cur = list(puz)
        self.notes = [()] * CELLS
        self.sol = sol
        self.moves = 0
        self.done = False

    # ------------------------------------------------------------ frågor
    def editable(self, i):
        return not self.done and 0 <= i < CELLS and self.given[i] == 0

    def digits(self, i):
        """Siffrorna som står i ruta i, stigande: svaret (en siffra) eller anteckningarna (noll till fyra)."""
        return (self.cur[i],) if self.cur[i] else self.notes[i]

    def has_notes(self):
        return any(self.notes)

    def empty_count(self):
        """Rutor utan svar (en ruta med bara anteckningar räknas som tom)."""
        return self.cur.count(0)

    def remaining(self, d):
        """Hur många siffror d som ännu ska läggas (9 minus de som ligger i rutnätet; aldrig under noll)."""
        return max(0, 9 - self.cur.count(d))

    def conflicts(self):
        """Index för rutor vars siffra finns på en ruta till i samma rad, kolumn eller 3x3-ruta."""
        bad = set()
        for u in UNITS:
            seen = {}
            for i in u:
                d = self.cur[i]
                if d:
                    seen.setdefault(d, []).append(i)
            for idx in seen.values():
                if len(idx) > 1:
                    bad.update(idx)
        return bad

    def wrong(self):
        """Index för rutor där spelaren skrivit en siffra som inte är den rätta (för knappen Kontrollera)."""
        return [i for i in range(CELLS) if self.cur[i] and self.cur[i] != self.sol[i]]

    def is_solved(self):
        return 0 not in self.cur and not self.conflicts()

    # ------------------------------------------------------------ drag
    def _store(self, i, ds):
        """Lägger siffrorna ds i ruta i: en siffra blir svaret, två till fyra anteckningar, ingen tömmer rutan."""
        ds = tuple(sorted(ds))
        if len(ds) == 1:
            self.cur[i], self.notes[i] = ds[0], ()
        else:
            self.cur[i], self.notes[i] = 0, ds
        self.moves += 1
        if self.is_solved():
            self.done = True
            self.solved += 1

    @staticmethod
    def _digit_ok(d, lo):
        return isinstance(d, int) and not isinstance(d, bool) and lo <= d <= 9

    def put(self, i, d):
        """Gör siffran d (1-9) till rutans enda innehåll (svaret); 0 tömmer rutan, anteckningar med. Ger True om något
        ändrades. Givna rutor och ett färdigt sudoku går inte att ändra."""
        if not self._digit_ok(d, 0) or not self.editable(i):
            return False
        target = (d,) if d else ()
        if self.digits(i) == target:
            return False
        self._store(i, target)
        return True

    def toggle(self, i, d):
        """Lägger till siffran d (1-9) i ruta i, eller tar bort den om den redan står där. Högst MAX_DIGITS siffror
        får stå i en ruta. Ger True om något ändrades."""
        if not self._digit_ok(d, 1) or not self.editable(i):
            return False
        ds = set(self.digits(i))
        if d in ds:
            ds.discard(d)
        elif len(ds) >= MAX_DIGITS:
            return False
        else:
            ds.add(d)
        self._store(i, ds)
        return True

    # ------------------------------------------------------------ lagring
    def to_dict(self):
        return {'given': ''.join(map(str, self.given)), 'cur': ''.join(map(str, self.cur)),
                'sol': ''.join(map(str, self.sol)), 'moves': self.moves,
                'notes': dict((str(i), ''.join(map(str, ds))) for i, ds in enumerate(self.notes) if ds)}

    def load_dict(self, d):
        """Läser ett sparat spel. Ger False (och rör inget) om något är fel eller konstigt."""
        try:
            given, cur, sol = _digits81(d['given']), _digits81(d['cur']), _digits81(d['sol'])
            if given is None or cur is None or sol is None:
                return False
            if 0 in sol or not _full_grid_ok(sol):
                return False
            for i in range(CELLS):
                if given[i] and given[i] != sol[i]:
                    return False
                if given[i] and cur[i] != given[i]:
                    return False
            moves = int(d.get('moves', 0))
            if moves < 0:
                return False
            notes = _notes_ok(d.get('notes'), given, cur)
            if notes is None:
                return False
        except (KeyError, TypeError, ValueError, AttributeError):
            return False
        self.given, self.cur, self.sol, self.moves, self.notes = given, cur, sol, moves, notes
        self.done = self.is_solved()            # flaggan sparas inte: den räknas ut (och räknar inte upp 'solved')
        return True


# ---------------------------------------------------------------- sparformat
def dump_data(game):
    """Det som sparas: antal klarade och det pågående spelet (samma format som den äldre sudoku.json)."""
    return {'v': SAVE_VERSION, 'solved': game.solved, 'state': game.to_dict()}


def load_data(game, d):
    """Läser sparad data in i game. Ger False om den inte alls går att läsa (fel version eller form)."""
    if not isinstance(d, dict) or d.get('v') != SAVE_VERSION:
        return False
    n = d.get('solved')
    if isinstance(n, int) and not isinstance(n, bool) and n > 0:
        game.solved = n
    st = d.get('state')
    if isinstance(st, dict):
        game.load_dict(st)
    return True


# ---------------------------------------------------------------- spelväljarens rad och ikon
def status(data):
    """Raden under namnet i spelväljaren: pågående spel (rutor kvar) eller antal klarade."""
    if not data:
        return None
    g = Rules(random.Random(0))
    if not load_data(g, data):
        return None
    if not (g.done or g.moves == 0):
        left = g.empty_count()
        return 'Pågående spel · %d %s kvar' % (left, 'ruta' if left == 1 else 'rutor'), True
    return ('Klarade sudokun: %s' % thousands(g.solved), False) if g.solved else None


_ICON_ART = ((5, False), (0, False), (3, False),        # 3x3 rutor: (siffra, vald)
             (0, False), (7, True), (0, False),
             (8, False), (0, False), (1, False))


def draw_icon(im):
    """Ikonen (128x128): tre gånger tre rutor med några siffror, en vald."""
    pitch, size = 44, 40
    off = (sdk.ICON - (3 * pitch - (pitch - size))) // 2
    for k, (d, sel) in enumerate(_ICON_ART):
        x, y = off + (k % 3) * pitch, off + (k // 3) * pitch
        if sel:
            bbox(im, x, y, x + size, y + size, 8, T.BLUE_D, T.BLUE, 2)
        else:
            rbox(im, x, y, x + size, y + size, 8, TILE_BG)
        if d:
            centered(im, x + size // 2, y + 29, str(d), 500, 24, T.BLUE_L if sel else T.TEXT)


# ================================================================ skärmen
# ---------------------------------------------------------------- mått
CARD = (24, 84, 504, 564)               # kortet runt brädet
WELL, WELL_GAP, WELL_PAD = 150, 6, 4    # en 3x3-brunn, luften mellan brunnarna och luften inne i brunnen
BX0, BY0 = 33, 93                       # övre vänstra hörnet av första brunnen
TILE, TILE_GAP = 46, 2                  # en ruta och luften mellan rutor i samma brunn
RIGHT_RECT = (528, 84, 1008, 564)
STAT_RECT = (528, 100, 1008, 226)
INFO_RECT = (528, 240, 1008, 468)
CHECK_RECT = (528, 484, 764, 564)
NEW_RECT = (780, 484, 1008, 564)
AGAIN_RECT = (104, 410, 424, 478)       # "Nytt spel" på brädet när sudokut är klart

POP_RECT = (570, 100, 966, 542)         # rutan med siffror
KEY_W, KEY_H, KEY_GAP = 112, 80, 10
KEYS_X0, KEYS_Y0 = POP_RECT[0] + 20, POP_RECT[1] + 86
_ROW_Y = KEYS_Y0 + 3 * KEY_H + 2 * KEY_GAP + 12
_HALF = (3 * KEY_W + 2 * KEY_GAP - KEY_GAP) // 2
ERASE_RECT = (KEYS_X0, _ROW_Y, KEYS_X0 + _HALF, _ROW_Y + 64)
OK_RECT = (KEYS_X0 + _HALF + KEY_GAP, _ROW_Y, KEYS_X0 + 2 * _HALF + KEY_GAP, _ROW_Y + 64)

HIT_SLOP = 16                           # så långt fingret får glida från en knapp och ändå trycka på den
CELL_SLOP = 8                           # och från en ruta på brädet (rutorna sitter tätt)
MSG_SECONDS = 7.0
CONFIRM_SECONDS = 3.0
OVER_GUARD = 1.0                        # så länge efter att sudokut blivit klart ignoreras tryck på "Nytt spel"

WELL_BG = (0x15, 0x15, 0x15)
TILE_BG = (0x2b, 0x2b, 0x2b)
TILE_PEER = (0x3a, 0x3a, 0x3a)
NOTE_SIZE = 18                          # anteckningarnas siffror i en ruta: 2x2, stigande
NOTE_DX = (12, 34)
NOTE_DY = (21, 41)
NOTE_COLOR = (0x9f, 0xc4, 0xd8)
POP_HINTS = ('Välj upp till 4 siffror', 'En siffra är svaret', 'Flera siffror är anteckningar', 'Fyra är max: ta bort en för att byta')


def tile_xy(i):
    r, c = divmod(i, 9)
    return (BX0 + (c // 3) * (WELL + WELL_GAP) + WELL_PAD + (c % 3) * (TILE + TILE_GAP),
            BY0 + (r // 3) * (WELL + WELL_GAP) + WELL_PAD + (r % 3) * (TILE + TILE_GAP))


def tile_rect(i):
    x, y = tile_xy(i)
    return (x, y, x + TILE, y + TILE)


def key_rect(d):
    r, c = divmod(d - 1, 3)
    x = KEYS_X0 + c * (KEY_W + KEY_GAP)
    y = KEYS_Y0 + r * (KEY_H + KEY_GAP)
    return (x, y, x + KEY_W, y + KEY_H)


# ---------------------------------------------------------------- förrenderade rutor
_tiles = {}
_STYLES = {
    'normal': (TILE_BG, None),
    'peer': (TILE_PEER, None),
    'sel': (T.BLUE_D, T.BLUE),
    'bad': (T.RED_D, None),
    'wrong': (T.RED_D, T.RED),
}


def tile_sprite(style, pressed=False):
    """En ruta på brädet (46x46, med brunnens färg runt de rundade hörnen)."""
    key = (style, pressed)
    hit = _tiles.get(key)
    if hit is not None:
        return hit
    fill, border = _STYLES[style]
    if pressed:
        fill = blend(fill, (255, 255, 255), 0.10)
    img = Image.new('RGB', (TILE, TILE), WELL_BG)
    if border:
        bbox(img, 0, 0, TILE, TILE, 9, fill, border, 2)
    else:
        rbox(img, 0, 0, TILE, TILE, 9, fill)
    _tiles[key] = img
    return img


_frame = []


def frame_image():
    """Kortet med de nio brunnarna (förrenderat en gång)."""
    if _frame:
        return _frame[0]
    w, h = CARD[2] - CARD[0], CARD[3] - CARD[1]
    im = Image.new('RGB', (w, h), T.BG)
    bbox(im, 0, 0, w, h, 18, T.CARD, T.CARD_BORDER, 1)
    for br in range(3):
        for bc in range(3):
            x = BX0 - CARD[0] + bc * (WELL + WELL_GAP)
            y = BY0 - CARD[1] + br * (WELL + WELL_GAP)
            rbox(im, x, y, x + WELL, y + WELL, 12, WELL_BG)
    _frame.append(im)
    return im


def button(img, rect, label, fill, border, bw, pressed, icon_name=None, icon_color=None, size=24):
    x0, y0, x1, y1 = rect
    if pressed:
        fill = blend(fill, (255, 255, 255), 0.09)
    bbox(img, x0, y0, x1, y1, 20, fill, border, bw)
    base = y0 + (y1 - y0) // 2 + 9
    if icon_name:
        icon(img, icon_name, 40, x0 + 22, y0 + (y1 - y0 - 40) // 2, icon_color)
        text(img, x0 + 78, base, label, 500, size, T.TEXT)
    else:
        centered(img, (x0 + x1) // 2, base, label, 500, size, T.TEXT)


class Game(sdk.GameBase):
    """Hela sudokuts skärm och pek. Panelen anropar draw(gen) och on_touch(kind, x, y) medan det visas.
    (Ett "avancerat" spel: egen ritning med en nyckel per ruta och egen pekhantering; GameBase sköter tidtagare,
    sparfil, krokar och felskydd.)"""

    def setup(self):
        self.game = Rules(self.rng)
        self.sel = None                 # vald ruta (rutan med siffror visas) eller None
        self.msg = None                 # (rubrik, färg, text) efter Kontrollera
        self.show_wrong = False         # rutor med fel siffra är markerade (efter Kontrollera)
        self.confirm_new = False
        self.over_at = None

    # ------------------------------------------------------------ in och ut, spara
    def on_open(self):
        self._reset_ui()
        if self.game.done:
            self.over_at = self.loop.time()

    def on_close(self):
        self._reset_ui()

    def _reset_ui(self):
        self.sel = None
        self.pressed = None
        self.touch = None
        self.msg = None
        self.show_wrong = False
        self.confirm_new = False

    def state(self):
        return dump_data(self.game)

    def restore(self, data):
        return load_data(self.game, data)

    # ------------------------------------------------------------ pek
    def _rect_of(self, name):
        kind = name[0]
        if kind == 'back':
            return self._back_rect
        if kind == 'cell':
            return tile_rect(name[1])
        if kind == 'key':
            return key_rect(name[1])
        return {'again': AGAIN_RECT, 'new': NEW_RECT, 'check': CHECK_RECT, 'erase': ERASE_RECT,
                'ok': OK_RECT}.get(kind)

    def _hit(self, x, y):
        """Namnet på det som ligger under fingret, eller None."""
        g = self.game
        if inside(self._back_rect, x, y, 8):
            return ('back',)
        if g.done:
            if inside(AGAIN_RECT, x, y):
                if self.over_at is not None and self.loop.time() - self.over_at < OVER_GUARD:
                    return None
                return ('again',)
            if inside(NEW_RECT, x, y):
                return ('new',)
            return None
        if self.sel is not None:
            for d in range(1, 10):
                if inside(key_rect(d), x, y) and self._key_enabled(d):
                    return ('key', d)
            if g.digits(self.sel) and inside(ERASE_RECT, x, y):
                return ('erase',)
            if inside(OK_RECT, x, y):
                return ('ok',)
        else:
            if inside(CHECK_RECT, x, y):
                return ('check',)
            if inside(NEW_RECT, x, y):
                return ('new',)
        best = None
        for i in range(CELLS):
            if inside(tile_rect(i), x, y, CELL_SLOP):
                x0, y0, x1, y1 = tile_rect(i)
                dist = abs(x - (x0 + x1) / 2.0) + abs(y - (y0 + y1) / 2.0)
                if best is None or dist < best[0]:
                    best = (dist, i)
        if best is not None:
            return ('cell', best[1])
        return None

    def _key_enabled(self, d):
        """Siffran d går att trycka på: den står redan i rutan (tryck tar bort den), eller det finns plats för en till
        och det finns någon d kvar att lägga."""
        g = self.game
        if self.sel is None:
            return False
        ds = g.digits(self.sel)
        return d in ds or (len(ds) < MAX_DIGITS and g.remaining(d) > 0)

    def on_touch(self, kind, x, y):
        if kind == 'down':
            self._down(x, y)
        elif kind == 'move':
            self._move(x, y)
        else:
            self._up(x, y)

    def _down(self, x, y):
        self.touch = None
        name = self._hit(x, y)
        if name is not None:
            self.touch = {'t': name, 'inside': True}
            self.pressed = name
            self.refresh(urgent=True)
        elif self.sel is not None and not inside(POP_RECT, x, y) and not self.game.done:
            self.touch = {'t': ('dismiss',), 'inside': True}        # tryck utanför rutan stänger den

    def _move(self, x, y):
        tc = self.touch
        if tc is None or tc['t'][0] == 'dismiss':
            return
        rect = self._rect_of(tc['t'])
        if rect is None:
            return
        inn = inside(rect, x, y, CELL_SLOP if tc['t'][0] == 'cell' else HIT_SLOP)
        if inn != tc['inside']:
            tc['inside'] = inn
            self.pressed = tc['t'] if inn else None
            self.refresh(urgent=True)

    def _up(self, x, y):
        tc, self.touch = self.touch, None
        if tc is None:
            return
        name = tc['t']
        was = self.pressed is not None
        self.pressed = None
        if name[0] == 'dismiss':
            self._select(None)
            return
        rect = self._rect_of(name)
        if rect is not None and tc['inside'] and inside(rect, x, y, CELL_SLOP if name[0] == 'cell' else HIT_SLOP):
            self._activate(name)
        elif was:
            self.refresh(urgent=True)

    def _activate(self, name):
        kind = name[0]
        g = self.game
        if kind == 'back':
            self.exit()
        elif kind == 'cell':
            i = name[1]
            if g.done:
                return
            self._select(None if (i == self.sel or not g.editable(i)) else i)
        elif kind == 'key':
            self._toggle(name[1])
        elif kind == 'erase':
            self._erase()
        elif kind == 'ok':
            self._select(None)
        elif kind == 'check':
            self._check()
        elif kind == 'new':
            if g.done or g.moves == 0 or self.confirm_new:
                self._new_game()
            else:
                self.confirm_new = True
                self.later('confirm', CONFIRM_SECONDS, self._confirm_end)
                self.refresh(urgent=True)
        elif kind == 'again':
            self._new_game()

    def _select(self, i):
        self.sel = i
        self.refresh(urgent=True)

    def _toggle(self, d):
        """Lägger siffran d i den valda rutan, eller tar bort den om den redan står där. Siffer-rutan ligger kvar (så
        att man kan välja fler) tills man trycker OK; väljer man den fjärde siffran, eller sudokut blir klart, stängs
        den av sig själv."""
        g = self.game
        i = self.sel
        if i is None:
            return
        if g.toggle(i, d):
            self._board_changed()
        if g.done or len(g.digits(i)) >= MAX_DIGITS:
            self.sel = None
        self.refresh(urgent=True)

    def _erase(self):
        """Tömmer den valda rutan (svar och anteckningar). Siffer-rutan ligger kvar för nya siffror."""
        i = self.sel
        if i is None:
            return
        if self.game.put(i, 0):
            self._board_changed()
        self.refresh(urgent=True)

    def _board_changed(self):
        g = self.game
        self.msg = None
        self.show_wrong = False
        self.confirm_new = False
        self.cancel('msg')
        self.cancel('confirm')
        if g.done:
            self.over_at = self.loop.time()
            self.save_now(force=True)
        else:
            self.save_soon()

    def _check(self):
        wrong = self.game.wrong()
        if not wrong:
            self.show_wrong = False
            sub = 'Allt du skrivit in stämmer. Fortsätt så här!'
            if self.game.has_notes():
                sub = 'Allt du skrivit in stämmer (anteckningar kontrolleras inte). Fortsätt så här!'
            self.msg = ('Inga fel hittills', T.GREEN, sub)
        else:
            self.show_wrong = True
            n = len(wrong)
            self.msg = ('%d %s är fel' % (n, 'ruta' if n == 1 else 'rutor'), T.RED,
                        'De är markerade med röd kant. Tryck på en av dem för att skriva en annan siffra.')
        self.later('msg', MSG_SECONDS, self._msg_end)
        self.refresh(urgent=True)

    def _msg_end(self):
        self._timers.pop('msg', None)
        if self.msg is not None or self.show_wrong:
            self.msg = None
            self.show_wrong = False
            self.refresh()

    def _confirm_end(self):
        self._timers.pop('confirm', None)
        if self.confirm_new:
            self.confirm_new = False
            self.refresh()

    def _new_game(self):
        for name in ('confirm', 'msg'):
            self.cancel(name)
        self._reset_ui()
        self.over_at = None
        self.game.new()
        self.save_now(force=True)
        self.refresh(urgent=True)

    # ------------------------------------------------------------ ritning
    def draw(self, gen):
        """Ritar det som ändrats sedan sist. gen ändras när hela skärmen ska ritas om."""
        img = self.s.img
        if gen != self._gen:
            self._gen = gen
            self._keys = {}
        g = self.game
        self._clock = self.clock
        conflicts = g.conflicts()
        wrong = set(g.wrong()) if self.show_wrong else set()
        sel = self.sel
        peers = set(PEERS[sel]) if sel is not None else set()
        mode = 'done' if g.done else ('pop' if sel is not None else 'idle')

        def part(name, rect, key, paint):
            if self._keys.get(name) == key:
                return False
            self._keys[name] = key
            paint(img, rect)
            self.s.mark(rect)
            return True

        part('head', HEAD_RECT, (self.pressed == ('back',),), self._paint_head)
        part('clock', CLOCK_RECT, (self._clock,), lambda im, r: paint_clock(im, self._clock))
        over_key = (g.done, self.pressed == ('again',), g.solved)
        # (mörkläggningen ligger ovanpå brädet: ändras den ritas brädet om under den, annars mörknar det för varje gång)
        if part('frame', CARD, over_key, self._paint_frame):
            for i in range(CELLS):
                self._keys.pop(('c', i), None)
        for i in range(CELLS):
            if i == sel:
                style = 'sel'
            elif i in wrong:
                style = 'wrong'
            elif i in conflicts:
                style = 'bad'
            elif i in peers:
                style = 'peer'
            else:
                style = 'normal'
            key = (style, g.cur[i], g.given[i] != 0, i in conflicts or i in wrong, self.pressed == ('cell', i), g.done,
                   g.notes[i])
            part(('c', i), tile_rect(i), key, lambda im, r, i=i, key=key: self._paint_tile(im, i, key))
        part('over', CARD, over_key, self._paint_over)
        if part('mode', RIGHT_RECT, (mode,), lambda im, r: clear(im, r)):
            for name in ('stat', 'info', 'check', 'new', 'pop'):
                self._keys.pop(name, None)
        if mode == 'pop':
            ds = g.digits(sel)
            rem = tuple(g.remaining(d) for d in range(1, 10))
            pk = self.pressed if (self.pressed and self.pressed[0] in ('key', 'erase', 'ok')) else None
            part('pop', POP_RECT, (sel, ds, rem, pk), self._paint_pop)
        else:
            part('stat', STAT_RECT, (g.empty_count(), g.solved), self._paint_stat)
            info = self._info(conflicts)
            part('info', INFO_RECT, info, self._paint_info)
            if mode == 'idle':
                part('check', CHECK_RECT, (self.pressed == ('check',),), self._paint_check)
            part('new', NEW_RECT, (self.pressed == ('new',), self.confirm_new, g.done), self._paint_new)

    # --- delar
    def _paint_head(self, img, rect):
        self._back_rect = paint_head(img, self.title, self.pressed == ('back',))

    def _paint_frame(self, img, rect):
        img.paste(frame_image(), (CARD[0], CARD[1]))

    def _paint_tile(self, img, i, key):
        style, d, given, bad, pressed, done, notes = key
        x, y = tile_xy(i)
        img.paste(tile_sprite(style, pressed), (x, y))
        if d:
            if bad:
                col = T.RED
            elif given:
                col = T.TEXT
            else:
                col = T.BLUE_L
            centered(img, x + TILE // 2, y + 33, str(d), 500 if given else 400, 30, col)
        for k, nd in enumerate(notes):          # anteckningar: små siffror, två och två, stigande
            centered(img, x + NOTE_DX[k % 2], y + NOTE_DY[k // 2], str(nd), 500, NOTE_SIZE, NOTE_COLOR)

    def _paint_over(self, img, rect):
        g = self.game
        if not g.done:
            return
        w, h = CARD[2] - CARD[0], CARD[3] - CARD[1]
        dark = rbox_mask(w, h, 18).point([int(i * 0.93) for i in range(256)])
        img.paste((0, 0, 0), (CARD[0], CARD[1]), dark)
        cx = (CARD[0] + CARD[2]) // 2
        centered(img, cx, 222, 'Klart!', 500, 56, T.GREEN)
        centered(img, cx, 276, 'Du löste sudokut', 400, 24, T.TEXT)
        centered(img, cx, 330, 'Klarade sudokun: %s' % thousands(g.solved), 400, 20, T.MUTED)
        button(img, AGAIN_RECT, 'Nytt spel', T.BLUE_D, T.BLUE, 2, self.pressed == ('again',))

    def _info(self, conflicts):
        g = self.game
        if g.done:
            return ('Klart!', T.GREEN, 'Tryck på Nytt spel när du vill ha ett nytt sudoku.')
        if self.msg:
            return self.msg
        if conflicts:
            return ('Samma siffra två gånger', T.WARN, 'De röda siffrorna finns redan i samma rad, kolumn eller ruta.')
        return ('Välj en tom ruta', T.TEXT, 'Tryck på en tom ruta och välj siffra. Väljer du flera (högst fyra) blir de '
                                            'små anteckningar i rutan. Tryck OK när du är klar.')

    def _paint_stat(self, img, rect):
        g = self.game
        clear(img, rect)
        x0, y0, x1, y1 = rect
        bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
        text(img, x0 + 24, y0 + 36, 'Rutor kvar', 400, 15, T.MUTED)
        text(img, x0 + 22, y0 + 100, str(g.empty_count()), 300, 60, T.TEXT)
        text(img, x1 - 24, y0 + 36, 'Klarade sudokun', 400, 15, T.MUTED, anchor='rs')
        text(img, x1 - 24, y0 + 98, thousands(g.solved), 400, 40, T.TEXT, anchor='rs')

    def _paint_info(self, img, rect):
        title, color, sub = self._info(self.game.conflicts())
        clear(img, rect)
        x0, y0, x1, y1 = rect
        bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
        text(img, x0 + 28, y0 + 72, title, 500, 32, color)
        lines = wrap(sub, 400, 19, x1 - x0 - 56)
        for k, line in enumerate(lines[:4]):
            text(img, x0 + 28, y0 + 118 + k * 28, line, 400, 19, T.MUTED)

    def _paint_check(self, img, rect):
        clear(img, rect)
        button(img, rect, 'Kontrollera', T.CARD, T.CARD_BORDER, 1, self.pressed == ('check',))

    def _paint_new(self, img, rect):
        clear(img, rect)
        g = self.game
        if self.confirm_new:
            fill, border, label, bw = T.WARN_D, T.WARN_BORDER, 'Tryck igen', 2
        elif g.done:
            fill, border, label, bw = T.BLUE_D, T.BLUE, 'Nytt spel', 2
        else:
            fill, border, label, bw = T.CARD, T.CARD_BORDER, 'Nytt spel', 1
        button(img, rect, label, fill, border, bw, self.pressed == ('new',), size=22)

    def _paint_pop(self, img, rect):
        g = self.game
        sel = self.sel
        ds = g.digits(sel)
        clear(img, rect)                # de rundade hörnen blandas mot det som ligger under: rensa först
        x0, y0, x1, y1 = rect
        bbox(img, x0, y0, x1, y1, 22, T.CARD, T.BLUE, 2)
        text(img, x0 + 24, y0 + 46, 'Välj siffror', 500, 24, T.TEXT)
        text(img, x1 - 24, y0 + 44, 'Rad %d, kolumn %d' % (sel // 9 + 1, sel % 9 + 1), 400, 16, T.MUTED, anchor='rs')
        text(img, x0 + 24, y0 + 72, POP_HINTS[(0, 1, 2, 2, 3)[len(ds)]], 400, 16, T.MUTED)
        for d in range(1, 10):
            kr = key_rect(d)
            left = g.remaining(d)
            enabled = self._key_enabled(d)
            chosen = d in ds
            pressed = self.pressed == ('key', d)
            if chosen:
                fill, border, dcol = T.BLUE_BG, T.BLUE, T.TEXT
            elif enabled:
                fill, border, dcol = T.BTN_BG, T.CARD_BORDER, T.TEXT
            else:
                fill, border, dcol = T.CARD, T.CARD_BORDER, T.STALE_TEXT
            if pressed and enabled:
                fill = blend(fill, (255, 255, 255), 0.10)
            bbox(img, kr[0], kr[1], kr[2], kr[3], 16, fill, border, 2 if chosen else 1)
            cx = (kr[0] + kr[2]) // 2
            centered(img, cx, kr[1] + 46, str(d), 500, 38, dcol)
            if left > 0:
                centered(img, cx, kr[1] + 68, '%d kvar' % left, 400, 13, T.MUTED)
            else:
                centered(img, cx, kr[1] + 68, 'klar', 400, 13, T.GREEN if enabled or chosen else blend(T.GREEN, T.CARD, 0.45))
        can_erase = bool(ds)
        er = ERASE_RECT
        fill, border = (T.RED_D, T.RED_BORDER) if can_erase else (T.CARD, T.CARD_BORDER)
        if self.pressed == ('erase',) and can_erase:
            fill = blend(fill, (255, 255, 255), 0.09)
        bbox(img, er[0], er[1], er[2], er[3], 16, fill, border, 1)
        centered(img, (er[0] + er[2]) // 2, er[1] + 40, 'Radera', 500, 22, T.TEXT if can_erase else T.STALE_TEXT)
        ok = OK_RECT
        fill = T.BLUE_D
        if self.pressed == ('ok',):
            fill = blend(fill, (255, 255, 255), 0.09)
        bbox(img, ok[0], ok[1], ok[2], ok[3], 16, fill, T.BLUE, 2)
        centered(img, (ok[0] + ok[2]) // 2, ok[1] + 40, 'OK', 500, 24, T.TEXT)


# ================================================================ pussel
# GENERERAD av tools/make_sudoku_data.py: ändra inte för hand mellan PUZZLES BEGIN och PUZZLES END.
# Varje rad är "pussel:lösning", 81 + 81 siffror (0 = tom ruta). Alla pussel har exakt en lösning, går att lösa utan att
# gissa och har 38-44 givna siffror.
# PUZZLES BEGIN
PUZZLES = (
    '520000706071030000640257900060015380010328070038670020006591043000040860304000097:529184736871936452643257918267415389915328674438679521786591243192743865354862197',
    '120385006006712000000090002200050497430207051875040003600030000000521600500674019:127385946946712538358496172261853497439267851875149263614938725793521684582674319',
    '056040790108009050907130040490053007500824009600970024060087905030500408015090270:356248791148769352927135846492653187571824639683971524264387915739512468815496273',
    '000240090970008026601000004798605002103407809500801637400000105310700048050084000:835246791974518326621973584798635412163427859542891637489362175316759248257184963',
    '700500390300680125020340070654090037000000000930060251080056010195073002076004003:768521394349687125521349678654192837812735946937468251483256719195873462276914583',
    '004736000300102746600509002210090800008000200003020019500203004142908007000451600:824736951359182746671549382215694873498317265763825419586273194142968537937451628',
    '100502009000701023050490108003065780000308000015920300704013090920604000500209006:187532649649781523352496178493165782276348951815927364764813295921654837538279416',
    '200508300030000825870043069500089730000000000083620004760130052359000080002805003:296518347134976825875243169521489736647351298983627514768134952359762481412895673',
    '400750831000040002501300649706500084300614005940003206864007503100060000259038007:492756831683941752571382649716529384328614975945873216864197523137265498259438167',
    '400002096002100480510094720050460200000317000007085010061970042074001300920600001:483752196792136485516894723158469237249317658637285914361978542874521369925643871',
    '076024900200000004403007800107450098502080107380079205005700402700000009008640730:876524913219863574453917826167452398592386147384179265635791482741238659928645731',
    '940310000103704000507020030802037510030000020014850603070040806000108302000073049:946315287123784965587926431892637514635491728714852693371249856459168372268573149',
    '684900017002407509900000084009610028800000003140028600250000006403701800790005431:684952317312487569975136284539614728826579143147328695251843976463791852798265431',
    '802004076000070403704900015270009160005806700086700059940005307608090000350400602:832154976519678423764932815273549168195826734486713259941265387628397541357481692',
    '709680200185029006000735800416000000900000008000000513004518000500240387008097105:739681254185429736642735891416853972953172468827964513374518629591246387268397145',
    '470208593009304106100067800921003000007000400000700319002640007603809200794502081:476218593289354176135967842921483765367195428548726319852641937613879254794532681',
    '000140536508002000360750810970084160003507400081960057032095041000300905159026000:297148536518632794364759812975284163623517489481963257732895641846371925159426378',
    '508069030100503700003140600409750021012000570850021906004012300001905008080630209:578269134146583792293147685439756821612498573857321946964812357321975468785634219',
    '094000807020708500000195002009000403476823195203000700100954000005602080907000250:594236817621748539738195642819567423476823195253419768182954376345672981967381254',
    '209700060740806100600004007067020804008407300401060270100500009004602081050009702:219735468745896123683214957567321894928457316431968275172583649394672581856149732',
    '427090003951807402000040500600010320270653041043080006009020000504308279300070614:427596183951837462836142597695714328278653941143289756769421835514368279382975614',
    '090460013060530004130007026000270300210394058005018000850700032600053070470029060:598462713762531984134987526986275341217394658345618297859746132621853479473129865',
    '890004020004062080320000690502010030640357019030020705015000072080290100060700058:896134527754962381321578694572419836648357219139826745915683472487295163263741958',
    '085431920073050046002000803006800000004125600000003400307000500590060270021587360:685431927973258146142796853216849735734125698859673412367912584598364271421587369',
    '120940700000167200640820030004200010910000027050004600070052069006738000005091072:128943756539167284647825931864279513913586427752314698371452869296738145485691372',
    '180604703600008490204007068473000002000502000500000617310700809046800001708901056:189654723637218495254397168473169582861572934592483617315726849946835271728941356',
    '804709320320001970019502800030604008970000046600207030007905480092300017083106502:854769321326481975719532864231694758975813246648257139167925483592348617483176592',
    '000010865708059100451080070015063200007000400002970580080090342009540708174030000:923714865768359124451682973815463297697825431342971586586197342239546718174238659',
    '831005260297100000500300800720860050013050980050093076006002001000008543045900628:831475269297186435564329817729861354613754982458293176386542791972618543145937628',
    '080005049300900850050040260125834000600271005000569132062050070049002003530400020:286715349314926857957348261125834796693271485478569132862153974749682513531497628',
    '032560098460000320000082704000240080001807900040015000103670000074000032980023610:732564198468791325519382764397246581251837946846915273123678459674159832985423617',
    '000003008250078943830960500080706094000010000640802010003041089419380052700500000:974253168256178943831964527185736294392415876647892315523641789419387652768529431',
    '800001002005802976300079010204108700080794020001503604050210008427906500900300007:879651342145832976362479815234168759586794123791523684653217498427986531918345267',
    '060100005000062083082795164008000036240000019530000400859326740420570000600004050:964138275715462983382795164198247536247653819536819427859326741423571698671984352',
    '705869000602037054903050700800000415090040060426000009008010207270690501000372608:745869123682137954913254786837926415591743862426581379368415297274698531159372648',
    '054200079002007010000000402608450031015302890790081205209000000030800900580006320:354218679862947513971563482628459731415372896793681245249735168136824957587196324',
    '956200400230450690010068003501004060600000004080600705300540080025086049007002156:956213478238457691714968523571834962692175834483629715369541287125786349847392156',
    '050038720137004860024600913040310000700000001000049050583006170062700539071250080:659138724137924865824675913245317698798562341316849257583496172462781539971253486',
    '100800020070026008328090704000480502290603041405017000703060219800740030060001007:156874923974326158328195764631489572297653841485217396743568219819742635562931487',
    '500160024200090003100725608067958030012000850050231470603549007700080005890017002:589163724276894513134725698467958231312476859958231476623549187741382965895617342',
    '390010458180750060050800000000460810010582030042071000000007040030048026421030087:397216458184753269256894371573469812619582734842371695968127543735948126421635987',
    '870250410000046387014800002030502068709000204260407050300008670187360000026015043:873259416592146387614873592431592768759681234268437159345928671187364925926715843',
    '075090821408060097900800306043000950560409073097000610109006002350020109726030480:675394821438162597912875346243617958561489273897253614189546732354728169726931485',
    '027834000009020103460519020056007300070203050008600270090378014804060700000492630:127834965589726143463519827256947381971283456348651279692378514834165792715492638',
    '910320004007068500048900632100007406090010080602800001754009260001250300300086045:916325874237468519548971632183597426495612783672843951754139268861254397329786145',
    '204096103600000400090400002168704005040508010500109684800002040006000008402380506:274896153685213479391475862168724935943568217527139684839652741756941328412387596',
    '091042008002300090008000602489203500175864239003905874807000100020006900900580420:791642358642358791358791642489273516175864239263915874837429165524136987916587423',
    '730200465190006830000300129200043700080791050007620001573004000049800013821005074:738219465192456837465387129216543798384791256957628341573164982649872513821935674',
    '605007000170520800000604501900002035024308190310900008406703000001096083000800607:645187329173529864892634571968412735524378196317965248486753912751296483239841657',
    '095000007010572039002690840000417296100020004274963000041039700380146050900000410:695384127418572639732691845853417296169825374274963581541239768387146952926758413',
    '010000690700096010036501742040902300000304000001608070473109520060840001089000060:814723695752496813936581742547912386628374159391658274473169528265847931189235467',
    '070349105540217068002005000890530400001402500005068031000900800980123057107854090:678349125549217368312685749896531472731492586425768931253976814984123657167854293',
    '801300050006054008002901406080619000200705001000832090304508200600170500050006103:841367952796254318532981476483619725269745831175832694314598267628173549957426183',
    '094068200030050090501042738205700100010826040006005907478630502020080070003270860:794368251832157694561942738245793186917826345386415927478639512629581473153274869',
    '800206070402030009003010620308004062046000710270800504037040800600080307080703006:815296473462537189793418625358174962946325718271869534537642891624981357189753246',
    '900204068624190005700365004000603007309702801800409000200546003400027659570901002:935274168624198375781365924142683597369752841857419236298546713413827659576931482',
    '345062070719504800600001000170096008803207604500140093000700006007603541030410987:345862179719534862628971435174396258893257614562148793451789326987623541236415987',
    '584000320031004570002500400000010087190607045420090000009006800075300160046000759:584971326931264578762583491653412987198637245427895613219756834875349162346128759',
    '140709520007000809008062700901400000476503918000001604009250400704000100035604097:143789526267145839598362741981476352476523918352891674619257483724938165835614297',
    '270010000000540000005237904490381607657020318301675092106752800000063000000090076:274916583963548721815237964492381657657429318381675492146752839729863145538194276',
    '020005001046830702008070409801620074003154800560089103602010300705042960400500010:327495681946831752158276439891623574273154896564789123682917345715342968439568217',
    '642801053000035008030940200009024380000000000084160500006053090800410000950602147:642871953791235468538946271179524386265398714384167529416753892827419635953682147',
    '120009630050760981000130407800004250200050008046200009602073000385041060094500013:127489635453762981968135427871394256239657148546218379612873594385941762794526813',
    '800107306650300100130920408260500007070682040900003065405079031006001084308405002:849157326652348179137926458263594817571682943984713265425879631796231584318465792',
    '280009307010074000097238000402650800069703420008042106000417960000320010701800034:284169357613574289597238641472651893169783425358942176835417962946325718721896534',
    '054680000072410685806000200000069040008127300020340000007000501581096420000051760:154682937972413685836975214713569842498127356625348179267834591581796423349251768',
    '025301006630900170000800935704100203000000000201006708193005000042003069500209310:925371486638954172417862935764198253389527641251436798193645827842713569576289314',
    '000700204820009130051060070080300690260804017075006080040030760036400029908007000:693781254827549136451263978184372695269854317375196482542938761736415829918627543',
    '420810560006035000085002030000608900569000781008109000050300890000590600092081045:423817569916435278785962134241678953569243781378159426154326897837594612692781345',
    '000800631010034008030201045364005080270148063080300492820609070700410050456003000:542897631617534928938261745364925187279148563185376492821659374793412856456783219',
    '570249308209003150008000270057408900030901040004605830016000700023100506705362091:571249368269783154348516279657438912832971645194625837916854723423197586785362491',
    '010893670000020009003740100049006051230178096760400230007082900900060000086914020:412893675578621349693745182849236751235178496761459238157382964924567813386914527',
    '107005040205410000306790510050834090000507000030961050071046805000078904060200107:197685243285413679346792518652834791419527386738961452971346825523178964864259137',
    '300900820051000003089001760968004070034562190020700436016400280400000350073005004:347956821651827943289341765968134572734562198125789436516473289492618357873295614',
    '420003080100420365000057142200000000678391254000000001741230000892045003060900027:425163789187429365936857142219574836678391254354682971741236598892745613563918427',
    '705893002012405008800160705070300290003000600061009080307041009100208450200957306:745893162612475938839162745578316294923584671461729583357641829196238457284957316',
    '000025030300010040800037509007002058593786214420900600905170002030090005040560000:679425831352819746814637529167342958593786214428951673985173462736294185241568397',
    '000620005170000000020401863732040580050712030091080472368504020000000056500067000:483629715176853294925471863732946581854712639691385472368594127247138956519267348',
    '819247500000603900236800704005000028600070009490000600503009871007306000002751436:819247563754613982236895714375964128621578349498132657563429871147386295982751436',
    '002608405000000060400035890045980006981070254600052180074160008060000000308509600:792618435853294761416735892245981376981376254637452189574163928169827543328549617',
    '004060503369500004005934061000809052000040000970103000540682700600007425207010300:124768593369521874785934261436879152851246937972153648543682719618397425297415386',
    '750010680268030041000000005801600007536000924400003806900000000610080493085090072:753214689268539741149867235891642357536178924427953816974321568612785493385496172',
    '540607000207800000000002068054208631070309080823105970430700000000006402000504097:548697123267813549391452768954278631176349285823165974439721856785936412612584397',
    '807269400046350020503048100000506200650010089001807000009680302060035970005972604:817269435946351827523748196738596241652413789491827563179684352264135978385972614',
    '601043097040062030500801624062000058450000019190000270314206005080710040970380102:621543897847962531539871624762139458458627319193458276314296785286715943975384162',
    '270480315089601020300750009090000002053204980100000070900045001020306450435027098:276489315589631724314752869698573142753214986142968573967845231821396457435127698',
    '024090150300000027010053006047538610260010085051726930100470060570000001082060370:624897153395641827718253496947538612263914785851726934139472568576389241482165379',
    '098600300000270950274000100035020408007546200402080560009000643041062000006003810:598614327163278954274935186635129478987546231412387569829751643341862795756493812',
    '207300059001527400060004000380019500050203040004750082000600030008935200520001607:247368159931527468865194723382419576756283941194756382419672835678935214523841697',
    '029840500816020000050190260082479050900203007070658920094061030000030745007084190:729846513816325479453197268682479351945213687371658924594761832168932745237584196',
    '210700960006000084308296001000809342004050600632401000700918405520000100081003096:215784963976135284348296571157869342894352617632471859763918425529647138481523796',
    '007825163010007859506000002024090080000030000030050290300000906179600020865972400:497825163213467859586319742724196385958234617631758294342581976179643528865972431',
    '029500108600004035500190207002607400000235000006908500201059004790400001805001390:429573168617824935538196247352617489984235716176948523261359874793482651845761392',
    '430680209097130000005927000710050802083209150504010063000872400000061730108093025:431685279297134586865927314719356842683249157524718963356872491942561738178493625',
    '203005064000400000408060070829057140370040096045310782080090607000006000560200409:213785964796421358458963271829657143371842596645319782182594637934176825567238419',
    '860003409104920600029470100983000040500000007070000836005094380002085701708200094:867153429154928673329476158983617245546832917271549836615794382492385761738261594',
    '050000702072040630090627054705001023021000980380200507540372060016080370907000040:654138792872945631193627854765891423421753986389264517548372169216489375937516248',
    '810070954420080107000310080370008640000060000064700029050037000209040018741090065:813276954426589137597314286375928641982461573164753829658137492239645718741892365',
    '400000930086419057000830041000054090004607500050290000840065000530128460069000005:412576938386419257975832641728354196194687523653291784841965372537128469269743815',
    '560020007000700290200408001905004800416872935002500406300205004057009000600080059:568921347143756298279438561935614872416872935782593416391265784857149623624387159',
    '780406000500329000429807305600200908845000237207008006308902571000165003000703029:783456192516329784429817365631274958845691237297538416368942571972165843154783629',
    '047905320009040086018000940260730090104209603070061054091000860750010400036402710:647985321329147586518326947265734198184259673973861254491573862752618439836492715',
    '500639801908002003030001004380065049100904008420180057800500090200300405705428006:574639821918742563632851974387265149156974238429183657843516792261397485795428316',
    '600408005310650000025970000051009067080217030740800910000084390000026048800103006:697438125318652479425971683251349867986217534743865912562784391139526748874193256',
    '700105000002073060051004072090002716200708004174500020680200140010380200000901007:768125439942873561351694872895432716236718954174569328689257143417386295523941687',
    '109025370053807690206009080010080060030261040060090050040100709021908430095340806:189625374453817692276439581914583267537261948862794153348156729621978435795342816',
    '306754000415000207870100054054000196000462000687000340190007063503000879000935401:326754918415689237879123654254378196931462785687591342192847563543216879768935421',
    '620030400839070000007260030260810043000603000370024016040082100000090264002040078:621538497839471625457269831265817943914653782378924516746382159183795264592146378',
    '280600703057000092031000845065300080028704150010006230173000460890000570506001029:289645713457138692631927845765312984328794156914586237173259468892463571546871329',
    '803052040900013008400806032659207010020104090030905627590301006300520009080670403:863752941972413568415896732659237814728164395134985627597341286346528179281679453',
    '050008003108290500203050098032809007070000050600705830480070905001084302300900080:957648123148293576263157498532819647879436251614725839486372915791584362325961784',
    '040006905005003010003150247314065008000000000500710364852091400060300100109500080:741286935925473816683159247314965728276834591598712364852691473467328159139547682',
    '935008260027301500400050070009517000740239058000684900070090002003106480054800796:935748261827361549461952873389517624746239158512684937678495312293176485154823796',
    '009005304002000907400073050040030805975802143308050090010390002807000400203400600:789215364532648917461973258146739825975862143328154796614397582897526431253481679',
    '060198003300060020409032080081004600730689014006500730020850309090010007800947060:562198473378465921419732586281374695735689214946521738127856349694213857853947162',
    '403500000872641593000703600148050000507906108000010257006309000254178369000005802:463592781872641593915783624148257936527936148639814257786329415254178369391465872',
    '320500490598600000740192005007001309035907280902300700600829073000006942079003018:321578496598634127746192835467281359135967284982345761614829573853716942279453618',
    '064000000307008001008639475973401800080090010006302794725914600800200107000000950:564127389397548261218639475973451826482796513156382794725914638839265147641873952',
    '028306059759008006600105002531060000002080500000010327300809004200600895980401670:128376459759248136643195782531762948472983561896514327367859214214637895985421673',
    '000602400200390058370840000008070010617504982040080700000059037130028009009403000:895612473264397158371845296528976314617534982943281765482159637136728549759463821',
    '000240000070196258501800060207658000080724010000931702040009501135467020000012000:869245137374196258521873964217658493983724615456931782642389571135467829798512346',
    '060087000702003010138024957000051030027000160050860000489210573010900406000340090:965187324742593618138624957694751832827439165351862749489216573213975486576348291',
    '040030590207460010009020700712008040385000271090100385001080900060094108078010050:146837592257469813839521764712358649385946271694172385421685937563794128978213456',
    '200740018090368450000050900100872000067000120000416007003080000072593060580024009:235749618791368452648251973154872396867935124329416587913687245472593861586124739',
    '208010654519260000003008200605092018300040002790830506007100400000057839954080107:278913654519264783463578291645792318381645972792831546837129465126457839954386127',
    '000400950091706002570300004640500830080604070027009045700001028900203710016005000:863412957491756382572398164649527831185634279327189645734961528958243716216875493',
    '900310000428607190050924807600000201090103070103000008209576010034801526000032009:967318452428657193351924867645789231892143675173265948289576314734891526516432789',
    '008021600020750000906480200004062030092807560060530800007015906000094070009270400:578921643423756198916483257854162739392847561761539824247315986185694372639278415',
    '120630000804005036000984521007001253009040100281300400973428000410500902000079084:125637849894215736736984521647891253359742168281356497973428615418563972562179384',
    '640000007009870605080400031010063004960704058200580060490007080102058400800000019:641395827329871645785426931518263794963714258274589163496137582132958476857642319',
    '820091040003076090019000300086053070700942008090760410002000760060530900070620035:827391546543276891619485327486153279731942658295768413352819764164537982978624135',
    '001605029259008600604090700048506130000921000026304950007050304003400298490803500:781635429259748613634192785948576132375921846126384957817259364563417298492863571',
    '706090100100000506030140802508704903010000060409301708601073080203000001004010307:786295134142837596935146872528764913317928465469351728651473289273589641894612357',
    '907080002032704190500920083001040027700206008290070600470019005059402870100030409:917683542832754196564921783681345927745296318293178654476819235359462871128537469',
    '004702190080409700000031608420876039009020400670945081706390000008207060042608300:364782195185469723297531648421876539859123476673945281716394852538217964942658317',
    '030001040000630172715000300270150063300296007860043021007000219426019000090800050:632971845948635172715482396274158963351296487869743521587364219426519738193827654',
    '000040080100200537800007946610004320309020804054800091765900008982001003030050000:597346182146289537823517946618794325379125864254863791765932418982471653431658279',
    '970230100050740082008060407180090750400080003037010096305070600860024070009056028:974238165653741982218965437182693754496587213537412896325879641861324579749156328',
    '580074603013520479000000825800201030090060080040809006726000000954082160108790042:582974613613528479479613825867251934395467281241839756726145398954382167138796542',
    '000378910800560002900024806009045600000793000005810300601430008500081007028957000:256378914814569732937124856389245671162793485745816329671432598593681247428957163',
    '082460000010983000360201849006700305170000062803002400649108053000526090000049670:982467531415983726367251849296714385174835962853692417649178253738526194521349678',
    '007003901010090540000500827790640000240309076000081092186005000023060050504200600:857423961612897543439516827791642385248359176365781492186975234923164758574238619',
    '004105700201437800000008015025000671670502084419000520140200000002643108006701200:984165732251437896367928415825394671673512984419876523148259367792643158536781249',
    '070805034005070906002609057000231009030000020200968000580706400104080700720104080:679815234845372916312649857468231579931457628257968143583726491194583762726194385',
    '710806439003004200000300187060000075530010042270000090842001000001600700657208014:715826439983174256426359187169482375538917642274563891842791563391645728657238914',
    '182060340007320009430005270800000061574030928210000004045200087700096100061070492:182967345657324819439185276893742561574631928216859734945213687728496153361578492',
    '050108027309640800002050640008320179040506080231097400083060700005083201420901030:654138927379642815812759643568324179947516382231897456183265794795483261426971538',
    '904001082001080600683020000046300100519000438007009250000010723002090500170400809:954761382721983645683524971246358197519276438837149256498615723362897514175432869',
    '420100500083000020106052080814976000609020108000841697050280406040000810008004032:427138569583469721196752384814976253679325148235841697951283476342697815768514932',
    '020001675056032080190000032580400706960000051201006048710000093040190560639800010:328941675456732189197568432583419726964287351271356948715624893842193567639875214',
    '900034000840791305000268907094000023100040009270000410409317000701689034000420001:967534182842791365315268947594176823136842579278953416429317658751689234683425791',
    '002385006360000758580006040405607810000154000097208405050900081673000029900562300:742385196361429758589716243435697812826154937197238465254973681673841529918562374',
    '100300000090052740040960100854020007370481052200030864002047030087510090000006008:125374689698152743743968125854629317376481952219735864962847531487513296531296478',
    '003001829050978060100000504700094030509306702030750008901000007020819050845200900:673541829254978361198623574782194635519386742436752198961435287327819456845267913',
    '000007000020040089460120530900430750670205018035018004049082071810070090000900000:193857426527643189468129537981436752674295318235718964349582671816374295752961843',
    '907003140650094037300708005760000980209407501018000074800601009120840053093500608:987253146652194837341768295764315982239487561518926374875631429126849753493572618',
    '040873100008010049301900060400680215006735400985041006090007504570090600002458070:649873152728516349351924867437689215216735498985241736893167524574392681162458973',
    '468030170000900085051780020506340090100050004090018502070093240340005000019020357:468532179237961485951784623526347891183259764794618532675193248342875916819426357',
    '000600790106700420740200006231865904000070000608943215300007069067001802085006000:823654791156739428749218356231865974594172683678943215312487569467591832985326147',
    '020405008548002630167000452200080000704609301000030005835000964072900813900308020:329465178548172639167893452293581746754629381681734295835217964472956813916348527',
    '002034090065820004000690210106540800749103652008067109051078000600052780080410900:812734596965821374473695218126549837749183652538267149251978463694352781387416925',
    '046159000003872000020364709000000534001705900485000000207918040000537800000426150:746159283193872465528364719972681534361745928485293671257918346614537892839426157',
    '000130002271069500083024001410000805002671400307000016100780960008240157700015000:549137682271869543683524791416392875852671439397458216125783964938246157764915328',
    '296514073045078060000000000900006345000345000534800002000000000050280930810769524:296514873345978261781632459978126345162345798534897612629453187457281936813769524',
    '049006000003487009670159304904000051700010003810000602401763095500291400000800710:149326587253487169678159324934672851726518943815934672481763295567291438392845716',
    '010000000030167200000342016800009650526831974049700008360518000004273060000000030:612985743435167289798342516873429651526831974149756328367518492984273165251694837',
    '000850900208030000590400823600710049782304615910026008425003076000070504009045000:347852961268139457591467823653718249782394615914526738425983176836271594179645382',
    '319004000602098700478003591000530800980000025005081000563400178007310206000800953:319754682652198734478263591746532819981647325235981467563429178897315246124876953',
    '040719026026805700107300000030200087050000030710003050000001208001908470280476010:845719326326845791197362845639254187458197632712683954974531268561928473283476519',
    '201400007098650403300017600000045070410000058070280000009760005804093760600004801:261439587798652413345817629982345176413976258576281934129768345854193762637524891',
    '260540907078260410009870026105002030000405000080900205920057800036094750701028094:263541987578269413419873526145782639692435178387916245924357861836194752751628394',
    '304900800600000210152604370400009703703412506509700001046203157017000002005007908:374921865698375214152684379461859723783412596529736481846293157917548632235167948',
    '009047001057010468000580009980370040270461093010058076500094000641030980700120300:829647531357219468164583729986372145275461893413958276532894617641735982798126354',
    '017000050000509761605700200800000542201406807734000009006003104372105000040000320:917632458423589761685714293869371542251496837734258619596823174372145986148967325',
    '307106084600279050090300076002003008000907000400600100850001030030465007740802509:327156984684279351195384276962513748518947623473628195856791432239465817741832569',
    '700082409000051670621090008008509104002103800406208500100020946084910000905430001:753682419849351672621794358378569124592143867416278593137825946284916735965437281',
    '025100740908000205730560000500040306400301009103050004000039058307000102049005630:625198743918473265734562981592847316486321579173956824261739458357684192849215637',
    '900084010043061508086597000000100736001070200672003000000639870809710340050420009:925384617743261598186597423498152736531976284672843951214639875869715342357428169',
    '580240000040003875391080040000402190400070006019308000060090453153600080000035061:587246319246913875391587642735462198428179536619358724862791453153624987974835261',
    '010027659000040320200000041005230910160708035043015200590000004027050000831470060:314827659679541328258963741785234916162798435943615287596382174427156893831479562',
    '700005020238074056501020700052016030070000010010530280006050803140360592080700001:764185329238974156591623748452816937873249615619537284926451873147368592385792461',
    '050080200600207801002004006017562098040070020280941360500800700708409002004020080:451683279693257841872194536317562498946378125285941367529836714738419652164725983',
    '380000479100800000047329186400980001000207000800046002798415620000008007651000094:382561479169874235547329186425983761916257348873146952798415623234698517651732894',
    '005000040000520713623070800089754020201000408060218350002060134136042000070000900:715389246948526713623471895389754621251693478467218359592867134136942587874135962',
    '549001000003902010810765340001270000000403000000056900097634085030108400000500163:549381726763942518812765349381279654956413872274856931197634285635128497428597163',
    '000006901905040020040820000294000608513687294608000315000068030030070409702900000:827356941965741823341829567294513678513687294678492315459168732136275489782934156',
    '009405107240000000501093004700050943900701006835040002300910408000000071107304600:689425137243176895571893264716258943924731586835649712362917458498562371157384629',
    '400783905000000008082961407600000800803607104001000003307426580100000000208175006:416783925739254618582961437654312879823697154971548263397426581165839742248175396',
    '510000783329805100074310500600000009400592008200000004002053860003407925965000037:516249783329875146874316592658734219431592678297681354742953861183467925965128437',
    '008000090061902050059708400000306520534000689082504000003205960010803240070000800:728451396461932758359768412197386524534127689682594173843215967916873245275649831',
    '057002810108543609309070000640300200000060000005004036000080701802137504016400390:457692813128543679369871452641359287973268145285714936534986721892137564716425398',
    '952001370706004001108070002504700063001603400670008509300040708400200906069100245:952861374736524891148379652584792163291653487673418529325946718417285936869137245',
    '360005010052793604970018500020070060006134200030050090005360047609587320010900056:368425719152793684974618532521879463896134275437256198285361947649587321713942856',
    '001075980080320007027090031410000870002000300098000026250030610800069050036580700:341675982985321467627894531413256879762918345598743126259437618874169253136582794',
    '581020073967003800234000000010204609059308120802901030000000741006500398190030265:581629473967143852234785916713254689659378124842961537325896741476512398198437265',
    '500012000206804031490600200910530008003000500800049072009006057650701803000380006:538912764276854931491673285912537648743268519865149372389426157654791823127385496',
    '800100026197050040602839000006780000310060082000091600000518203030070861980006004:853147926197652348642839157526783419319465782478291635764518293235974861981326574',
    '009004732002006409007090000305601970004508600016309508000030800208100300543900200:169854732832716459457293186385621974924578613716349528671432895298165347543987261',
    '478010003005402108126000000000001325050349010731600000000000836503104900200030541:478516293395472168126893754649781325852349617731625489914257836583164972267938541',
    '070240100214809600398061000000320780001506200042097000000970864007408325005032010:576243198214859673398761452659324781731586249842197536123975864967418325485632917',
    '003001090076439081091060730030000007740050069600000050052070310360185940010300600:483721596576439281291568734135946827748253169629817453952674318367185942814392675',
    '000608010654200908180005000903700004502809103800001205000500021401003756060104000:239648517654217938187395642913752864542869173876431295398576421421983756765124389',
    '000780504200009071740106800507410903918000457406075102002801045370600008804097000:169783524283549671745126839527418963918362457436975182692831745371654298854297316',
    '340100620150270000000069051600940003030785010900031008860590000000026094097004065:349158627156273489728469351681942573432785916975631248864597132513826794297314865',
    '809030000050610004160020507720590046605743208340068075506080029400052080000070401:879435162253617894164829537728591346695743218341268975536184729417952683982376451',
    '048300000309120805601000900792035006100897004500260793007000308403082507000003420:248359671379126845651748932792435186136897254584261793927514368463982517815673429',
    '405396000601480009902500060026000007090275030300000850050004603200059708000638905:475396281631482579982517364526843197198275436347961852859724613263159748714638925',
    '605020400208006073130047060407900001090000040500001708050680014820300907004050806:675123489248596173139847562487965321391278645562431798753689214826314957914752836',
    '082470930700002580001000024078563000054010670000749150430000800067800005019057460:582471936746932581391685724178563249954218673623749158435126897267894315819357462',
    '700050420003761000915008360860530079007010200190087036028600713000843900039070008:786359421243761895915428367862534179357916284194287536428695713671843952539172648',
    '300020001000010470721940538000201309190704025402605000683079254014050000200060003:345827961869513472721946538576281349198734625432695817683179254914352786257468193',
    '070900500954031867013785000007092030000678000080150700000316940345820671006007080:872964513954231867613785294567492138231678459489153726728316945345829671196547382',
    '000094061701068000300500040004083759007209600139650400080002004000430108410870000:528794361741368295396521847264183759857249613139657482683912574975436128412875936',
    '027830401008000007105470900064180370000000000073095180001028506300000700402067810:627839451948251637135476928564182379819743265273695184791328546386514792452967813',
    '380002047072000080400789300023010800854903162001020530005248006090000410640300058:389152647572436981416789325923615874854973162761824539135248796298567413647391258',
    '037026540060000000150000280210060375009508100543010068021000037000000050085670410:937826541862154793154793286218469375679538124543217968421985637796341852385672419',
    '800600493493008250000094000016789004030241060900536180000810000087400931164003005:871652493493178256625394718516789324738241569942536187359817642287465931164923875',
    '007680000000700048890243705012068000680000074000570280301824097920007000000036400:147685932253719648896243715712468359685392174439571286361824597924157863578936421',
    '000000024704009001950240007010062570230754096076910040800025013100400705340000000:683571924724839651951246837419362578238754196576918342897625413162493785345187269',
    '400598006002007090600010040536209710701403609024701853060070005040900300100835002:417598236352647198698312547536289714781453629924761853263174985845926371179835462',
    '017600000582900740306050000825709401970000062601205897000090605064008913000006280:417682359582913746396457128825769431973841562641235897238194675764528913159376284',
    '061900704390005680000030501000620405105304809608091000804050000059100048206007950:561982734397415682482736591973628415125374869648591327834259176759163248216847953',
    '904210000200000017701950020100542603020739040305186002070028104530000009000095308:964217835253864917781953426197542683826739541345186792679328154538471269412695378',
    '070362584006050390030810000960270000003000600000091073000087030097030800381926040:179362584826754391435819267964273158713548629258691473542187936697435812381926745',
    '700060040068504070340270580506140000003080400000059608094013065030805710070020003:751968342268534179349271586586142937923687451417359628894713265632895714175426893',
    '060510400000300071400826000278145030540000087030678245000289004680003000004061050:963517428825394671417826593278145936546932187139678245751289364682453719394761852',
    '080107000000080030372604190049710006800369005600048970056803419090070000000501060:984137652561982734372654198249715386817369245635248971756823419198476523423591867',
    '503000009904061008070985003360070020492010756010050094100627080700590102200000907:583742619924361578671985243365479821492813756817256394139627485746598132258134967',
    '007015029040096380065000147400000006706541908500000002698000270054160090370280500:837415629142796385965832147413928756726541938589673412698354271254167893371289564',
    '690000000208010067300000192567083901003175600102490753826000009410020806000000014:691732485258914367374658192567283941943175628182496753826341579419527836735869214',
    '907500031630002000000137960004896070206351804080724300092685000000200058860003709:927568431631942587458137962314896275276351894589724316792685143143279658865413729',
    '200095700905184063030276859400000002608000405300000006843621090720853601001740008:286395714975184263134276859497568132618932475352417986843621597729853641561749328',
    '001980000809270100307614020193042800008000400006590231010329605002057309000061700:261983574849275163357614928193742856528136497476598231714329685682457319935861742',
    '085002316003850907014300080400008000802705109000900008050006830208034700347100650:785492316623851947914367285491628573832745169576913428159276834268534791347189652',
    '000690100150034002760150034603420001090000060200016309930068015500970023002043000:324697158159834672768152934673429581491385267285716349937268415546971823812543796',
    '060000405007040169094501000500016048931000526480320007000108790849030200705000080:168279435257843169394561872572916348931784526486325917623158794849637251715492683',
    '906080400020060007080532100078600005549827316600009870005296040200070050007010608:956781432321964587784532169178643295549827316632159874815296743263478951497315628',
    '305100064060800023400065700003600200870201046006007900004720009980006030630004107:395172864761849523428365791143698275879251346256437918514723689987516432632984157',
    '639000500580069210000008936900080063802603105370010002468100000097430051003000674:639721548584369217721548936915284763842673195376915482468157329297436851153892674',
    '645020080901840500803560004409000030082030150010000408100094605007012803060050719:645927381971843562823561974459186237782439156316275498138794625597612843264358719',
)
# PUZZLES END
