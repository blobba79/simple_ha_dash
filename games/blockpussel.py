"""Blockpussel (en spelfil för dash-panelen, se games/SKAPA-SPEL.md).

Ett Block Blast-liknande spel: ett rutnät på 8x8, tre bitar åt gången som dras med fingret till rutnätet. Hela rader och
kolumner försvinner; spelet är slut när ingen av bitarna som är kvar får plats.

Filen har två delar: Rules (spelreglerna: ingen ritning, rutnätet är ett 64-bitars heltal plus en färglista så att kontroller
går fort på dashs lilla processor) och Game (skärmen: ritning och tryck). Ritningen följer panelens sätt: allt som inte
rör sig ritas i en hel bild i minnet (`bg`) och kopieras bara där något ändrats; det man drar ritas ovanpå och tas bort
genom att samma ruta kopieras tillbaka ur `bg`.

Sparfilen har samma format som den äldre game.json (spelet tar över den om den finns)."""
import math
import random

from PIL import Image

from dashpanel import gamesdk as sdk

META = {
    'api': 1,
    'id': 'blockpussel',
    'name': 'Blockpussel',
    'desc': 'Dra bitar till rutnätet och fyll hela rader och kolumner.',
    'version': 1,
    'legacy_save': '/var/lib/dash-panel/game.json',
}

T = sdk                         # färgerna heter likadant i sdk som i panelens tema
W, H = sdk.W, sdk.H
text, text_width, bbox, rbox, rbox_mask = sdk.text, sdk.text_width, sdk.bbox, sdk.rbox, sdk.rbox_mask
blend, icon, snap = sdk.blend, sdk.icon, sdk.snap


# ================================================================ reglerna
N = 8
NCOLORS = 7
ROWMASK = [0xFF << (8 * r) for r in range(N)]
COLMASK = [sum(1 << (8 * r + c) for r in range(N)) for c in range(N)]

SAVE_VERSION = 1            # sparfilens format (samma som i den äldre game.json)
CLEAR_POINTS = 10           # poäng per rensad rad eller kolumn, gånger antalet i samma drag i kvadrat
EMPTY_BONUS = 300           # extra poäng om hela brädet blir tomt
COMBO_GAP = 3               # så många utan rensning i rad tillåts innan kombon bryts


class Shape(object):
    __slots__ = ('name', 'cells', 'w', 'h', 'mask', 'weight')

    def __init__(self, name, art, weight):
        self.name = name
        self.cells = tuple((r, c) for r, row in enumerate(art) for c, ch in enumerate(row) if ch == '#')
        self.h = max(r for r, _ in self.cells) + 1
        self.w = max(c for _, c in self.cells) + 1
        self.mask = sum(1 << (r * 8 + c) for r, c in self.cells)
        self.weight = weight

    def placed(self, r, c):
        """Bitmask för bitens rutor när dess övre vänstra hörn ligger på rad r, kolumn c."""
        return self.mask << (r * 8 + c)


# (konstruktion i text, vikt): lägre vikt = ovanligare. Små bitar är vanligast.
_ART = [
    (['#'], 4),
    (['##'], 4), (['#', '#'], 4),
    (['###'], 4), (['#', '#', '#'], 4),
    (['####'], 2.5), (['#', '#', '#', '#'], 2.5),
    (['#####'], 1.2), (['#', '#', '#', '#', '#'], 1.2),
    (['##', '##'], 5),
    (['###', '###', '###'], 1.5),
    (['###', '###'], 2), (['##', '##', '##'], 2),
    # vinkel med tre rutor
    (['##', '#.'], 3), (['##', '.#'], 3), (['#.', '##'], 3), (['.#', '##'], 3),
    # L och J med fyra rutor
    (['#.', '#.', '##'], 2), (['.#', '.#', '##'], 2), (['##', '#.', '#.'], 2), (['##', '.#', '.#'], 2),
    (['###', '#..'], 2), (['###', '..#'], 2), (['#..', '###'], 2), (['..#', '###'], 2),
    # T
    (['###', '.#.'], 2), (['.#.', '###'], 2), (['#.', '##', '#.'], 2), (['.#', '##', '.#'], 2),
    # S och Z
    (['.##', '##.'], 2), (['##.', '.##'], 2), (['#.', '##', '.#'], 2), (['.#', '##', '#.'], 2),
    # stor vinkel med fem rutor
    (['#..', '#..', '###'], 1.2), (['..#', '..#', '###'], 1.2), (['###', '#..', '#..'], 1.2), (['###', '..#', '..#'], 1.2),
]
SHAPES = []
for _i, (_art, _w) in enumerate(_ART):
    SHAPES.append(Shape('s%d' % _i, _art, _w))
