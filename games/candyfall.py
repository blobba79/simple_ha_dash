"""Candy Fall: matcha godisar innan tiden rinner ut! Dra mellan intilliggande rutor för att byta platser.
3+ i rad = borta + tid. 4 = radrensare. 5+ = bomb som rensar 3x3. Specialer = MASSIV tid!"""
from dashpanel import gamesdk as sdk

META = {
    'api': 1,
    'id': 'candyfall',
    'name': 'Candy Fall',
    'desc': 'Matcha godisar innan tiden rinner ut! 3+ = tid, 4+ = specialer, 5+ = MASSIV tid!',
    'version': 1,
}

# --- bräde ---
COLS, ROWS = 8, 7
CELL = 64
PAD = 16
BX, BY = PAD, 148                       # brädets övre vänstra
BOARD = (BX - PAD, BY - PAD, BX + COLS * CELL + PAD, BY + ROWS * CELL + PAD)
BOARD_W = COLS * CELL
BOARD_H = ROWS * CELL

# --- HUD ---
HUD = (PAD, 96, 1024 - PAD, 120)
TIME_BAR = (PAD, 124, 1024 - PAD, 144)
TIME_BAR_BG = (PAD + 4, 128, 1024 - PAD - 4, 140)
SCORE = (PAD, 128, 300, 152)
START = (360, 260, 664, 330)

# --- färger (ljusa godisar på mörk bakgrund) ---
CANDY = [
    (239, 68, 68),    # 0 röd
    (59, 130, 246),   # 1 blå
    (34, 197, 94),    # 2 grön
    (250, 204, 21),   # 3 gul
    (168, 85, 247),   # 4 lila
    (251, 146, 60),   # 5 orange
]
SPECIAL_COLORS = [
    None,
    (255, 255, 255),  # radrensare (horisontell)
    (100, 255, 100),  # kolumnrensare (vertikal)
    (255, 100, 255),  # bomb (3x3)
]

# --- tid (allt i centisekunder = heltal) ---
INIT_TIME = 6000                           # starttid (60s * 100)
DRAIN = 100                                # centisekunder per sekund
TIME_3 = 200                               # tid för 3-match
TIME_4 = 400                               # tid för 4-match
TIME_5 = 800                               # tid för 5-match
TIME_SPECIAL = 1200                        # tid för special-match
MAX_TIME = 12000                           # max 120s


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


# --- ritning av godisar ---
def _draw_candy(img, cx, cy, t, size):
    """Ritar en godis i center (cx, cy) med diameter size."""
    r = size // 2 - 2
    col = _candy_color(t)
    sdk.circle(img, cx - r, cy - r, size - 4, col)
    if _is_special(t):
        st = _special_type(t)
        sc = SPECIAL_COLORS[st]
        sdk.circle(img, cx - 6, cy - 6, 12, sc)


