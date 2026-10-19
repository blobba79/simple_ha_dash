"""Patians: klassisk Klondike-solitär. Bygg upp fyra högar i färg från Ess till Kung.
Tryck på ett kort för att välja det (det blir blått), tryck sedan där det ska ligga. Gröna ramar visar
var det valda kortet får läggas. Tryck på ett valt kort en gång till för att lägga upp det på en grundhög."""
import copy
from PIL import Image, ImageDraw
from dashpanel import gamesdk as sdk

META = {
    'api': 1,
    'id': 'patians',
    'name': 'Patians',
    'desc': 'Klassisk solitär. Bygg upp fyra högar i färg från Ess till Kung.',
    'version': 2,
}

SAVE_VERSION = 2

# ---------------------------------------------------------------- layout
CW, CH = 96, 134                 # kortets storlek
CR = 8                           # hörnradie
COL_X = [16 + i * 108 for i in range(7)]
TAB_Y = 96
TAB_BOTTOM = 592
DOWN_OFF = 16                    # avstånd mellan nedvända kort i en kolumn
UP_OFF = 36                      # avstånd mellan uppvända kort
UP_MIN = 27                      # minst så här mycket av ett uppvänt kort syns (valör och färg)

PX = (784, 896)                  # högerpanelens två kolumner
STOCK = (PX[0], 96, PX[0] + CW, 96 + CH)
WASTE = (PX[1], 96, PX[1] + CW, 96 + CH)
FOUND = [(PX[0], 240, PX[0] + CW, 240 + CH), (PX[1], 240, PX[1] + CW, 240 + CH),
         (PX[0], 384, PX[0] + CW, 384 + CH), (PX[1], 384, PX[1] + CW, 384 + CH)]
UNDO = (PX[0], 528, PX[0] + CW, 592)
NEW = (PX[1], 528, PX[1] + CW, 592)
WIN_BOX = (150, 210, 630, 470)
WIN_BTN = (270, 380, 510, 448)

# ---------------------------------------------------------------- färger
FACE = (250, 250, 250)           # vit kortyta
FACE_SEL = (200, 228, 255)       # valt kort: ljusblått
FACE_BORDER = (150, 150, 150)
RED_C = (200, 30, 30)
BLACK_C = (20, 20, 20)
BACK = (0x1d, 0x4f, 0x91)
BACK_L = (0x4f, 0x86, 0xc6)
SLOT_BG = (0x18, 0x18, 0x18)
SLOT_BORDER = (0x3a, 0x3a, 0x3a)
SEL_RING = sdk.BLUE
HINT_RING = sdk.GREEN

SUITS = 'HDSC'                   # hjärter, ruter, spader, klöver
RANK_TXT = {1: 'E', 11: 'Kn', 12: 'D', 13: 'K'}

_CACHE = {}                      # färdigritade bilder (fylls vid behov)


def _rank_txt(r):
    return RANK_TXT.get(r, str(r))


def _is_red(card):
    return card[1] in 'HD'


# ---------------------------------------------------------------- färgsymboler (kantutjämnade)
def _suit_mask(suit, size):
    key = ('suit', suit, size)
    m = _CACHE.get(key)
    if m is not None:
        return m
    k = 4
    s = size * k
    big = Image.new('L', (s, s), 0)

    def P(x, y):
        return (int(x * s / 100), int(y * s / 100))

    def disc(cx, cy, r):
        sdk.circle(big, int((cx - r) * s / 100), int((cy - r) * s / 100), int(2 * r * s / 100), 255)

    d = ImageDraw.Draw(big)
    if suit == 'D':
        d.polygon([P(50, 0), P(88, 50), P(50, 100), P(12, 50)], fill=255)
    elif suit == 'H':
        disc(28, 30, 26)
        disc(72, 30, 26)
        d.polygon([P(4, 38), P(96, 38), P(50, 96)], fill=255)
    elif suit == 'S':
        disc(28, 58, 24)
        disc(72, 58, 24)
        d.polygon([P(6, 52), P(94, 52), P(50, 2)], fill=255)
        d.polygon([P(50, 60), P(32, 100), P(68, 100)], fill=255)
    else:  # 'C'
        disc(50, 26, 23)
        disc(25, 60, 23)
        disc(75, 60, 23)
        disc(50, 50, 14)
        d.polygon([P(50, 48), P(32, 100), P(68, 100)], fill=255)
    m = big.resize((size, size), Image.LANCZOS)
    _CACHE[key] = m
    return m


