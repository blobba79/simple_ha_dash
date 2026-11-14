"""Candy Fall: matcha godisar innan tiden rinner ut! Dra mellan intilliggande rutor for att byta platser.
3+ i rad = borta + tid. 4 = radrensare. 5+ = bomb som rensar 3x3. Specialer = MASSIV tid!"""
from dashpanel import gamesdk as sdk
import time

META = {
    'api': 1,
    'id': 'candyfall',
    'name': 'Candy Fall',
    'desc': 'Matcha godisar innan tiden rinner ut! 3+ = tid, specialer = MASSIV tid!',
    'version': 1,
}

# --- brade ---
COLS, ROWS = 8, 7
CELL = 64
PAD = 16
BX, BY = PAD, 148                       # bradets ovre vatra
BOARD = (BX - PAD, BY - PAD, BX + COLS * CELL + PAD, BY + ROWS * CELL + PAD)
BOARD_W = COLS * CELL
BOARD_H = ROWS * CELL

# --- HUD ---
HUD = (PAD, 96, 1024 - PAD, 120)
TIME_BAR = (PAD, 124, 1024 - PAD, 144)
TIME_BAR_BG = (PAD + 4, 128, 1024 - PAD - 4, 140)
SCORE = (PAD, 128, 300, 152)

# Overlay / start-knapp
OVERLAY = (262, 160, 762, 440)
START = (380, 340, 644, 400)

# --- farver (ljusa godisar pa mork bakgrund) ---
CANDY = [
    (239, 68, 68),    # 0 roed
    (59, 130, 246),   # 1 bla
    (34, 197, 94),    # 2 groen
    (250, 204, 21),   # 3 gul
    (168, 85, 247),   # 4 lila
    (251, 146, 60),   # 5 orange
]

# Speciel farver
SPECIAL_COLORS = [
    None,
    (255, 255, 255),  # radrensare (horisontell)
    (100, 255, 100),  # kolumnrensare (vertikal)
    (255, 100, 255),  # bomb (3x3)
]

# --- tid (allt i centisekunder = heltal) ---
INIT_TIME = 6000                           # starttid (60s * 100)
DRAIN = 100                                # centisekunder per sekund
TIME_3 = 100                               # tid for 3-match (1s)
TIME_4 = 150                               # tid for 4-match (1.5s)
TIME_5 = 200                               # tid for 5-match (2s)
TIME_SPECIAL = 100                         # tid for special-match (1s)
MAX_TIME = 9000                            # max 90s

# --- animation (allt i millisekunder for loop.t) ---
FALL_DURATION = 600                        # 600ms for fall
FADE_DURATION = 300                        # 300ms for fade out


def _candy_color(t):
    if isinstance(t, int) and 0 <= t < len(CANDY):
        return CANDY[t]
    return CANDY[0]


def _is_special(t):
    return isinstance(t, int) and t >= 10


def _special_type(t):
    if t == 10:
        return 0  # radrensare
    if t == 11:
        return 1  # kolumnrensare
    if t == 12:
        return 2  # bomb
    return -1


def _is_clearable(t):
    return t >= 0


