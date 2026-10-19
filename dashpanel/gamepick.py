"""Spelväljaren: sidan som spelikonen öppnar. Den söker igenom spelmappen varje gång den öppnas och visar ett kort per spel
(ikon, namn, en rad om spelet och hur det står till: pågående spel eller rekord). Ett tryck på ett kort öppnar spelet.
Sidan visar fyra spel i taget; finns fler bläddrar man med pilarna. En spelfil som inte går att köra visas nedtonad med
orsaken i stället för att döljas.

Under korten sitter knappen Uppdatera spel: den hämtar mappen games/ från GitHub (gamesync.py) och söker sedan igenom
spelmappen igen. Den vanliga knappen Uppdatera (inställningarna) rör inte spelen.

Väljaren är själv ett spel i SDK:ts mening (GameBase): rubrikraden, klockan, tryck på knappar och ritning av bara det som
ändrats kommer därifrån. Panelen (ui.py) ger den krokarna 'pick' (id på spelet som valdes) och 'exit' (Tillbaka, till
flikarna). Spelen som öppnas härifrån har sin egen Tillbaka som leder hit igen."""
from PIL import Image

from . import gamesdk as sdk
from . import gamesync

PER_PAGE = 4
POLL_SECONDS = 1.0                    # så ofta läses hur hämtningen går (en liten fil, inget anrop)
COLS = 2
TILE_W, TILE_H, GAP = 480, 192, 16
GRID_X, GRID_Y = 24, 96
GRID_RECT = (GRID_X, GRID_Y, GRID_X + COLS * TILE_W + GAP, GRID_Y + 2 * TILE_H + GAP)         # (24, 96, 1000, 496)
SYNC_RECT = (24, 516, 384, 584)
PREV_RECT = (832, 516, 912, 584)
NEXT_RECT = (920, 516, 1000, 584)
PAGE_RIGHT = 820                     # sidnumret ("1/2") slutar här
BAR_RECT = (16, 508, 1008, 592)      # hela raden under korten
CONTENT = (16, 90, 1008, 592)
MSG_X = 404
TILE_BG = sdk.ICON_BG
TILE_BORDER = (0x33, 0x33, 0x33)
TEXT_X = 176                         # textens vänsterkant inuti ett kort (ikonen tar 24 + 128 + 24)

MSG_COLORS = {'ok': sdk.GREEN, 'same': sdk.MUTED, 'warn': sdk.WARN, 'fail': sdk.RED}
HINT = 'Hämtar nya och ändrade spel från GitHub.'


def tile_rect(i):
    """Kortets ruta för plats i (0-3) på sidan."""
    col, row = i % COLS, i // COLS
    x0 = GRID_X + col * (TILE_W + GAP)
    y0 = GRID_Y + row * (TILE_H + GAP)
    return (x0, y0, x0 + TILE_W, y0 + TILE_H)