def _draw_striped_h(img, cx, cy, t, size):
    col = _candy_color(t)
    sdk.circle(img, cx - (size // 2 - 2), cy - (size // 2 - 2), size - 4, col)
    for dy in range(-size // 2 + 6, size // 2 - 4, 8):
        sdk.circle(img, cx - 4, cy + dy - 2, 4, (255, 255, 255))


def _draw_striped_v(img, cx, cy, t, size):
    col = _candy_color(t)
    sdk.circle(img, cx - (size // 2 - 2), cy - (size // 2 - 2), size - 4, col)
    for dx in range(-size // 2 + 6, size // 2 - 4, 8):
        sdk.circle(img, cx + dx - 2, cy - 4, 4, (255, 255, 255))


def _draw_bomb(img, cx, cy, t, size):
    r = size // 2 - 2
    col = _candy_color(t)
    sdk.circle(img, cx - r, cy - r, size - 4, col)
    sdk.circle(img, cx - 10, cy - 10, 20, (255, 255, 255))
    sdk.circle(img, cx - 6, cy - 6, 12, (200, 0, 200))


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
        self.dragging = None          # (r, c) om en godis dras
        self.drag_pos = None          # (x, y)
        self.swap_r1 = self.swap_c1 = self.swap_r2 = self.swap_c2 = None
        self.processing = False       # blockerar input under cascade
        self.running = False
        self.score = 0
        self.time_left = INIT_TIME    # centisekunder
        self.game_over = False
        self._timer_active = False

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
        # Starta inte timern automatiskt vid restore - den startas i on_tap('start')

    # ---- input ----
    def on_close(self):
        self.cancel('timer')
        self._timer_active = False
        self.dragging = None
        self.processing = False

    def targets(self):
        if not self.running or self.game_over:
            return [('start', START)]
        return []

    def on_tap(self, name):
        if name == 'start':
            if self.game_over or not self.running:
                self._new_game()
            self.save_soon()
            self.invalidate()

    def on_down(self, x, y):
        if not self.running or self.game_over or self.processing:
            return
        r = (y - BY) // CELL
        c = (x - BX) // CELL
        if 0 <= r < ROWS and 0 <= c < COLS and _is_clearable(self.board[r][c]):
            self.dragging = (r, c)
            self.drag_pos = (x, y)

    def on_move(self, x, y):
        if not self.dragging:
            return
        self.drag_pos = (x, y)
        r = (y - BY) // CELL
        c = (x - BX) // CELL
        dr, dc = abs(r - self.dragging[0]), abs(c - self.dragging[1])
        if (dr + dc == 1) and 0 <= r < ROWS and 0 <= c < COLS:
            if _is_clearable(self.board[r][c]):
                self.swap_r1, self.swap_c1 = self.dragging
                self.swap_r2, self.swap_c2 = r, c
                self.dragging = None
                self._try_swap()
                return
        self.dragging = (r, c)
        self.drag_pos = (x, y)

    def on_up(self, x, y):
        if self.dragging:
            self.dragging = None
            self.drag_pos = None
        self.swap_r1 = self.swap_c1 = self.swap_r2 = self.swap_c2 = None

    # ---- nya spelet ----
    def _new_game(self):
        self.running = True
        self.game_over = False
        self.score = 0
        self.time_left = INIT_TIME    # 6000 cs = 60s
        self.processing = False
        self.dragging = None
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

    def _cascade(self):
        """Kör ett steg av cascade: hitta-matcha-rensa-gravitfyll."""
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
                # välj en godis att göra till special
                sr, sc = cells[sz // 2]
                if sz >= 5:
                    # 5+ = bomb (type 12)
                    self.board[sr][sc] = 12
                else:
                    # 4 = radrensare (type 10)
                    self.board[sr][sc] = 10
            for (mr, mc) in cells:
                cleared.add((mr, mc))

        # hantera specialer från matchade celler
        for (mr, mc) in list(cleared):
            t = self.board[mr][mc]
            if _is_special(t):
                st = _special_type(t)
                if st == 0:  # radrensare
                    for cc in range(COLS):
                        cleared.add((mr, cc))
                elif st == 1:  # kolumnrensare
                    for rr in range(ROWS):
                        cleared.add((rr, mc))
                elif st == 2:  # bomb
                    for dr in range(-1, 2):
                        for dc in range(-1, 2):
                            nr, nc = mr + dr, mc + dc
                            if 0 <= nr < ROWS and 0 <= nc < COLS:
                                cleared.add((nr, nc))

        # beräkna poäng och tid
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
        # bonus för specialer
        has_special = any(_is_special(self.board[mr][mc]) for (mr, mc) in cleared)
        if has_special:
            time_gain += TIME_SPECIAL

        self.time_left = min(self.time_left + time_gain, MAX_TIME)  # max 120s
        self.score += points

        # rensa celler
        for (mr, mc) in cleared:
            self.board[mr][mc] = -1

        # rita rensade
        cleared_rects = [_cell_rect(r, c) for (r, c) in cleared]
        self.invalidate(sdk.union(*cleared_rects))

        # gravitation: låt godisar falla
        self._apply_gravity()

        # fyll tomrum
        self._fill_gaps()

        # rita brädet
        self.invalidate(BOARD)
        self.invalidate(SCORE)
        self.invalidate(TIME_BAR)

        # nästa cascade-steg
        self.later('cascade', 0.15, self._cascade)

    def _get_match_sizes(self, matches):
        """Ger listan med match-storlekar."""
        return [len(m) for m in matches]

    def _apply_gravity(self):
        """Låt godisar falla ner."""
        for c in range(COLS):
            write_pos = ROWS - 1
            for r in range(ROWS - 1, -1, -1):
                if self.board[r][c] >= 0:
                    self.board[write_pos][c] = self.board[r][c]
                    write_pos -= 1
            for r in range(write_pos, -1, -1):
                self.board[r][c] = -1

    def _fill_gaps(self):
        """Fyll tomma rutor med nya godisar."""
        for c in range(COLS):
            for r in range(ROWS):
                if self.board[r][c] < 0:
                    self.board[r][c] = self.rng.randrange(0, 6)

    # ---- match-detektion ----
    def _find_matches(self):
        """Hitta alla horisontella och vertikala matches (3+)."""
        matches = []
        # horisontella
        for r in range(ROWS):
            count = 1
            for c in range(1, COLS):
                if _is_clearable(self.board[r][c]) and self.board[r][c] == self.board[r][c - 1]:
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
                if _is_clearable(self.board[r][c]) and self.board[r][c] == self.board[r - 1][c]:
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
        # HUD: poäng
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

        # Bräde
        if sdk.meets(rect, BOARD):
            sdk.fill(img, sdk.clip(rect, BOARD), sdk.CARD)
            for r in range(ROWS):
                for c in range(COLS):
                    t = self.board[r][c]
                    if not _is_clearable(t):
                        continue
                    cx, cy = _cell_center(r, c)
                    if t == 10:  # radrensare
                        _draw_striped_h(img, cx, cy, t, CELL - 8)
                    elif t == 11:  # kolumnrensare
                        _draw_striped_v(img, cx, cy, t, CELL - 8)
                    elif t == 12:  # bomb
                        _draw_bomb(img, cx, cy, t, CELL - 8)
                    else:
                        _draw_candy(img, cx, cy, t, CELL - 8)

            # drag-förhandsvisning
            if self.dragging and self.drag_pos and not self.processing:
                dr, dc = self.dragging
                cx, cy = _cell_center(dr, dc)
                dx = self.drag_pos[0] - cx
                dy = self.drag_pos[1] - cy
                alpha = 0.6
                # rita den flyttade godisen med halvt transparens (genom att blanda färg)
                t = self.board[dr][dc]
                if t >= 0:
                    col = _candy_color(t)
                    bright = sdk.blend(col, (255, 255, 255), 0.3)
                    sdk.circle(img, cx + sdk.snap(dx) - (CELL // 2 - 2),
                               cy + sdk.snap(dy) - (CELL // 2 - 2),
                               CELL - 4, bright)

        # Startskärm / game over
        if sdk.meets(rect, START):
            if not self.running or self.game_over:
                sdk.fill(img, sdk.clip(rect, BOARD), sdk.BG)
                sdk.rbox(img, 262, 180, 762, 420, 24, sdk.CARD)
                sdk.bbox(img, 262, 180, 762, 420, 24, sdk.CARD, sdk.CARD_BORDER, 2)
                if self.game_over:
                    sdk.centered(img, 512, 230, 'Slut!', 500, 40, sdk.RED)
                    sdk.centered(img, 512, 280, 'Poang: %d' % self.score, 400, 28, sdk.TEXT)
                    if self.score >= self.best:
                        sdk.centered(img, 512, 320, 'Nytt rekord!', 500, 24, sdk.GREEN)
                else:
                    sdk.centered(img, 512, 230, 'Candy Fall', 500, 36, sdk.BLUE_L)
                    sdk.centered(img, 512, 275, 'Matcha 3+ godisar', 400, 22, sdk.MUTED)
                    sdk.centered(img, 512, 305, 'för att fa tid!', 400, 22, sdk.MUTED)
                sdk.centered(img, 512, 370, 'Start', 500, 30, sdk.TEXT)

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