def _paste_suit(im, suit, size, x, y, color):
    im.paste(color, (x, y), _suit_mask(suit, size))


# ---------------------------------------------------------------- kortbilder
def _card_im(rank, suit, selected=False):
    key = ('card', rank, suit, selected)
    im = _CACHE.get(key)
    if im is not None:
        return im
    bg = FACE_SEL if selected else FACE
    border = SEL_RING if selected else FACE_BORDER
    im = Image.new('RGB', (CW, CH), sdk.BG)
    sdk.bbox(im, 0, 0, CW, CH, CR, bg, border, 3 if selected else 1)
    col = RED_C if suit in 'HD' else BLACK_C
    txt = _rank_txt(rank)
    # Hörnet uppe: valör till vänster, färg till höger (syns även när korten ligger tätt)
    sdk.text(im, 7, 25, txt, 500, 25, col)
    _paste_suit(im, suit, 20, CW - 27, 6, col)
    # Mitten
    if rank in (11, 12, 13):
        sdk.bbox(im, 14, 36, CW - 14, CH - 14, 6, bg, col, 2)
        sdk.centered(im, CW // 2, 84, txt, 500, 38, col)
        _paste_suit(im, suit, 26, CW // 2 - 13, 92, col)
    elif rank == 1:
        _paste_suit(im, suit, 54, CW // 2 - 27, 56, col)
    else:
        _paste_suit(im, suit, 44, CW // 2 - 22, 60, col)
    _CACHE[key] = im
    return im


def _back_im():
    im = _CACHE.get('back')
    if im is not None:
        return im
    im = Image.new('RGB', (CW, CH), sdk.BG)
    sdk.bbox(im, 0, 0, CW, CH, CR, BACK, (230, 230, 230), 3)
    sdk.bbox(im, 8, 8, CW - 8, CH - 8, 4, BACK, BACK_L, 2)
    for yy in range(16, CH - 20, 14):
        for xx in range(16, CW - 20, 14):
            if (xx + yy) % 28 == 4:
                _paste_suit(im, 'D', 10, xx, yy, BACK_L)
    _CACHE['back'] = im
    return im


def _mask():
    return sdk.rbox_mask(CW, CH, CR)


def _paste_card(img, im, x, y):
    img.paste(im, (x, y), _mask())


def _ring(img, r, color, w=4):
    """Ram runt en ruta (ritas före kortet så att bara kanten syns)."""
    sdk.rbox(img, r[0] - w, r[1] - w, r[2] + w, r[3] + w, CR + w, color)


def _slot(img, r, label=None, hint=False):
    sdk.bbox(img, r[0], r[1], r[2], r[3], CR, SLOT_BG, HINT_RING if hint else SLOT_BORDER, 3 if hint else 2)
    if label:
        sdk.centered(img, (r[0] + r[2]) // 2, (r[1] + r[3]) // 2 + 12, label, 400, 32, sdk.STALE_TEXT)


# ================================================================ spelväljaren
def draw_icon(im):
    """Ikon: tre kort i en solfjäder (ett nedvänt, K i hjärter och E i spader)."""
    w, h = 54, 76
    for i, (kind, rank, suit) in enumerate([('back', 0, ''), ('card', 13, 'H'), ('card', 1, 'S')]):
        x, y = 14 + i * 24, 26 - (i % 2) * 6
        if kind == 'back':
            sdk.bbox(im, x, y, x + w, y + h, 6, BACK, (230, 230, 230), 2)
            sdk.bbox(im, x + 6, y + 6, x + w - 6, y + h - 6, 3, BACK, BACK_L, 2)
        else:
            col = RED_C if suit in 'HD' else BLACK_C
            sdk.bbox(im, x, y, x + w, y + h, 6, FACE, FACE_BORDER, 1)
            sdk.text(im, x + 5, y + 20, _rank_txt(rank), 500, 19, col)
            _paste_suit(im, suit, 26, x + w // 2 - 13, y + 36, col)


def status(data):
    """Raden i spelväljaren."""
    if not data or data.get('v') != SAVE_VERSION:
        return None
    try:
        if data.get('won'):
            return 'Klart på %d drag' % int(data.get('moves', 0)), False
        up = sum(len(f) for f in data.get('found', []))
        if int(data.get('moves', 0)) > 0:
            return 'Pågående · %d av 52 upplagda' % up, True
        if data.get('best'):
            return 'Rekord %d drag' % int(data['best']), False
    except (TypeError, ValueError):
        return None
    return None


# ================================================================ spelet
class Game(sdk.GameBase):
    def setup(self):
        self.best = 0
        self.wins = 0
        self.confirm = False
        self._new_deal()

    def _new_deal(self):
        deck = [[r, s] for s in SUITS for r in range(1, 14)]
        self.rng.shuffle(deck)
        self.tab = []
        i = 0
        for c in range(7):
            col = []
            for row in range(c + 1):
                r, s = deck[i]
                i += 1
                col.append([r, s, row == c])      # [valör, färg, uppvänt]
            self.tab.append(col)
        self.stock = deck[i:]                     # sista i listan är översta kortet
        self.waste = []
        self.found = [[], [], [], []]
        self.moves = 0
        self.won = False
        self.sel = None
        self.undo_stack = []
        self.auto = False
        self._set_title()

    # ---------------------------------------------------------------- spara
    def state(self):
        return {
            'v': SAVE_VERSION,
            'stock': self.stock,
            'waste': self.waste,
            'found': self.found,
            'tab': self.tab,
            'moves': self.moves,
            'won': self.won,
            'best': self.best,
            'wins': self.wins,
        }

    def restore(self, data):
        if not isinstance(data, dict):
            return False
        if data.get('v') != SAVE_VERSION:
            return True                           # sparfil från gamla versionen: börja på en ny giv
        seen = set()

        def card(c):
            r, s = int(c[0]), str(c[1])
            if not (1 <= r <= 13) or s not in SUITS or (r, s) in seen:
                raise ValueError('kort')
            seen.add((r, s))
            return [r, s]

        stock = [card(c) for c in data['stock']]
        waste = [card(c) for c in data['waste']]
        found = [[card(c) for c in f] for f in data['found']]
        if len(found) != 4:
            return False
        for f in found:
            for k, c in enumerate(f):
                if c[0] != k + 1 or c[1] != f[0][1]:
                    return False
        tab = []
        for col in data['tab']:
            tab.append([card(c) + [bool(c[2])] for c in col])
        if len(tab) != 7 or len(seen) != 52:
            return False
        self.stock, self.waste, self.found, self.tab = stock, waste, found, tab
        self.moves = int(data.get('moves', 0))
        self.won = bool(data.get('won', False))
        self.best = int(data.get('best', 0))
        self.wins = int(data.get('wins', 0))
        self.sel = None
        self.undo_stack = []
        self.auto = False
        self._set_title()
        return True

    def on_open(self):
        self.sel = None
        self.confirm = False
        self._set_title()
        self._maybe_auto()

    def on_close(self):
        self.sel = None
        self.confirm = False
        self.auto = False

    def _set_title(self):
        self.title = 'Patians · %d drag' % self.moves if self.moves else 'Patians'

    # ---------------------------------------------------------------- regler
    def _found_count(self):
        return sum(len(f) for f in self.found)

    def _sel_cards(self):
        """Korten som det valda omfattar (översta sist), eller []."""
        s = self.sel
        if s is None:
            return []
        if s[0] == 'waste':
            return [self.waste[-1]] if self.waste else []
        if s[0] == 'found':
            f = self.found[s[1]]
            return [f[-1]] if f else []
        col = self.tab[s[1]]
        if s[2] >= len(col) or not col[s[2]][2]:
            return []
        return col[s[2]:]

    def _ok_found(self, cards, fi):
        if len(cards) != 1:
            return False
        if self.sel and self.sel[0] == 'found' and self.sel[1] == fi:
            return False
        c = cards[0]
        pile = self.found[fi]
        if not pile:
            return c[0] == 1
        top = pile[-1]
        return top[1] == c[1] and c[0] == top[0] + 1

    def _ok_tab(self, cards, ci):
        if not cards:
            return False
        if self.sel and self.sel[0] == 'tab' and self.sel[1] == ci:
            return False
        c = cards[0]
        col = self.tab[ci]
        if not col:
            return c[0] == 13
        top = col[-1]
        return top[2] and _is_red(top) != _is_red(c) and c[0] == top[0] - 1

    def _snapshot(self):
        self.undo_stack.append(copy.deepcopy((self.stock, self.waste, self.found, self.tab, self.moves)))
        if len(self.undo_stack) > 200:
            del self.undo_stack[0]

    def _take_sel(self):
        """Ta bort de valda korten från sin plats och ge dem (utan uppvänt-flagga)."""
        s = self.sel
        if s[0] == 'waste':
            return [self.waste.pop()]
        if s[0] == 'found':
            return [self.found[s[1]].pop()]
        col = self.tab[s[1]]
        moving = col[s[2]:]
        del col[s[2]:]
        if col and not col[-1][2]:
            col[-1][2] = True                     # vänd kortet som blev överst
        return [[c[0], c[1]] for c in moving]

    def _move_to(self, kind, i):
        cards = self._sel_cards()
        ok = self._ok_found(cards, i) if kind == 'found' else self._ok_tab(cards, i)
        if not ok:
            return False
        self._snapshot()
        moving = self._take_sel()
        if kind == 'found':
            self.found[i].append(moving[0])
        else:
            self.tab[i].extend([[c[0], c[1], True] for c in moving])
        self.sel = None
        self._after_move()
        return True

    def _auto_found(self):
        """Lägg det valda kortet på en grundhög om det går."""
        cards = self._sel_cards()
        for fi in range(4):
            if self._ok_found(cards, fi):
                return self._move_to('found', fi)
        return False

    def _after_move(self):
        self.moves += 1
        self.confirm = False
        self.cancel('confirm')
        if self._found_count() == 52:
            self.won = True
            self.auto = False
            self.wins += 1
            if not self.best or self.moves < self.best:
                self.best = self.moves
            self._set_title()
            self.refresh()
            self.invalidate()
            self.save_now(force=True)
            return
        self._set_title()
        self.refresh()
        self.invalidate()
        self.save_soon()
        self._maybe_auto()

    def _all_open(self):
        return (not self.stock and not self.waste and
                all(c[2] for col in self.tab for c in col))

    def _maybe_auto(self):
        """Allt är uppvänt och leken slut: lägg upp resten av sig själv."""
        if not self.won and not self.auto and self._all_open() and self._found_count() < 52:
            self.auto = True
            self.later('auto', 0.15, self._auto_step)

    def _auto_step(self):
        if not self.auto or self.won:
            self.auto = False
            return
        best = None
        for ci, col in enumerate(self.tab):
            if not col:
                continue
            c = col[-1]
            for fi in range(4):
                pile = self.found[fi]
                if (not pile and c[0] == 1) or (pile and pile[-1][1] == c[1] and pile[-1][0] + 1 == c[0]):
                    if best is None or c[0] < best[0]:
                        best = (c[0], ci, fi)
                    break
        self.auto = False
        if best is None:
            return
        self.sel = ('tab', best[1], len(self.tab[best[1]]) - 1)
        self._move_to('found', best[2])           # startar nästa steg via _maybe_auto

    # ---------------------------------------------------------------- tryck
    def _select(self, s):
        self.sel = s if self._sel_from(s) else None

    def _sel_from(self, s):
        old = self.sel
        self.sel = s
        ok = bool(self._sel_cards())
        self.sel = old
        return ok

    def on_tap(self, name):
        if name == 'new' or name == 'win_new':
            if self.won or self.moves == 0 or self.confirm or name == 'win_new':
                self.cancel('confirm')
                self.cancel('auto')
                self.confirm = False
                self._new_deal()
                self.refresh()
                self.invalidate()
                self.save_now(force=True)
            else:
                self.confirm = True
                self.later('confirm', 3.0, self._unconfirm)
                self.invalidate(NEW)
            return
        if name == 'undo':
            if self.undo_stack and not self.won:
                self.stock, self.waste, self.found, self.tab, self.moves = self.undo_stack.pop()
                self.sel = None
                self.auto = False
                self.cancel('auto')
                self._set_title()
                self.refresh()
                self.invalidate()
                self.save_soon()
            return
        if self.won or self.auto:
            return

        if name == 'stock':
            self.sel = None
            if not self.stock and not self.waste:
                return
            self._snapshot()
            if self.stock:
                self.waste.append(self.stock.pop())
            else:
                while self.waste:
                    self.stock.append(self.waste.pop())
            self._after_move()
            return

        if name == 'waste':
            if self.sel and self.sel[0] == 'waste':
                if not self._auto_found():
                    self.sel = None
            else:
                self._select(('waste',))
            self.invalidate()
            return

        if name.startswith('found:'):
            fi = int(name.split(':')[1])
            if self.sel is None:
                self._select(('found', fi))
            elif self.sel == ('found', fi):
                self.sel = None
            elif not self._move_to('found', fi):
                self._select(('found', fi))
            self.invalidate()
            return

        if name.startswith('tab:'):
            _, ci, j = name.split(':')
            ci, j = int(ci), int(j)
            s = self.sel
            if s is None:
                self._select(('tab', ci, j))
            elif s == ('tab', ci, j):
                if j != len(self.tab[ci]) - 1 or not self._auto_found():
                    self.sel = None
            elif s[0] == 'tab' and s[1] == ci:
                self._select(('tab', ci, j))
            elif not self._move_to('tab', ci):
                self._select(('tab', ci, j))
            self.invalidate()
            return

        if name.startswith('col:'):
            ci = int(name.split(':')[1])
            if self.sel is not None and not self._move_to('tab', ci):
                self.sel = None
            self.invalidate()
            return

    def _unconfirm(self):
        self.confirm = False
        self.invalidate(NEW)

    # ---------------------------------------------------------------- geometri
    def _col_ys(self, ci):
        """y för varje kort i kolumnen; trycks ihop så att kolumnen ryms på skärmen."""
        col = self.tab[ci]
        n = len(col)
        if not n:
            return []
        nd = sum(1 for c in col[:-1] if not c[2])
        nu = n - 1 - nd                               # uppvända kort som har ett kort ovanpå sig
        avail = TAB_BOTTOM - TAB_Y - CH
        d, u = DOWN_OFF, UP_OFF
        if nd * d + nu * u > avail and nu:
            u = max(UP_MIN, (avail - nd * d) // nu)
        if nd * d + nu * u > avail and nd:
            d = max(6, (avail - nu * u) // nd)
        if nd * d + nu * u > avail and nu:
            u = max(10, (avail - nd * d) // nu)
        ys = []
        y = TAB_Y
        for c in col:
            ys.append(y)
            y += u if c[2] else d
        return ys

    def targets(self):
        ts = []
        if self.won:
            ts.append(('win_new', WIN_BTN))
        ts.append(('undo', UNDO))
        ts.append(('new', NEW))
        if self.won:
            return ts
        if self.stock or self.waste:
            ts.append(('stock', STOCK))
        if self.waste:
            ts.append(('waste', WASTE))
        for fi in range(4):
            ts.append(('found:%d' % fi, FOUND[fi]))
        for ci, col in enumerate(self.tab):
            x = COL_X[ci]
            ys = self._col_ys(ci)
            for j in range(len(col) - 1, -1, -1):
                if not col[j][2]:
                    break
                ts.append(('tab:%d:%d' % (ci, j), (x, ys[j], x + CW, ys[j] + CH)))
            ts.append(('col:%d' % ci, (x, TAB_Y, x + CW, TAB_BOTTOM)))
        return ts

    # ---------------------------------------------------------------- ritning
    def _hints(self):
        """Platser där det valda får läggas."""
        cards = self._sel_cards()
        if not cards:
            return set()
        h = set()
        for fi in range(4):
            if self._ok_found(cards, fi):
                h.add(('found', fi))
        for ci in range(7):
            if self._ok_tab(cards, ci):
                h.add(('tab', ci))
        return h

    def paint(self, img, rect):
        hints = self._hints()
        sel = self.sel

        # Lek
        if sdk.meets(rect, STOCK):
            if self.stock:
                _paste_card(img, _back_im(), STOCK[0], STOCK[1])
                cx, cy = (STOCK[0] + STOCK[2]) // 2, (STOCK[1] + STOCK[3]) // 2
                sdk.rbox(img, cx - 22, cy - 16, cx + 22, cy + 16, 16, (0x10, 0x2a, 0x4e))
                sdk.centered(img, cx, cy + 8, str(len(self.stock)), 500, 22, (240, 240, 240))
            elif self.waste:
                _slot(img, STOCK)
                sdk.centered(img, (STOCK[0] + STOCK[2]) // 2, STOCK[1] + 72, 'Vänd', 500, 20, sdk.MUTED)
                sdk.centered(img, (STOCK[0] + STOCK[2]) // 2, STOCK[1] + 96, 'leken', 500, 20, sdk.MUTED)
            else:
                _slot(img, STOCK)

        # Slänghög
        if sdk.meets(rect, (WASTE[0] - 6, WASTE[1] - 6, WASTE[2] + 6, WASTE[3] + 6)):
            if self.waste:
                c = self.waste[-1]
                is_sel = sel is not None and sel[0] == 'waste'
                if is_sel:
                    _ring(img, WASTE, SEL_RING)
                _paste_card(img, _card_im(c[0], c[1], is_sel), WASTE[0], WASTE[1])
            else:
                _slot(img, WASTE)

        # Grundhögar
        for fi in range(4):
            fr = FOUND[fi]
            if not sdk.meets(rect, (fr[0] - 6, fr[1] - 6, fr[2] + 6, fr[3] + 6)):
                continue
            pile = self.found[fi]
            hint = ('found', fi) in hints
            if pile:
                c = pile[-1]
                is_sel = sel == ('found', fi)
                if is_sel:
                    _ring(img, fr, SEL_RING)
                elif hint:
                    _ring(img, fr, HINT_RING)
                _paste_card(img, _card_im(c[0], c[1], is_sel), fr[0], fr[1])
            else:
                _slot(img, fr, 'E', hint)

        # Knappar
        if sdk.meets(rect, UNDO):
            sdk.button(img, UNDO, 'Ångra', 'normal', self.pressed == 'undo',
                       enabled=bool(self.undo_stack) and not self.won, size=19)
        if sdk.meets(rect, NEW):
            if self.confirm:
                sdk.button(img, NEW, 'Säker?', 'warn', self.pressed == 'new', size=19)
            else:
                sdk.button(img, NEW, 'Ny giv', 'normal', self.pressed == 'new', size=19)

        # Spelplanen
        for ci in range(7):
            x = COL_X[ci]
            colr = (x - 6, TAB_Y - 6, x + CW + 6, TAB_BOTTOM + 6)
            if not sdk.meets(rect, colr):
                continue
            col = self.tab[ci]
            hint = ('tab', ci) in hints
            if not col:
                _slot(img, (x, TAB_Y, x + CW, TAB_Y + CH), 'K' if hint else None, hint)
                continue
            ys = self._col_ys(ci)
            sel_j = sel[2] if (sel is not None and sel[0] == 'tab' and sel[1] == ci) else None
            last = len(col) - 1
            for j, c in enumerate(col):
                y = ys[j]
                if j == sel_j:
                    _ring(img, (x, y, x + CW, ys[last] + CH), SEL_RING)
                elif j == last and hint:
                    _ring(img, (x, y, x + CW, y + CH), HINT_RING)
                if not sdk.meets(rect, (x - 6, y - 6, x + CW + 6, y + CH + 6)) and j != sel_j:
                    continue
                if c[2]:
                    im = _card_im(c[0], c[1], sel_j is not None and j >= sel_j)
                else:
                    im = _back_im()
                _paste_card(img, im, x, y)

        # Vinst
        if self.won and sdk.meets(rect, WIN_BOX):
            sdk.bbox(img, WIN_BOX[0], WIN_BOX[1], WIN_BOX[2], WIN_BOX[3], 20, sdk.CARD, sdk.GREEN_BORDER, 2)
            cx = (WIN_BOX[0] + WIN_BOX[2]) // 2
            sdk.centered(img, cx, WIN_BOX[1] + 70, 'Klart!', 500, 52, sdk.GREEN)
            line = '%d drag' % self.moves
            if self.best:
                line += ' · rekord %d' % self.best
            sdk.centered(img, cx, WIN_BOX[1] + 120, line, 400, 26, sdk.TEXT)
            sdk.button(img, WIN_BTN, 'Ny giv', 'primary', self.pressed == 'win_new', size=26)