# ================================================================
# Ritning av snyggare godisar med unika former
# ================================================================
def _draw_candy(img, cx, cy, t, size):
    """Ritar en godis med unik form baserad pa typ."""
    r = size // 2 - 4
    col = _candy_color(t)
    dark = (col[0] // 2, col[1] // 2, col[2] // 2)
    light = tuple(min(255, c + 80) for c in col)

    # Yttre skugga
    sdk.circle(img, cx - r + 2, cy - r + 2, r * 2, (0, 0, 0, 60))

    # Botten (3D-effekt)
    sdk.circle(img, cx - r + 1, cy - r + 1, r * 2, dark)

    # Huvudkropp
    sdk.circle(img, cx - r, cy - r, r * 2, col)

    # Inre highlight (ovre kant)
    sdk.circle(img, cx - r + 3, cy - r + 3, r * 2 - 6, light)

    # Unika former per typ
    if t == 0:
        # Rod - stjärna i mitten
        sdk.circle(img, cx - 3, cy - 3, 6, (255, 255, 255))
        sdk.circle(img, cx + 3, cy - 3, 6, (255, 255, 255))
        sdk.circle(img, cx - 3, cy + 3, 6, (255, 255, 255))
        sdk.circle(img, cx + 3, cy + 3, 6, (255, 255, 255))
        sdk.circle(img, cx, cy, 6, (255, 255, 255))
    elif t == 1:
        # Blå - våglinje
        sdk.circle(img, cx - 8, cy, 4, (255, 255, 255))
        sdk.circle(img, cx - 4, cy - 4, 4, (255, 255, 255))
        sdk.circle(img, cx, cy, 4, (255, 255, 255))
        sdk.circle(img, cx + 4, cy + 4, 4, (255, 255, 255))
        sdk.circle(img, cx + 8, cy, 4, (255, 255, 255))
    elif t == 2:
        # Grön - blad/klöver
        sdk.circle(img, cx - 5, cy - 5, 5, (255, 255, 255))
        sdk.circle(img, cx + 5, cy - 5, 5, (255, 255, 255))
        sdk.circle(img, cx - 5, cy + 5, 5, (255, 255, 255))
        sdk.circle(img, cx + 5, cy + 5, 5, (255, 255, 255))
        sdk.circle(img, cx, cy, 4, (255, 255, 255))
    elif t == 3:
        # Gul - solstralar
        sdk.circle(img, cx, cy - 8, 4, (255, 255, 255))
        sdk.circle(img, cx, cy + 8, 4, (255, 255, 255))
        sdk.circle(img, cx - 8, cy, 4, (255, 255, 255))
        sdk.circle(img, cx + 8, cy, 4, (255, 255, 255))
        sdk.circle(img, cx - 6, cy - 6, 4, (255, 255, 255))
        sdk.circle(img, cx + 6, cy + 6, 4, (255, 255, 255))
        sdk.circle(img, cx - 6, cy + 6, 4, (255, 255, 255))
        sdk.circle(img, cx + 6, cy - 6, 4, (255, 255, 255))
    elif t == 4:
        # Lila - virvel
        sdk.circle(img, cx - 6, cy - 2, 5, (255, 255, 255))
        sdk.circle(img, cx + 2, cy - 6, 5, (255, 255, 255))
        sdk.circle(img, cx + 6, cy + 2, 5, (255, 255, 255))
        sdk.circle(img, cx - 2, cy + 6, 5, (255, 255, 255))
    elif t == 5:
        # Orange - prickar
        sdk.circle(img, cx - 6, cy - 6, 4, (255, 255, 255))
        sdk.circle(img, cx + 6, cy - 6, 4, (255, 255, 255))
        sdk.circle(img, cx - 6, cy + 6, 4, (255, 255, 255))
        sdk.circle(img, cx + 6, cy + 6, 4, (255, 255, 255))
        sdk.circle(img, cx, cy, 4, (255, 255, 255))

    # Specielldesign
    if t == 10:
        # Radrensare - horisontella strimor
        for dy in range(-r + 8, r - 6, 8):
            sdk.circle(img, cx - 2, cy + dy, 3, (255, 255, 255))
    elif t == 11:
        # Kolumnrensare - vertikala strimor
        for dx in range(-r + 8, r - 6, 8):
            sdk.circle(img, cx + dx, cy - 2, 3, (255, 255, 255))
    elif t == 12:
        # Bomb - mörk med rött X
        sdk.circle(img, cx - r + 1, cy - r + 1, r * 2, (40, 40, 40))
        sdk.circle(img, cx - r + 3, cy - r + 3, r * 2 - 4, (60, 60, 60))
        # X-mark
        sdk.circle(img, cx - 6, cy - 6, 5, (255, 50, 50))
        sdk.circle(img, cx + 6, cy + 6, 5, (255, 50, 50))
        sdk.circle(img, cx + 6, cy - 6, 5, (255, 50, 50))
        sdk.circle(img, cx - 6, cy + 6, 5, (255, 50, 50))


def _draw_fading_candy(img, cx, cy, t, size, alpha):
    """Ritar en godis med genomskinlighet for fade-out-effekt."""
    r = size // 2 - 4
    col = _candy_color(t)

    # Kant
    sdk.circle(img, cx - r, cy - r, r * 2, (20, 20, 20))

    # Huvudkropp
    sdk.circle(img, cx - r + 2, cy - r + 2, r * 2 - 4, col)

    # Highlight
    sdk.circle(img, cx - r + 6, cy - r + 6, 6, (255, 255, 255))


def _draw_candy_flying(img, cx, cy, t, size):
    """Ritar en godis pa en godtycklig position (for fall-animation)."""
    r = size // 2 - 4
    col = _candy_color(t)
    dark = (col[0] // 2, col[1] // 2, col[2] // 2)
    light = tuple(min(255, c + 80) for c in col)

    # Yttre skugga
    sdk.circle(img, cx - r + 2, cy - r + 2, r * 2, (0, 0, 0, 60))

    # Botten (3D-effekt)
    sdk.circle(img, cx - r + 1, cy - r + 1, r * 2, dark)

    # Huvudkropp
    sdk.circle(img, cx - r, cy - r, r * 2, col)

    # Inre highlight (ovre kant)
    sdk.circle(img, cx - r + 3, cy - r + 3, r * 2 - 6, light)

    # Unika former per typ (samma som _draw_candy)
    if t == 0:
        sdk.circle(img, cx - 3, cy - 3, 6, (255, 255, 255))
        sdk.circle(img, cx + 3, cy - 3, 6, (255, 255, 255))
        sdk.circle(img, cx - 3, cy + 3, 6, (255, 255, 255))
        sdk.circle(img, cx + 3, cy + 3, 6, (255, 255, 255))
        sdk.circle(img, cx, cy, 6, (255, 255, 255))
    elif t == 1:
        sdk.circle(img, cx - 8, cy, 4, (255, 255, 255))
        sdk.circle(img, cx - 4, cy - 4, 4, (255, 255, 255))
        sdk.circle(img, cx, cy, 4, (255, 255, 255))
        sdk.circle(img, cx + 4, cy + 4, 4, (255, 255, 255))
        sdk.circle(img, cx + 8, cy, 4, (255, 255, 255))
    elif t == 2:
        sdk.circle(img, cx - 5, cy - 5, 5, (255, 255, 255))
        sdk.circle(img, cx + 5, cy - 5, 5, (255, 255, 255))
        sdk.circle(img, cx - 5, cy + 5, 5, (255, 255, 255))
        sdk.circle(img, cx + 5, cy + 5, 5, (255, 255, 255))
        sdk.circle(img, cx, cy, 4, (255, 255, 255))
    elif t == 3:
        sdk.circle(img, cx, cy - 8, 4, (255, 255, 255))
        sdk.circle(img, cx, cy + 8, 4, (255, 255, 255))
        sdk.circle(img, cx - 8, cy, 4, (255, 255, 255))
        sdk.circle(img, cx + 8, cy, 4, (255, 255, 255))
        sdk.circle(img, cx - 6, cy - 6, 4, (255, 255, 255))
        sdk.circle(img, cx + 6, cy + 6, 4, (255, 255, 255))
        sdk.circle(img, cx - 6, cy + 6, 4, (255, 255, 255))
        sdk.circle(img, cx + 6, cy - 6, 4, (255, 255, 255))
    elif t == 4:
        sdk.circle(img, cx - 6, cy - 2, 5, (255, 255, 255))
        sdk.circle(img, cx + 2, cy - 6, 5, (255, 255, 255))
        sdk.circle(img, cx + 6, cy + 2, 5, (255, 255, 255))
        sdk.circle(img, cx - 2, cy + 6, 5, (255, 255, 255))
    elif t == 5:
        sdk.circle(img, cx - 6, cy - 6, 4, (255, 255, 255))
        sdk.circle(img, cx + 6, cy - 6, 4, (255, 255, 255))
        sdk.circle(img, cx - 6, cy + 6, 4, (255, 255, 255))
        sdk.circle(img, cx + 6, cy + 6, 4, (255, 255, 255))
        sdk.circle(img, cx, cy, 4, (255, 255, 255))

    # Specielldesign
    if t == 10:
        for dy in range(-r + 8, r - 6, 8):
            sdk.circle(img, cx - 2, cy + dy, 3, (255, 255, 255))
    elif t == 11:
        for dx in range(-r + 8, r - 6, 8):
            sdk.circle(img, cx + dx, cy - 2, 3, (255, 255, 255))
    elif t == 12:
        sdk.circle(img, cx - r + 1, cy - r + 1, r * 2, (40, 40, 40))
        sdk.circle(img, cx - r + 3, cy - r + 3, r * 2 - 4, (60, 60, 60))
        sdk.circle(img, cx - 6, cy - 6, 5, (255, 50, 50))
        sdk.circle(img, cx + 6, cy + 6, 5, (255, 50, 50))
        sdk.circle(img, cx + 6, cy - 6, 5, (255, 50, 50))
        sdk.circle(img, cx - 6, cy + 6, 5, (255, 50, 50))


# --- cell-ruta ---
def _cell_rect(r, c):
    return (BX + c * CELL, BY + r * CELL, BX + (c + 1) * CELL, BY + (r + 1) * CELL)


def _cell_center(r, c):
    return (BX + c * CELL + CELL // 2, BY + r * CELL + CELL // 2)


# ================================================================
# Spelklass
# ================================================================
class Game(sdk.GameBase):
    def setup(self):
        self.best = 0
        self.board = [[-1] * COLS for _ in range(ROWS)]
        self.selected = None          # vald godis (r, c) eller None
        self._drag_r = self._drag_c = None  # drar mellan celler
        self.processing = False       # blockerar input under cascade
        self.running = False
        self.score = 0
        self.time_left = INIT_TIME    # centisekunder
        self.game_over = False
        self._timer_active = False

        # Animationer
        self._fade_out = {}           # {(r,c): start_time} - godisar som forsvinner
        self._falling = {}            # {(r,c): (start_r, start_time)} - godisar som faller
        self._new_candies = {}        # {(r,c): spawn_time} - nya godisar som dyker upp

    # ---- sparfil ----
    def state(self):
        return {
            'best': self.best,
            'score': self.score,
            'time_left': self.time_left,
            'board': self.board,
            'running': self.running,
            'game_over': self.game_over,
        }

    def restore(self, d):
        self.best = max(0, int(d.get('best', 0)))
        self.score = max(0, int(d.get('score', 0)))
        self.time_left = max(0, int(d.get('time_left', INIT_TIME)))
        b = d.get('board', [])
        if isinstance(b, list) and len(b) == ROWS and all(
                isinstance(row, list) and len(row) == COLS for row in b):
            self.board = [[int(v) for v in row] for row in b]
        else:
            self.board = [[-1] * COLS for _ in range(ROWS)]
        self.running = bool(d.get('running', False))
        self.game_over = bool(d.get('game_over', False))

    # ---- input ----
    def on_close(self):
        self.cancel('timer')
        self._timer_active = False
        self.selected = None
        self.processing = False

    def targets(self):
        if not self.running or self.game_over:
            return [('start', OVERLAY)]
        return []

    def on_tap(self, name):
        if name == 'start':
            if self.game_over or not self.running:
                self._new_game()
            self.save_soon()
            self.invalidate()
            return
        if len(name) >= 3 and name[0] == 'c':
            try:
                rest = name[1:]
                underscore_pos = rest.find('_')
                if underscore_pos > 0:
                    r = int(rest[:underscore_pos])
                    c = int(rest[underscore_pos + 1:])
                    self._tap_candy(r, c)
            except Exception:
                pass

    def on_down(self, x, y):
        try:
            if self.processing or not self.running or self.game_over:
                return
            r = (y - BY) // CELL
            c = (x - BX) // CELL
            if 0 <= r < ROWS and 0 <= c < COLS and _is_clearable(self.board[r][c]):
                # Alla beslut i on_down - ingen on_up-beroende
                if self.selected is None:
                    # Forsta trycket - val
                    self.selected = (r, c)
                    self.invalidate(_cell_rect(r, c))
                elif self.selected == (r, c):
                    # Samma godis - avval
                    self.selected = None
                    self.invalidate(_cell_rect(r, c))
                else:
                    # Annan godis - kolla om intilliggande
                    sr, sc = self.selected
                    if abs(r - sr) + abs(c - sc) == 1:
                        # Intilliggande - byt
                        self.swap_r1, self.swap_c1 = sr, sc
                        self.swap_r2, self.swap_c2 = r, c
                        self.selected = None
                        self._try_swap()
                    else:
                        # Inte intilliggande - val ny
                        self.invalidate(_cell_rect(sr, sc))
                        self.selected = (r, c)
                        self.invalidate(_cell_rect(r, c))
        except Exception as e:
            self.log('KRASH on_down: %s' % e)

    def on_move(self, x, y):
        pass

    def on_up(self, x, y):
        pass

    # ---- nya spelet ----
    def _new_game(self):
        self.running = True
        self.game_over = False
        self.score = 0
        self.time_left = INIT_TIME    # 6000 cs = 60s
        self.processing = False
        self.dragging = None
        self._fade_out.clear()
        self._falling.clear()
        self._new_candies.clear()
        self._fill_board()
        self._start_timer()

    def _fill_board(self):
        while True:
            self.board = [[self.rng.randrange(0, 6) for _ in range(COLS)] for _ in range(ROWS)]
            if not self._find_matches():
                break

    # ---- tid ----
    def _start_timer(self):
        self.cancel('timer')
        self._timer_active = True
        self._tick_timer()

    def _tick_timer(self):
        if not self._timer_active:
            return
        self.time_left -= 20          # 20 cs = 0.2s per tick
        if self.time_left <= 0:
            self.time_left = 0
            self._game_over()
            return
        # rita om tidslinjen
        self.invalidate(TIME_BAR)
        self.invalidate(SCORE)
        self.later('timer', 0.2, self._tick_timer)

    def _game_over(self):
        self.running = False
        self.game_over = True
        self._timer_active = False
        self.cancel('timer')
        if self.score > self.best:
            self.best = self.score
            self.save_now(force=True)
        else:
            self.save_soon()
        self.invalidate()

    # ---- swap & match ----
    def _try_swap(self):
        try:
            r1, c1, r2, c2 = self.swap_r1, self.swap_c1, self.swap_r2, self.swap_c2
            # byt
            self.board[r1][c1], self.board[r2][c2] = self.board[r2][c2], self.board[r1][c1]
            matches = self._find_matches()
            if matches:
                self.processing = True
                self._cascade()
            else:
                # byt tillbaka
                self.board[r1][c1], self.board[r2][c2] = self.board[r2][c2], self.board[r1][c1]
                self.invalidate(sdk.union(_cell_rect(r1, c1), _cell_rect(r2, c2)))
        except Exception as e:
            self.log('KRASH _try_swap: %s' % e)

    def _cascade(self):
        """Kor ett steg av cascade: hitta-matcha-rensa-gravitfyll."""
        try:
            # Animationerna ska vara klara efter 650ms - rensa eventuella gamla poster
            self._fade_out.clear()
            self._falling.clear()

            matches = self._find_matches()
            if not matches:
                self.processing = False
                self.save_soon()
                self.invalidate()
                return

            # gruppera matchade celler och skapa specialer
            cleared = set()
            for cells in matches:
                sz = len(cells)
                if sz >= 4:
                    # valj en godis att gor till special
                    sr, sc = cells[sz // 2]
                    if sz >= 5:
                        # 5+ = bomb (type 12)
                        self.board[sr][sc] = 12
                    else:
                        # 4 = radrensare (type 10)
                        self.board[sr][sc] = 10
                for (mr, mc) in cells:
                    cleared.add((mr, mc))

            # hantera specialer fran matchade celler (iterativt)
            changed = True
            while changed:
                changed = False
                for (mr, mc) in list(cleared):
                    t = self.board[mr][mc]
                    if _is_special(t):
                        st = _special_type(t)
                        if st == 0:  # radrensare
                            for cc in range(COLS):
                                if (mr, cc) not in cleared:
                                    cleared.add((mr, cc))
                                    changed = True
                        elif st == 1:  # kolumnrensare
                            for rr in range(ROWS):
                                if (rr, mc) not in cleared:
                                    cleared.add((rr, mc))
                                    changed = True
                        elif st == 2:  # bomb
                            for dr in range(-1, 2):
                                for dc in range(-1, 2):
                                    nr, nc = mr + dr, mc + dc
                                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                                        if (nr, nc) not in cleared:
                                            cleared.add((nr, nc))
                                            changed = True

            # berakna poang och tid
            points = len(cleared) * 10
            match_sizes = self._get_match_sizes(matches)
            time_gain = 0
            for sz in match_sizes:
                if sz >= 5:
                    time_gain += TIME_5
                elif sz == 4:
                    time_gain += TIME_4
                else:
                    time_gain += TIME_3
            # bonus for specialer
            has_special = any(_is_special(self.board[mr][mc]) for (mr, mc) in cleared)
            if has_special:
                time_gain += TIME_SPECIAL

            self.time_left = min(self.time_left + time_gain, MAX_TIME)  # max
            self.score += points

            # Starta fade-out animation
            now = self.loop.time()
            for (mr, mc) in cleared:
                self._fade_out[(mr, mc)] = now

            # Rensa celler
            for (mr, mc) in cleared:
                self.board[mr][mc] = -1

            # Rita rensade
            cleared_rects = [_cell_rect(r, c) for (r, c) in cleared]
            union_rect = cleared_rects[0]
            for rect in cleared_rects[1:]:
                union_rect = sdk.union(union_rect, rect)
            self.invalidate(union_rect)

            # Gravitation: lat godisar falla
            falling_cells = self._apply_gravity_with_animation(now)

            # Fyll tomrum med nya godisar fran ovan
            self._fill_gaps_with_animation(now, falling_cells)

            # Rita bradets
            self.invalidate(BOARD)
            self.invalidate(SCORE)
            self.invalidate(TIME_BAR)

            # Starta animationstimer for kontinuerliga redraws under fall-animation
            self._anim_timer_start = now
            self._invalidate_anim()

            # Nasta cascade-steg - vanta pa animation
            self.later('cascade', (FALL_DURATION + 50) / 1000.0, self._cascade)
        except Exception as e:
            self.log('KRASH cascade: %s' % e)
            self.processing = False
            self.invalidate()

    def _invalidate_anim(self):
        """Invalidera brade kontinuerligt under animation."""
        if not self.processing:
            return
        now = self.loop.time()
        # Kolla om det finns nagon animation pagaende
        has_anim = bool(self._fade_out) or bool(self._falling)
        if has_anim:
            self.invalidate(BOARD)
            # Schemalaga nasta invalidation om 50ms
            self.later('anim_invalidate', 0.05, self._invalidate_anim)
        else:
            # Ingen animation pagaende, stoppa timern
            self.cancel('anim_invalidate')

    def _get_match_sizes(self, matches):
        """Ger listan med match-storlekar."""
        return [len(m) for m in matches]

    def _apply_gravity(self):
        """Lat godisar falla ner."""
        for c in range(COLS):
            write_pos = ROWS - 1
            for r in range(ROWS - 1, -1, -1):
                if self.board[r][c] >= 0:
                    self.board[write_pos][c] = self.board[r][c]
                    write_pos -= 1
            for r in range(write_pos, -1, -1):
                self.board[r][c] = -1

    def _apply_gravity_with_animation(self, now):
        """Lat godisar falla ner med animation. Returnerar celler som faller."""
        falling = []
        for c in range(COLS):
            write_pos = ROWS - 1
            for r in range(ROWS - 1, -1, -1):
                if self.board[r][c] >= 0:
                    if write_pos != r:
                        # Denna godis faller
                        falling.append((write_pos, c, r, now))
                    self.board[write_pos][c] = self.board[r][c]
                    write_pos -= 1
            for r in range(write_pos, -1, -1):
                self.board[r][c] = -1
        # Lagra fall-info
        for (new_r, c, old_r, t) in falling:
            self._falling[(new_r, c)] = (old_r, t)
        return falling

    def _fill_gaps(self):
        """Fyll tomma rutor med nya godisar fran ovan."""
        for c in range(COLS):
            for r in range(ROWS):
                if self.board[r][c] < 0:
                    self.board[r][c] = self.rng.randrange(0, 6)

    def _fill_gaps_with_animation(self, now, falling_cells):
        """Fyll tomma rutor med nya godisar som faller fran ovan."""
        for c in range(COLS):
            for r in range(ROWS):
                if self.board[r][c] < 0:
                    self.board[r][c] = self.rng.randrange(0, 6)
                    # Ny godis faller fran ovan (3 rutor over bradet)
                    self._falling[(r, c)] = (r - 3, now)

    # ---- match-detektion ----
    def _find_matches(self, board=None):
        """Hitta alla horisontella och vertikala matches (3+)."""
        if board is None:
            board = self.board
        matches = []
        # horisontella
        for r in range(ROWS):
            count = 1
            for c in range(1, COLS):
                if _is_clearable(board[r][c]) and board[r][c] == board[r][c - 1]:
                    count += 1
                else:
                    if count >= 3:
                        matches.append([(r, c - count + i) for i in range(count)])
                    count = 1
            if count >= 3:
                matches.append([(r, COLS - count + i) for i in range(count)])

        # vertikala
        for c in range(COLS):
            count = 1
            for r in range(1, ROWS):
                if _is_clearable(board[r][c]) and board[r][c] == board[r - 1][c]:
                    count += 1
                else:
                    if count >= 3:
                        matches.append([(r - count + i, c) for i in range(count)])
                    count = 1
            if count >= 3:
                matches.append([(ROWS - count + i, c) for i in range(count)])

        return matches

    # ---- ritning ----
    def paint(self, img, rect):
        # HUD: poang
        if sdk.meets(rect, HUD):
            sdk.fill(img, HUD, sdk.CARD)
            sdk.text(img, PAD + 4, 114, 'Poang', 400, 22, sdk.MUTED)
            sdk.text(img, PAD + 4, 136, str(self.score), 300, 36, sdk.TEXT)

        # Tidslinje
        if sdk.meets(rect, TIME_BAR):
            sdk.fill(img, TIME_BAR, sdk.CARD)
            sdk.fill(img, TIME_BAR_BG, (40, 40, 40))
            # fyllnad
            pct = self.time_left / INIT_TIME
            fill_w = int((TIME_BAR_BG[2] - TIME_BAR_BG[0]) * pct)
            if self.time_left < 1000:
                col = sdk.RED
            elif self.time_left < 2000:
                col = sdk.WARN
            else:
                col = sdk.GREEN
            sdk.fill(img, (TIME_BAR_BG[0], TIME_BAR_BG[1], TIME_BAR_BG[0] + fill_w, TIME_BAR_BG[3]), col)
            # text
            sdk.text(img, TIME_BAR_BG[0], TIME_BAR_BG[1] + 4, 'Tid', 400, 14, sdk.TEXT)
            sdk.text(img, TIME_BAR_BG[2], TIME_BAR_BG[1] + 4, '%.1f s' % (self.time_left / 100), 400, 14, sdk.TEXT, anchor='rs')

        # Brade
        if sdk.meets(rect, BOARD):
            sdk.fill(img, sdk.clip(rect, BOARD), sdk.CARD)
            now = self.loop.time()

            for r in range(ROWS):
                for c in range(COLS):
                    t = self.board[r][c]

                    cx, cy = _cell_center(r, c)

                    # Kontrollera animationer (FADE MASTE KOLLAS FORST - oavsett om t ar -1)
                    is_fading = (r, c) in self._fade_out
                    is_falling = (r, c) in self._falling

                    # Om ej klarbar och ingen animation, hoppa over
                    if not _is_clearable(t) and not is_fading and not is_falling:
                        continue

                    # Rita markerad godis med ljus bakgrund och gul kant
                    if self.selected == (r, c) and not is_fading:
                        sdk.fill(img, (BX + c * CELL, BY + r * CELL, BX + (c + 1) * CELL, BY + (r + 1) * CELL), (60, 60, 80))
                        r2 = CELL // 2 - 4
                        sdk.circle(img, cx - r2 - 2, cy - r2 - 2, (r2 + 2) * 2, sdk.YELLOW)

                    # Bestam vilken funktion som ska anvandas
                    if is_fading:
                        fade_time = now - self._fade_out[(r, c)]
                        if fade_time < FADE_DURATION:
                            alpha = int(100 * (1 - fade_time / FADE_DURATION))
                            _draw_fading_candy(img, cx, cy, t, CELL - 8, alpha)
                            continue  # Animering pagaende, hoppa over resten
                        else:
                            del self._fade_out[(r, c)]
                            # Fade klar, kolla fall-animation nedan

                    if is_falling:
                        start_r, start_time = self._falling[(r, c)]
                        fall_time = now - start_time
                        if fall_time < FALL_DURATION:
                            # Berakna nuvarande Y-position (ease-out)
                            progress = fall_time / FALL_DURATION
                            ease = 1 - (1 - progress) ** 3  # ease-out cubic
                            # Interpolera fran start till mal
                            draw_cy = int(BY + start_r * CELL + CELL // 2 + (r - start_r) * CELL * ease)
                            # Rita godis pa flytande position
                            _draw_candy_flying(img, cx, draw_cy, t, CELL - 8)
                            continue  # Animering pagaende
                        else:
                            # Klar att landa - radera och fortsatt till normal ritning
                            del self._falling[(r, c)]
                            # Fall through to normal drawing below

                    # Normal ritning (efter animation eller ingen animation)
                    _draw_candy(img, cx, cy, t, CELL - 8)

        # Startskarm / game over overlay
        if not self.running or self.game_over:
            if sdk.meets(rect, OVERLAY):
                sdk.fill(img, sdk.clip(rect, OVERLAY), sdk.BG)
                sdk.rbox(img, OVERLAY[0], OVERLAY[1], OVERLAY[2], OVERLAY[3], 24, sdk.CARD)
                sdk.bbox(img, OVERLAY[0], OVERLAY[1], OVERLAY[2], OVERLAY[3], 24, sdk.CARD, sdk.CARD_BORDER, 2)
                if self.game_over:
                    sdk.centered(img, 512, 210, 'Slut!', 500, 40, sdk.RED)
                    sdk.centered(img, 512, 260, 'Poang: %d' % self.score, 400, 28, sdk.TEXT)
                    if self.score >= self.best:
                        sdk.centered(img, 512, 300, 'Nytt rekord!', 500, 24, sdk.GREEN)
                else:
                    sdk.centered(img, 512, 210, 'Candy Fall', 500, 36, sdk.BLUE_L)
                    sdk.centered(img, 512, 255, 'Matcha 3+ godisar', 400, 22, sdk.MUTED)
                    sdk.centered(img, 512, 285, 'for att fa tid!', 400, 22, sdk.MUTED)
                # Start-knapp
                sdk.button(img, START, 'Start', 'primary', self.pressed == 'start', size=28)

        # Rekord
        if sdk.meets(rect, (PAD, 430, 400, 470)):
            if self.best > 0:
                sdk.text(img, PAD, 460, 'Rekord: %d' % self.best, 400, 20, sdk.MUTED)


def draw_icon(im):
    sdk.circle(im, 16, 16, 50, CANDY[0])
    sdk.circle(im, 72, 16, 50, CANDY[1])
    sdk.circle(im, 16, 72, 50, CANDY[2])
    sdk.circle(im, 72, 72, 50, CANDY[3])
    sdk.circle(im, 44, 44, 50, CANDY[4])


def status(data):
    if not data:
        return None
    if data.get('game_over') or not data.get('running'):
        best = data.get('best', 0)
        if best:
            return 'Rekord %d' % best, False
    if data.get('running') and not data.get('game_over'):
        score = data.get('score', 0)
        return 'Pågaende · %d' % score, True
    return None