SHAPE_BY_NAME = {s.name: s for s in SHAPES}
_TOTAL_W = sum(s.weight for s in SHAPES)


class Piece(object):
    __slots__ = ('shape', 'color')

    def __init__(self, shape, color):
        self.shape = shape
        self.color = color


def full_lines(occ):
    """Bitmask över alla rutor i hela rader och kolumner."""
    m = 0
    for i in range(N):
        if occ & ROWMASK[i] == ROWMASK[i]:
            m |= ROWMASK[i]
        if occ & COLMASK[i] == COLMASK[i]:
            m |= COLMASK[i]
    return m


def fits_somewhere(occ, shape):
    mask = shape.mask
    for r in range(N - shape.h + 1):
        for c in range(N - shape.w + 1):
            if not occ & (mask << (r * 8 + c)):
                return True
    return False


class Rules(object):
    """Spelreglerna (ingen ritning): brädet, bitarna, poängen och sparformatet."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.best = 0
        self.new()

    # ------------------------------------------------------------ nytt spel och utdelning
    def new(self):
        self.occ = 0
        self.col = [0] * 64
        self.score = 0
        self.combo = 0
        self.gap = 0            # drag sedan senaste rensning
        self.over = False
        self.new_best = False
        self.moves = 0
        self.pieces = [None, None, None]
        self.deal()
        self._check_over()

    def _rand_piece(self):
        x = self.rng.random() * _TOTAL_W
        for s in SHAPES:
            x -= s.weight
            if x <= 0:
                return Piece(s, self.rng.randint(1, NCOLORS))
        return Piece(SHAPES[0], self.rng.randint(1, NCOLORS))

    def deal(self):
        """Delar ut tre nya bitar. Ett par försök görs för att få en uppsättning där alla tre går att lägga i någon
        ordning (annars åtminstone en som får plats), så att spelet inte blir orättvist."""
        fallback = None
        ps = None
        for _ in range(12):
            ps = [self._rand_piece() for _ in range(3)]
            q = self._playable(ps)
            if q == 2:
                fallback = ps
                break
            if q == 1 and fallback is None:
                fallback = ps
        self.pieces = fallback or ps

    def _playable(self, ps):
        """2 = alla tre går att lägga i någon ordning, 1 = minst en får plats, 0 = ingen får plats."""
        shapes = [p.shape for p in ps]
        if not any(fits_somewhere(self.occ, s) for s in shapes):
            return 0
        return 2 if self._sequence(self.occ, shapes, [250]) else 1

    def _sequence(self, occ, shapes, budget):
        if not shapes:
            return True
        seen = set()
        for i, sh in enumerate(shapes):
            if sh.name in seen:
                continue
            seen.add(sh.name)
            rest = shapes[:i] + shapes[i + 1:]
            for r in range(N - sh.h + 1):
                for c in range(N - sh.w + 1):
                    m = sh.mask << (r * 8 + c)
                    if occ & m:
                        continue
                    budget[0] -= 1
                    if budget[0] < 0:
                        return False
                    noc = occ | m
                    noc &= ~full_lines(noc)
                    if self._sequence(noc, rest, budget):
                        return True
        return False

    # ------------------------------------------------------------ frågor
    def can_place(self, shape, r, c):
        return (0 <= r <= N - shape.h and 0 <= c <= N - shape.w and not self.occ & shape.placed(r, c))

    def preview(self, shape, r, c):
        """Bitmask över rutor som skulle rensas om biten lades på r, c (0 om inget rensas)."""
        return full_lines(self.occ | shape.placed(r, c))

    def piece_fits(self, slot):
        p = self.pieces[slot]
        return p is not None and fits_somewhere(self.occ, p.shape)

    def empty_cells(self):
        return N * N - bin(self.occ).count('1')

    def _check_over(self):
        self.over = not any(self.piece_fits(i) for i in range(3))

    # ------------------------------------------------------------ lägga en bit
    def place(self, slot, r, c):
        """Lägger bit nummer slot på r, c. Ger en ordbok med vad som hände, eller None om det inte går."""
        p = self.pieces[slot] if 0 <= slot < 3 else None
        if self.over or p is None or not self.can_place(p.shape, r, c):
            return None
        sh = p.shape
        m = sh.placed(r, c)
        self.occ |= m
        for dr, dc in sh.cells:
            self.col[(r + dr) * 8 + c + dc] = p.color
        clear = full_lines(self.occ)
        rows = [i for i in range(N) if self.occ & ROWMASK[i] == ROWMASK[i]]
        cols = [i for i in range(N) if self.occ & COLMASK[i] == COLMASK[i]]
        cleared = [(i, self.col[i]) for i in range(64) if clear >> i & 1]
        self.occ &= ~clear
        for i, _ in cleared:
            self.col[i] = 0
        lines = len(rows) + len(cols)
        gain = len(sh.cells)
        bonus = 0
        empty = False
        if lines:
            self.combo = self.combo + 1 if self.combo > 0 else 1
            self.gap = 0
            bonus = CLEAR_POINTS * lines * lines * self.combo
            gain += bonus
            if self.occ == 0:
                empty = True
                gain += EMPTY_BONUS
        else:
            self.gap += 1
            if self.gap >= COMBO_GAP:
                self.combo = 0
        self.score += gain
        if self.score > self.best:
            if self.best > 0:
                self.new_best = True        # "Nytt rekord!" först när det fanns ett rekord att slå
            self.best = self.score
        self.moves += 1
        self.pieces[slot] = None
        dealt = False
        if all(x is None for x in self.pieces):
            self.deal()
            dealt = True
        self._check_over()
        return {'slot': slot, 'r': r, 'c': c, 'shape': sh, 'color': p.color, 'lines': lines, 'rows': rows,
                'cols': cols, 'cleared': cleared, 'gain': gain, 'bonus': bonus, 'combo': self.combo,
                'empty': empty, 'dealt': dealt, 'over': self.over}

    # ------------------------------------------------------------ spara och läsa
    def to_dict(self):
        return {
            'board': list(self.col),
            'pieces': [None if p is None else [p.shape.name, p.color] for p in self.pieces],
            'score': self.score, 'combo': self.combo, 'gap': self.gap, 'moves': self.moves,
            'over': self.over, 'new_best': self.new_best,
        }

    def load_dict(self, d):
        """Läser ett sparat spel. Ger True om allt var rimligt; annars lämnas spelet som det var."""
        try:
            board = d['board']
            if not (isinstance(board, list) and len(board) == 64
                    and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= NCOLORS for v in board)):
                return False
            pieces = []
            for x in d['pieces']:
                if x is None:
                    pieces.append(None)
                    continue
                name, color = x
                if name not in SHAPE_BY_NAME or not (isinstance(color, int) and 1 <= color <= NCOLORS):
                    return False
                pieces.append(Piece(SHAPE_BY_NAME[name], color))
            if len(pieces) != 3:
                return False
            score, combo, gap, moves = (int(d.get(k, 0)) for k in ('score', 'combo', 'gap', 'moves'))
            if min(score, combo, gap, moves) < 0:
                return False
        except (KeyError, TypeError, ValueError):
            return False
        self.col = list(board)
        self.occ = sum(1 << i for i, v in enumerate(board) if v)
        self.pieces = pieces
        self.score, self.combo, self.gap, self.moves = score, combo, gap, moves
        self.new_best = bool(d.get('new_best', False))
        self.best = max(self.best, self.score)
        if all(p is None for p in self.pieces):
            self.deal()
        self._check_over()
        return True


# ---------------------------------------------------------------- sparformat
def dump_data(game):
    """Det som sparas: rekordet och det pågående spelet (samma format som den äldre game.json)."""
    return {'v': SAVE_VERSION, 'best': game.best, 'state': game.to_dict()}


def load_data(game, d):
    """Läser sparad data in i game. Ger False om den inte alls går att läsa (fel version eller form)."""
    if not isinstance(d, dict) or d.get('v') != SAVE_VERSION:
        return False
    best = d.get('best')
    if isinstance(best, int) and not isinstance(best, bool) and best > 0:
        game.best = best
    st = d.get('state')
    if isinstance(st, dict):
        game.load_dict(st)
    return True


# ---------------------------------------------------------------- spelväljarens rad och ikon
def status(data):
    """Raden under namnet i spelväljaren: pågående spel eller rekord."""
    if not data:
        return None
    g = Rules(random.Random(0))
    if not load_data(g, data):
        return None
    best, active = g.best, g.moves > 0 and not g.over
    if active:
        return ('Pågående spel · Rekord %s' % thousands(best) if best else 'Pågående spel'), True
    return ('Rekord %s' % thousands(best), False) if best else None


_ICON_ART = ('1...', '1.22', '1.22', '1133')       # 4x4 rutor, siffran är färgen (1-7)


def draw_icon(im):
    """Ikonen (128x128): fyra gånger fyra rutor med några bitar."""
    pitch = sdk.ICON // 4
    size = pitch - 2
    for r in range(4):
        for c in range(4):
            x, y = c * pitch + 1, r * pitch + 1
            ch = _ICON_ART[r][c]
            if ch == '.':
                rbox(im, x, y, x + size, y + size, 5, EMPTY)
            else:
                spr, msk = block_sprite(int(ch), size)
                im.paste(spr, (x, y), msk)


# ================================================================ skärmen
CELL = 56                       # rutnätets rutstorlek (pixlar)
GAP = 2                         # luft runt varje block
BX, BY = 40, 100                # rutnätets övre vänstra hörn
BOARD = (BX, BY, BX + N * CELL, BY + N * CELL)
CARD = (24, 84, 504, 564)       # kortet runt rutnätet
RIGHT_X0, RIGHT_X1 = 528, 1008
SCORE_RECT = (RIGHT_X0, 100, RIGHT_X1, 196)
TRAY_RECT = (RIGHT_X0, 208, RIGHT_X1, 388)
SLOT_W, SLOT_H, SLOT_GAP = 148, 156, 6
SLOT_Y = 220
SLOTS = [(RIGHT_X0 + 12 + i * (SLOT_W + SLOT_GAP), SLOT_Y, RIGHT_X0 + 12 + i * (SLOT_W + SLOT_GAP) + SLOT_W,
          SLOT_Y + SLOT_H) for i in range(3)]
MINI = 28                       # rutstorlek i fältet med bitar
MSG_RECT = (RIGHT_X0, 396, RIGHT_X1, 470)
NEW_RECT = (RIGHT_X0, 484, 768, 564)
COMBO_RECT = (784, 484, RIGHT_X1, 564)
HEAD_RECT = (0, 10, 700, 82)
CLOCK_RECT = (846, 10, W, 82)
AGAIN_RECT = (BX + 64, 410, BX + 384, 478)

GRAB_DY = 36                    # avstånd mellan fingret och bitens nederkant
SNAP_DIST = 0.8                 # så långt (i rutor) från en ledig plats snäpper biten
HIT_SLOP = 16
ANIM_STEPS = 5
ANIM_DT = 0.055
MSG_SECONDS = 2.6
CONFIRM_SECONDS = 3.0
SAVE_DELAY = 8.0
OVER_GUARD = 1.0                # så länge efter spelets slut ignoreras tryck på "Spela igen"

PALETTE = {
    1: (3, 169, 244),       # blå (som panelens blå)
    2: (255, 193, 7),       # gul
    3: (255, 112, 67),      # orange
    4: (102, 187, 106),     # grön
    5: (171, 71, 188),      # lila
    6: (239, 83, 80),       # röd
    7: (38, 198, 218),      # turkos
}
EMPTY = (0x2b, 0x2b, 0x2b)
SLOT_BG = (0x24, 0x24, 0x24)
GREEN = (102, 187, 106)

_PIL_BOX = getattr(getattr(Image, 'Resampling', Image), 'BOX')


def _shade(c, k):
    return tuple(max(0, min(255, int(round(v * k)))) for v in c)


# ---------------------------------------------------------------- block (förrenderade)
_sprites = {}
_alpha_masks = {}
_empty_board = []


def block_sprite(color, size, dim=0.0):
    """(bild, mask) för ett block med färgen color (1..7) och sidan size. dim 0..1 blandar mot mörkt (för bitar som
    inte får plats)."""
    key = (color, size, round(dim, 2))
    hit = _sprites.get(key)
    if hit is not None:
        return hit
    base = PALETTE[color]
    if dim:
        base = blend(base, SLOT_BG, dim)
    r = max(3, size // 6)
    ins = max(2, size // 13)
    img = Image.new('RGB', (size, size), _shade(base, 0.60))
    mask = Image.new('L', (size, size), 0)
    rbox(mask, 0, 0, size, size, r, 255)
    rbox(img, ins, ins, size - ins, size - ins - max(1, ins // 2), max(2, r - ins // 2), base)
    top = ins + max(1, size // 14)
    rbox(img, top, top, size - top, top + max(3, size // 4), max(2, r // 2), blend(base, (255, 255, 255), 0.26))
    _sprites[key] = (img, mask)
    return _sprites[key]


def alpha_mask(mask, a):
    key = (id(mask), round(a, 2))
    hit = _alpha_masks.get(key)
    if hit is None:
        hit = mask.point([int(i * a) for i in range(256)])
        _alpha_masks[key] = hit
    return hit


def draw_board_card(w, h):
    """Rutnätets kort med tomma rutor (förrenderat en gång)."""
    if _empty_board:
        return _empty_board[0]
    im = Image.new('RGB', (w, h), T.BG)
    bbox(im, 0, 0, w, h, 18, T.CARD, T.CARD_BORDER, 1)
    for r in range(N):
        for c in range(N):
            x = BX - CARD[0] + c * CELL + GAP
            y = BY - CARD[1] + r * CELL + GAP
            rbox(im, x, y, x + CELL - 2 * GAP, y + CELL - 2 * GAP, 9, EMPTY)
    _empty_board.append(im)
    return im


def cell_xy(i):
    return BX + (i % 8) * CELL, BY + (i // 8) * CELL


def _inside(r, x, y, slop=0):
    return r[0] - slop <= x < r[2] + slop and r[1] - slop <= y < r[3] + slop


def _clip(r):
    return (max(0, r[0]), max(0, r[1]), min(W, r[2]), min(H, r[3]))


def _union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _meets(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def thousands(n):
    s = '{:,}'.format(int(n))
    return s.replace(',', ' ')


def _clear(img, r, color=T.BG):
    img.paste(color, (r[0], r[1], r[2], r[3]))


def _centered(img, cx, baseline, s, weight, size, color):
    text(img, cx - text_width(s, weight, size) / 2.0, baseline, s, weight, size, color)


class Game(sdk.GameBase):
    """Hela spelets skärm och pek. Panelen anropar draw(gen) och on_touch(kind, x, y) medan spelet visas.
    (Det här är ett "avancerat" spel: det har egen ritning med en bild i minnet och egen pekhantering och använder
    GameBase bara för tidtagare, sparfil, krokar och felskydd.)"""

    def setup(self):
        self.game = Rules(self.rng)
        self.bg = Image.new('RGB', (W, H), T.BG)
        self.ov_rect = None
        self.ov_key = None
        self.drag = None
        self.msg = None
        self.anim = None
        self.confirm_new = False
        self.over_at = None

    # ------------------------------------------------------------ in och ut, spara
    def on_open(self):
        self.drag = None
        self.confirm_new = False
        if self.game.over:
            self.over_at = self.loop.time()

    def on_close(self):
        self.drag = None
        self.anim = None
        self.msg = None
        self.confirm_new = False

    def state(self):
        return dump_data(self.game)

    def restore(self, data):
        return load_data(self.game, data)

    # ------------------------------------------------------------ pek
    def on_touch(self, kind, x, y):
        if kind == 'down':
            self._down(x, y)
        elif kind == 'move':
            self._move(x, y)
        else:
            self._up(x, y)

    def _rects(self):
        r = {'back': self._back_rect, 'new': NEW_RECT}
        if self.game.over:
            r['again'] = AGAIN_RECT
        return r

    def _hit(self, x, y):
        for name, rect in self._rects().items():
            if _inside(rect, x, y, 8 if name == 'back' else 0):
                if name == 'again' and self.over_at is not None and self.loop.time() - self.over_at < OVER_GUARD:
                    return None
                return name
        return None

    def _down(self, x, y):
        self.touch = None
        self.drag = None
        name = self._hit(x, y)
        if name is not None:
            self.touch = {'t': name, 'inside': True}
            self.pressed = name
            self.refresh(urgent=True)
            return
        if self.game.over:
            return
        for i, rect in enumerate(SLOTS):
            if self.game.pieces[i] is not None and _inside(rect, x, y, 4):
                self.touch = {'t': 'drag', 'inside': True}
                self.drag = {'slot': i, 'x': x, 'y': y, 'snap': None, 'clear': 0, 'left': 0.0, 'top': 0.0}
                self._drag_update(x, y)
                self.refresh(urgent=True)
                return

    def _move(self, x, y):
        tc = self.touch
        if tc is None:
            return
        if tc['t'] == 'drag':
            if self.drag is not None:
                self._drag_update(x, y)
                self.refresh()
            return
        rect = self._rects().get(tc['t'])
        if rect is None:
            return
        inside = _inside(rect, x, y, HIT_SLOP)
        if inside != tc['inside']:
            tc['inside'] = inside
            self.pressed = tc['t'] if inside else None
            self.refresh(urgent=True)

    def _up(self, x, y):
        tc, self.touch = self.touch, None
        if tc is None:
            return
        if tc['t'] == 'drag':
            self._drop()
            return
        was = self.pressed is not None
        self.pressed = None
        rect = self._rects().get(tc['t'])
        if rect is not None and tc['inside'] and _inside(rect, x, y, HIT_SLOP):
            self._activate(tc['t'])
        elif was:
            self.refresh(urgent=True)

    def _activate(self, name):
        if name == 'back':
            self.exit()
        elif name == 'new':
            if self.game.over or self.game.moves == 0 or self.confirm_new:
                self._new_game()
            else:
                self.confirm_new = True
                self.later('confirm', CONFIRM_SECONDS, self._confirm_end)
                self.refresh(urgent=True)
        elif name == 'again':
            self._new_game()

    def _confirm_end(self):
        self._timers.pop('confirm', None)
        if self.confirm_new:
            self.confirm_new = False
            self.refresh()

    def _new_game(self):
        self.cancel('confirm')
        self.cancel('anim')
        self.cancel('msg')
        self.confirm_new = False
        self.anim = None
        self.msg = None
        self.drag = None
        self.over_at = None
        self.game.new()
        self.save_now(force=True)
        self.refresh(urgent=True)

    # ------------------------------------------------------------ dra och släppa
    def _drag_update(self, x, y):
        d = self.drag
        sh = self.game.pieces[d['slot']].shape
        d['x'], d['y'] = x, y
        left = x - sh.w * CELL / 2.0
        top = y - GRAB_DY - sh.h * CELL
        d['left'], d['top'] = left, top
        gc, gr = (left - BX) / float(CELL), (top - BY) / float(CELL)
        best = None
        for r in (int(math.floor(gr)), int(math.floor(gr)) + 1):
            for c in (int(math.floor(gc)), int(math.floor(gc)) + 1):
                if self.game.can_place(sh, r, c):
                    dist = math.hypot(r - gr, c - gc)
                    if dist <= SNAP_DIST and (best is None or dist < best[0]):
                        best = (dist, r, c)
        if best is None:
            d['snap'], d['clear'] = None, 0
        else:
            d['snap'] = (best[1], best[2])
            d['clear'] = self.game.preview(sh, best[1], best[2])

    def _drop(self):
        d, self.drag = self.drag, None
        if d is None:
            return
        if d['snap'] is None:
            self.refresh(urgent=True)
            return
        res = self.game.place(d['slot'], d['snap'][0], d['snap'][1])
        if res is None:
            self.refresh(urgent=True)
            return
        self._after_move(res)

    def _after_move(self, res):
        self.confirm_new = False
        self.cancel('confirm')
        if res['cleared']:
            self.anim = {'cells': res['cleared'], 'step': 0}
            self.later('anim', ANIM_DT, self._anim_tick)
        self._set_message(res)
        if res['over']:
            self.over_at = self.loop.time()
            self.save_now(force=True)
        else:
            self.save_soon()
        self.refresh(urgent=True)

    def _anim_tick(self):
        self._timers.pop('anim', None)
        a = self.anim
        if a is None:
            return
        a['step'] += 1
        if a['step'] >= ANIM_STEPS:
            self.anim = None
        else:
            self.later('anim', ANIM_DT, self._anim_tick)
        self.refresh()

    def _set_message(self, res):
        lines, gain = res['lines'], res['gain']
        if res['empty']:
            txt = 'Helt tomt! +%s' % thousands(gain)
        elif lines:
            name = {1: 'Rad borta!', 2: 'Dubbel!', 3: 'Trippel!'}.get(lines, 'Fantastiskt!')
            txt = '%s +%s' % (name, thousands(gain))
            if res['combo'] >= 2:
                txt = 'Kombo ×%d! +%s' % (res['combo'], thousands(gain))
        else:
            self.msg = None
            self.cancel('msg')
            return
        self.msg = txt
        self.later('msg', MSG_SECONDS, self._msg_end)

    def _msg_end(self):
        self._timers.pop('msg', None)
        if self.msg is not None:
            self.msg = None
            self.refresh()

    # ------------------------------------------------------------ ritning
    def draw(self, gen):
        """Ritar det som ändrats sedan sist. gen ändras när hela skärmen ska ritas om."""
        img = self.s.img
        full = gen != self._gen
        if full:
            self._gen = gen
            self._keys = {}
            self.ov_rect, self.ov_key = None, None
            self.bg.paste(T.BG, (0, 0, W, H))
        g = self.game
        self._clock = self.clock
        anim_step = self.anim['step'] if self.anim else -1
        fits = tuple(g.piece_fits(i) for i in range(3))
        drag_slot = self.drag['slot'] if self.drag else None
        tray = tuple(None if p is None else (p.shape.name, p.color, fits[i], drag_slot == i)
                     for i, p in enumerate(g.pieces))
        again_pr = self.pressed == 'again'
        parts = (
            ('head', HEAD_RECT, (self.pressed == 'back',), self._part_head),
            ('clock', CLOCK_RECT, (self._clock,), self._part_clock),
            ('board', CARD, (tuple(g.col), anim_step, g.over, g.new_best if g.over else 0, again_pr, g.score if g.over else 0),
             self._paint_board),
            ('score', SCORE_RECT, (g.score, g.best, g.new_best), self._paint_score),
            ('tray', TRAY_RECT, tray, self._paint_tray),
            ('msg', MSG_RECT, (self.msg, g.over), self._paint_msg),
            ('new', NEW_RECT, (self.pressed == 'new', self.confirm_new, g.over), self._paint_new),
            ('combo', COMBO_RECT, (g.combo,), self._paint_combo),
        )
        redrawn = []
        for name, rect, key, paint in parts:
            if self._keys.get(name) == key:
                continue
            self._keys[name] = key
            paint(self.bg, rect)
            self._copy(rect)
            redrawn.append(rect)
        self._draw_overlay(redrawn)

    def _copy(self, rect):
        r = _clip(rect)
        if r[2] <= r[0] or r[3] <= r[1]:
            return
        self.s.img.paste(self.bg.crop(r), (r[0], r[1]))
        self.s.mark(r)

    # --- det som rör sig: biten som dras, förhandsvisningen och rader som skulle rensas
    def _overlay_state(self):
        d = self.drag
        if d is None:
            return None, None
        p = self.game.pieces[d['slot']]
        if p is None:
            return None, None
        sh = p.shape
        if d['snap'] is not None:
            r0, c0 = d['snap']
            x0, y0 = BX + c0 * CELL, BY + r0 * CELL
            rect = (x0, y0, x0 + sh.w * CELL, y0 + sh.h * CELL)
            if d['clear']:
                rect = BOARD
            return ('snap', d['slot'], d['snap'], d['clear']), rect
        left, top = int(round(d['left'])), int(round(d['top']))
        return ('float', d['slot'], left, top), (left, top, left + sh.w * CELL, top + sh.h * CELL)

    def _draw_overlay(self, redrawn):
        key, rect = self._overlay_state()
        old = self.ov_rect
        need = key != self.ov_key
        if not need and rect is not None:
            need = any(_meets(rect, r) for r in redrawn)
        if not need and key is None and old is not None:
            need = True
        if not need:
            return
        region = _clip(_union(old, rect)) if (old is not None or rect is not None) else None
        if region is not None and region[2] > region[0] and region[3] > region[1]:
            self.s.img.paste(self.bg.crop(region), (region[0], region[1]))
            self.s.mark(region)
        if key is not None:
            self._paint_overlay()
        self.ov_key, self.ov_rect = key, rect

    def _paint_overlay(self):
        img = self.s.img
        d = self.drag
        p = self.game.pieces[d['slot']]
        sh = p.shape
        spr, msk = block_sprite(p.color, CELL - 2 * GAP)
        if d['snap'] is not None:
            r0, c0 = d['snap']
            full = alpha_mask(msk, 0.92)
            for i in range(64):
                if d['clear'] >> i & 1:             # rader och kolumner som blir fulla lyser upp i bitens färg
                    x, y = cell_xy(i)
                    img.paste(spr, (x + GAP, y + GAP), full)
            solid = alpha_mask(msk, 0.66)
            for dr, dc in sh.cells:
                i = (r0 + dr) * 8 + c0 + dc
                if not d['clear'] >> i & 1:
                    x, y = cell_xy(i)
                    img.paste(spr, (x + GAP, y + GAP), solid)
        else:
            solid = alpha_mask(msk, 0.78)
            left, top = int(round(d['left'])), int(round(d['top']))
            for dr, dc in sh.cells:
                img.paste(spr, (left + dc * CELL + GAP, top + dr * CELL + GAP), solid)

    # --- fasta delar
    def _part_head(self, bg, rect):
        self._back_rect = sdk.paint_head(bg, self.title, self.pressed == 'back')

    def _part_clock(self, bg, rect):
        sdk.paint_clock(bg, self._clock)

    def _paint_board(self, bg, rect):
        g = self.game
        card = draw_board_card(CARD[2] - CARD[0], CARD[3] - CARD[1])
        bg.paste(card, (CARD[0], CARD[1]))
        for i, c in enumerate(g.col):
            if c:
                spr, msk = block_sprite(c, CELL - 2 * GAP)
                x, y = cell_xy(i)
                bg.paste(spr, (x + GAP, y + GAP), msk)
        a = self.anim
        if a is not None:
            k = a['step']
            f = 1.0 - k / float(ANIM_STEPS)
            size = max(6, int(round((CELL - 2 * GAP) * f)))
            for i, c in a['cells']:
                spr, msk = block_sprite(c, size)
                if k == 0:
                    spr = Image.blend(spr, Image.new('RGB', spr.size, (255, 255, 255)), 0.45)
                x, y = cell_xy(i)
                off = (CELL - size) // 2
                bg.paste(spr, (x + off, y + off), msk)
        if g.over:
            self._paint_over(bg)

    def _paint_over(self, bg):
        g = self.game
        w, h = CARD[2] - CARD[0], CARD[3] - CARD[1]
        dark = rbox_mask(w, h, 18).point([int(i * 0.84) for i in range(256)])
        bg.paste((0, 0, 0), (CARD[0], CARD[1]), dark)
        cx = (BX + BOARD[2]) // 2
        _centered(bg, cx, 218, 'Spelet slut', 500, 44, T.TEXT)
        _centered(bg, cx, 268, 'Poäng', 400, 20, T.MUTED)
        _centered(bg, cx, 334, thousands(g.score), 300, 54, T.TEXT)
        if g.new_best and g.score > 0:
            _centered(bg, cx, 376, 'Nytt rekord!', 500, 22, T.YELLOW)
        x0, y0, x1, y1 = AGAIN_RECT
        fill = T.BLUE_D
        if self.pressed == 'again':
            fill = blend(fill, (255, 255, 255), 0.12)
        bbox(bg, x0, y0, x1, y1, 20, fill, T.BLUE, 2)
        _centered(bg, (x0 + x1) // 2, (y0 + y1) // 2 + 9, 'Spela igen', 500, 24, T.TEXT)

    def _paint_score(self, bg, rect):
        g = self.game
        _clear(bg, rect)
        x0, y0, x1, y1 = rect
        bbox(bg, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
        text(bg, x0 + 24, y0 + 32, 'Poäng', 400, 15, T.MUTED)
        text(bg, x0 + 22, y0 + 82, thousands(g.score), 300, 54, T.TEXT)
        text(bg, x1 - 24, y0 + 32, 'Nytt rekord!' if (g.new_best and g.score >= g.best and g.score > 0) else 'Rekord',
             500 if g.new_best else 400, 15, T.YELLOW if (g.new_best and g.score >= g.best and g.score > 0) else T.MUTED,
             anchor='rs')
        text(bg, x1 - 24, y0 + 80, thousands(g.best), 400, 34, T.TEXT, anchor='rs')

    def _paint_tray(self, bg, rect):
        _clear(bg, rect)
        x0, y0, x1, y1 = rect
        bbox(bg, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
        for i, sr in enumerate(SLOTS):
            rbox(bg, sr[0], sr[1], sr[2], sr[3], 14, SLOT_BG)
            p = self.game.pieces[i]
            if p is None or (self.drag is not None and self.drag['slot'] == i):
                continue
            sh = p.shape
            fits = self.game.piece_fits(i)
            spr, msk = block_sprite(p.color, MINI - 4, 0.0 if fits else 0.72)
            ox = sr[0] + (SLOT_W - sh.w * MINI) // 2
            oy = sr[1] + (SLOT_H - sh.h * MINI) // 2
            for dr, dc in sh.cells:
                bg.paste(spr, (ox + dc * MINI + 2, oy + dr * MINI + 2), msk)

    def _paint_msg(self, bg, rect):
        _clear(bg, rect)
        cx = (rect[0] + rect[2]) // 2
        if self.msg:
            _centered(bg, cx, 440, self.msg, 500, 30, T.YELLOW)
        elif self.game.over:
            _centered(bg, cx, 440, 'Inga bitar får plats', 400, 22, T.MUTED)
        else:
            _centered(bg, cx, 438, 'Dra en bit till rutnätet', 400, 22, T.MUTED)
            _centered(bg, cx, 466, 'Fyll hela rader och kolumner', 400, 16, T.FOOT)

    def _paint_new(self, bg, rect):
        _clear(bg, rect)
        x0, y0, x1, y1 = rect
        if self.confirm_new:
            fill, border, label = T.WARN_D, T.WARN_BORDER, 'Tryck igen'
        elif self.game.over:
            fill, border, label = T.BLUE_D, T.BLUE, 'Nytt spel'
        else:
            fill, border, label = T.CARD, T.CARD_BORDER, 'Nytt spel'
        if self.pressed == 'new':
            fill = blend(fill, (255, 255, 255), 0.09)
        bbox(bg, x0, y0, x1, y1, 20, fill, border, 2 if (self.confirm_new or self.game.over) else 1)
        icon(bg, 'Restart', 40, x0 + 22, y0 + (y1 - y0 - 40) // 2, T.BLUE_L if not self.confirm_new else T.WARN)
        text(bg, x0 + 78, y0 + (y1 - y0) // 2 + 9, label, 500, 24, T.TEXT)

    def _paint_combo(self, bg, rect):
        _clear(bg, rect)
        n = self.game.combo
        if n < 2:
            return
        x0, y0, x1, y1 = rect
        bbox(bg, x0, y0, x1, y1, 20, T.WARN_D, T.WARN_BORDER, 1)
        _centered(bg, (x0 + x1) // 2, y0 + 33, 'Kombo', 400, 15, T.MUTED)
        _centered(bg, (x0 + x1) // 2, y0 + 66, '×%d' % n, 500, 32, T.WARN)