class GamePicker(sdk.GameBase):
    """Spelväljarens skärm. library: gamelib.Library; syncer: gamesync.GameSync eller None (då finns ingen knapp att hämta
    med, till exempel i en provmiljö)."""

    def __init__(self, ctx, library, syncer=None):
        self.lib = library
        self.sync = syncer
        super(GamePicker, self).__init__(ctx)

    # ------------------------------------------------------------ tillstånd
    def setup(self):
        self.games = []
        self.status = {}                # spelets id -> (text, aktiv) eller None
        self.page = 0
        self.busy = False               # en hämtning pågår
        self.msg = None                 # (text, art) efter en hämtning
        self.can_sync = False
        self._t0 = 0.0
        self._task = None

    def pages(self):
        return max(1, (len(self.games) + PER_PAGE - 1) // PER_PAGE)

    def page_games(self):
        return self.games[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]

    def on_open(self):
        if not self.busy:
            self.msg = None
        try:
            self.can_sync = self.sync is not None and bool(self.sync.available())
        except Exception as e:
            self.can_sync = False
            self.log('kunde inte kontrollera hämtningen av spel: %r' % (e,))
        self.rescan()
        if self.busy:
            self.later('poll', POLL_SECONDS, self._poll)

    def rescan(self):
        """Söker igenom spelmappen och läser statusraderna."""
        try:
            self.games = self.lib.scan()
        except Exception as e:           # mappen ska aldrig kunna stoppa väljaren
            self.games = []
            self.log('kunde inte söka igenom spelmappen: %r' % (e,))
        self.status = {}
        for info in self.games:
            if not info.error:
                self.status[info.id] = self.lib.status(info)
        self.page = min(self.page, self.pages() - 1)

    # ------------------------------------------------------------ hämtning
    def _start_sync(self):
        self.busy = True
        self.msg = None
        self._t0 = self.now()
        self.invalidate(BAR_RECT)
        self._task = self.loop.create_task(self._begin())

    async def _begin(self):
        try:
            mode, text = await self.sync.start()
        except Exception as e:
            mode, text = 'error', 'Kunde inte starta hämtningen (%s).' % (e,)
        if mode in ('started', 'busy'):
            self.later('poll', POLL_SECONDS, self._poll)
        else:
            self._done(text, 'fail')

    def _poll(self):
        rc = self.sync.finished()
        if rc is not None:
            text, kind = self.sync.outcome(rc)
            self.sync.clear()
            self._done(text, kind)
        elif self.now() - self._t0 > gamesync.RUN_TIMEOUT:
            self._done(*self.sync.timeout_outcome())
        else:
            self.later('poll', POLL_SECONDS, self._poll)

    def _done(self, text, kind):
        self.busy = False
        self.msg = (text, kind)
        self.rescan()
        if self._opened:
            self.invalidate(CONTENT)

    # ------------------------------------------------------------ tryck
    def targets(self):
        out = []
        for i, info in enumerate(self.page_games()):
            if not info.error:
                out.append(('g:' + info.id, tile_rect(i)))
        if self.can_sync and not self.busy:
            out.append(('sync', SYNC_RECT))
        if self.page > 0:
            out.append(('prev', PREV_RECT))
        if self.page < self.pages() - 1:
            out.append(('next', NEXT_RECT))
        return out

    def on_tap(self, name):
        if name.startswith('g:'):
            fn = self.hooks.get('pick')
            if fn is not None:
                fn(name[2:])
        elif name == 'sync':
            self._start_sync()
        elif name in ('prev', 'next'):
            self.page = max(0, min(self.pages() - 1, self.page + (1 if name == 'next' else -1)))
            self.invalidate(CONTENT)

    def on_close(self):
        self._task = None

    # ------------------------------------------------------------ ritning
    def paint(self, img, rect):
        pg = self.page_games()
        if not self.games:
            if sdk.meets(rect, GRID_RECT):
                self._paint_empty(img)
        for i, info in enumerate(pg):
            r = tile_rect(i)
            if sdk.meets(rect, r):
                self._paint_tile(img, r, info)
        if sdk.meets(rect, SYNC_RECT):
            self._paint_sync(img)
        if sdk.meets(rect, self._msg_rect()):
            self._paint_msg(img)
        if self.pages() > 1:
            self._paint_pager(img, rect)

    def _paint_empty(self, img):
        x0, y0, x1, y1 = GRID_RECT
        sdk.bbox(img, x0, y0, x1, y1, 24, sdk.CARD, sdk.CARD_BORDER, 1)
        cx = (x0 + x1) // 2
        sdk.centered(img, cx, 268, 'Inga spel än', 500, 34, sdk.TEXT)
        if self.lib.games_dir is None:
            why = 'Spelmappen är inte inställd på den här enheten.'
        elif self.can_sync:
            why = 'Tryck på Uppdatera spel nedan för att hämta spelen från GitHub.'
        else:
            why = 'Det finns inga spelfiler i spelmappen.'
        for k, line in enumerate(sdk.wrap(why, 400, 20, 640)[:3]):
            sdk.centered(img, cx, 314 + k * 30, line, 400, 20, sdk.MUTED)

    def _paint_tile(self, img, r, info):
        x0, y0, x1, y1 = r
        ok = not info.error
        pressed = ok and self.pressed == 'g:' + info.id
        fill = sdk.blend(TILE_BG, (255, 255, 255), 0.08) if pressed else TILE_BG
        sdk.fill(img, r)                                # de rundade hörnen blandas mot det som ligger under
        sdk.bbox(img, x0, y0, x1, y1, 20, fill, TILE_BORDER, 1)
        pic = self.lib.icon(info, fill)
        if not ok:
            pic = Image.blend(pic, Image.new('RGB', pic.size, fill), 0.6)
        img.paste(pic, (x0 + 24, y0 + (TILE_H - sdk.ICON) // 2))
        tx, tw = x0 + TEXT_X, TILE_W - TEXT_X - 20
        sdk.text(img, tx, y0 + 60, sdk.fit(info.name, 500, 30, tw), 500, 30, sdk.TEXT if ok else sdk.STALE_TEXT)
        if ok:
            for k, line in enumerate(sdk.wrap(info.desc, 400, 16, tw)[:3]):
                sdk.text(img, tx, y0 + 92 + k * 22, line, 400, 16, sdk.MUTED)
            st = self.status.get(info.id)
            if st:
                label, active = st
                sdk.text(img, tx, y0 + 176, sdk.fit(label, 500 if active else 400, 17, tw), 500 if active else 400, 17,
                         sdk.BLUE_L if active else sdk.MUTED)
        else:
            sdk.text(img, tx, y0 + 92, 'Kan inte öppnas', 500, 16, sdk.WARN)
            for k, line in enumerate(sdk.wrap(info.error, 400, 15, tw)[:3]):
                sdk.text(img, tx, y0 + 114 + k * 20, line, 400, 15, sdk.MUTED)

    def _paint_sync(self, img):
        enabled = self.can_sync and not self.busy
        if self.busy:
            label, kind = 'Hämtar …', 'normal'
        else:
            label, kind = 'Uppdatera spel', ('primary' if not self.games and self.can_sync else 'normal')
        sdk.fill(img, SYNC_RECT)
        sdk.button(img, SYNC_RECT, label, kind, self.pressed == 'sync', enabled, 24, 'CloudDownload')

    def _msg_rect(self):
        return (MSG_X, BAR_RECT[1], (PAGE_RIGHT - 70) if self.pages() > 1 else BAR_RECT[2], BAR_RECT[3])

    def _paint_msg(self, img):
        r = self._msg_rect()
        sdk.fill(img, r)
        if self.busy:
            text, color = 'Hämtar spel från GitHub …', sdk.MUTED
        elif self.msg:
            text, color = self.msg[0], MSG_COLORS.get(self.msg[1], sdk.MUTED)
        elif not self.can_sync:
            text, color = ('Det går inte att hämta spel från den här enheten.' if self.sync is not None
                           else ''), sdk.MUTED
        else:
            text, color = HINT, sdk.MUTED
        lines = sdk.wrap(text, 400, 17, r[2] - r[0] - 8)[:3]
        top = (SYNC_RECT[1] + SYNC_RECT[3]) // 2 - (len(lines) * 22) // 2 + 17
        for k, line in enumerate(lines):
            sdk.text(img, r[0], top + k * 22, line, 400, 17, color)

    def _paint_pager(self, img, rect):
        label_r = (PAGE_RIGHT - 66, BAR_RECT[1], PAGE_RIGHT + 4, BAR_RECT[3])
        if sdk.meets(rect, label_r):
            sdk.fill(img, label_r)
            sdk.text(img, PAGE_RIGHT, 558, '%d/%d' % (self.page + 1, self.pages()), 500, 20, sdk.MUTED, anchor='rs')
        for name, r, ico, size, on in (('prev', PREV_RECT, 'ChevronLeft', 32, self.page > 0),
                                       ('next', NEXT_RECT, 'ChevronRight', 28, self.page < self.pages() - 1)):
            if not sdk.meets(rect, r):
                continue
            sdk.fill(img, r)
            fill = sdk.BTN_BG
            if on and self.pressed == name:
                fill = sdk.blend(fill, (255, 255, 255), 0.09)
            if not on:
                fill = sdk.blend(fill, sdk.BG, 0.5)
            sdk.bbox(img, r[0], r[1], r[2], r[3], 20, fill, sdk.CARD_BORDER if on else sdk.blend(sdk.CARD_BORDER, sdk.BG, 0.5), 1)
            sdk.icon(img, ico, size, (r[0] + r[2] - size) // 2, (r[1] + r[3] - size) // 2, sdk.TEXT if on else sdk.STALE_TEXT)
