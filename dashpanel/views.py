"""Ritar panelens vyer (Flikar: belysning, dimvy, temperaturer) och delar av dem.
Mått och färger kommer från designen (design/src/*.dc.html, mätta i Chromium).
Varje draw_*-funktion rensar sin egen yta först, så den kan anropas ensam (rita bara det som ändrats)."""
from PIL import Image, ImageDraw, ImageFilter

from . import theme as T
from .gfx import (W, H, bbox, blend, circle, fit, icon, rbox, rbox_mask, snap, text, text_width, wrap)
from .display import BRIGHT_MAX, BRIGHT_MIN, BRIGHT_STEP, OFF_MAX, OFF_MIN, OFF_STEP
from .qr import qr_mask


def clear(img, x0, y0, x1, y1, color=T.BG):
    ImageDraw.Draw(img).rectangle((x0, y0, x1 - 1, y1 - 1), fill=color)


def ty(v):
    """Textens baslinje i hela pixlar."""
    return snap(v)


class LampVM(object):
    """Visningsmodell för en cell på knappfliken. state: on, off, na (ej tillgänglig), stale (ingen kontakt).
    kind: lamp, all (knappen "Alla lampor"), toggle (annat på/av) eller action (scen, skript, knapp: tryck = kör).
    icons: (ikon när på, ikon när av). action: tryckknapp i stället för växel; done: senaste trycket gick igenom."""
    __slots__ = ('kind', 'name', 'state', 'status', 'pal', 'dimmable', 'pressed', 'icons', 'busy', 'done')

    def __init__(self, kind='lamp', name='', state='off', status='', pal=None, dimmable=False, pressed=False,
                 icons=None, busy=False, done=False):
        self.kind, self.name, self.state, self.status = kind, name, state, status
        self.pal, self.dimmable, self.pressed = pal, dimmable, pressed
        self.icons, self.busy, self.done = icons, busy, done

    def key(self):
        return (self.kind, self.name, self.state, self.status, tuple(sorted(self.pal.items())) if self.pal else None,
                self.dimmable, self.pressed, self.icons, self.busy, self.done)


# ---------------------------------------------------------------- överrad: flikar, klocka, spelikon och kugghjul
# Från höger: kugghjulet (inställningar), spelikonen (öppnar spelväljaren), klockan och flikarna. Knapparna är
# 48 px breda och lika höga som flikarna (60 px) så att flikraden får så mycket plats som möjligt.
NAV_RECT = (0, 10, 806, 82)
CLOCK_X = 898.0                 # klockans högerkant (spelikonen och kugghjulet sitter till höger om den)
CLOCK_RECT = (806, 10, 902, 82)
GAME_RECT = (906, 16, 954, 76)
GAME_SLOT = (902, 10, 956, 82)
GAME_HIT = (900, 6, 957, 80)
GEAR_RECT = (960, 16, 1008, 76)
GEAR_SLOT = (956, 10, W, 82)
GEAR_HIT = (957, 6, W, 80)
TITLE_END = 800                 # rubriker i dimvyn och inställningarna får inte nå klockan


def tab_geometry(tabs):
    """tabs: lista av dict(title, icon, badge|None, tight|None). Ger flyttalsgeometri och heltalsruta (för tryck).
    tight: märket (bara en siffra, när flikarna annars inte ryms) ritas med mindre luft runt siffran."""
    out = []
    x = 16.0
    for t in tabs:
        tw = text_width(t['title'], 500, 21)
        w = 4 + 44 + 26 + 12 + tw
        bw = None
        pad, gap = (6, 8) if t.get('tight') else (10, 12)
        if t.get('badge'):
            bw = text_width(t['badge'], 500, 14) + 2 * pad
            w += gap + bw
        out.append({'x': x, 'w': w, 'tw': tw, 'bw': bw, 'pad': pad, 'gap': gap, 'rect': (snap(x), 16, snap(x + w), 76)})
        x += w + 12
    return out


def draw_nav(img, tabs, active):
    clear(img, *NAV_RECT)
    for idx, (g, t) in enumerate(zip(tab_geometry(tabs), tabs)):
        on = idx == active
        if on:
            fill, border, tcol, icol = T.BLUE_BG, T.BLUE, T.TEXT, T.BLUE_L
        else:
            fill, border, tcol, icol = T.CARD, T.CARD_BORDER, T.MUTED, T.FOOT
        x0, _, x1, _ = g['rect']
        bbox(img, x0, 16, x1, 76, 18, fill, border, 2)
        ix = g['x'] + 2 + 22
        icon(img, t['icon'], 26, snap(ix), 33, icol)
        tx = ix + 26 + 12
        text(img, tx, 53, t['title'], 500, 21, tcol)
        if g['bw']:
            bx = tx + g['tw'] + g['gap']
            rbox(img, snap(bx), 34, snap(bx + g['bw']), 58, 12, T.BLUE_D)
            text(img, bx + g['pad'], 51, t['badge'], 500, 14, T.BLUE_L)


def draw_back(img, label):
    """Tillbaka-knappen i dimvyn. Ger rutan (för tryck)."""
    tw = text_width(label, 500, 21)
    w = 78 + tw          # mätt i Chromium: 169,59 px för "Belysning"
    clear(img, 0, 10, 600, 82)
    bbox(img, 16, 16, snap(16 + w), 76, 18, T.CARD, T.CARD_BORDER, 2)
    icon(img, 'ChevronLeft', 32, 30, 30, T.TEXT)
    text(img, 68, 53, label, 500, 21, T.TEXT)
    return (16, 16, snap(16 + w), 76), 16 + w


def draw_dim_title(img, title, x_after_back):
    x = x_after_back + 16
    clear(img, snap(x) - 4, 20, TITLE_END, 72)
    text(img, x, 56, fit(title, 400, 30, TITLE_END - x), 400, 30, T.TEXT)


def draw_clock(img, hhmm):
    clear(img, *CLOCK_RECT)
    text(img, CLOCK_X, 58, hhmm, 300, 36, T.TEXT, anchor='rs')


def _corner_button(img, rect, slot, icon_name, active=False, pressed=False):
    """Rund-rektangulär ikonknapp i hörnet (kugghjulet, spelikonen). active: sidan den öppnar visas just nu."""
    clear(img, *slot)
    if active:
        fill, border, icol = T.BLUE_BG, T.BLUE, T.BLUE_L
    else:
        fill, border, icol = T.CARD, T.CARD_BORDER, T.MUTED
    if pressed:
        fill = blend(fill, (255, 255, 255), 0.07)
    x0, y0, x1, y1 = rect
    bbox(img, x0, y0, x1, y1, 18, fill, border, 2)
    icon(img, icon_name, 32, x0 + (x1 - x0 - 32) // 2, y0 + (y1 - y0 - 32) // 2, icol)


def draw_gear(img, active=False, pressed=False):
    """Kugghjulsknappen längst till höger. active: inställningssidan är öppen."""
    _corner_button(img, GEAR_RECT, GEAR_SLOT, 'Cog', active, pressed)


def draw_game_btn(img, pressed=False):
    """Spelikonen till vänster om kugghjulet: öppnar spelväljaren (Blockpussel, Sudoku), från alla sidor."""
    _corner_button(img, GAME_RECT, GAME_SLOT, 'GamepadVariant', False, pressed)


# ---------------------------------------------------------------- nederkant: datum och anslutning
def draw_footer_date(img, s):
    clear(img, 16, 566, 500, 594)
    text(img, 24, 585, s, 400, 14, T.FOOT)


def draw_footer_status(img, level, msg, wifi_pct=None, batt=None):
    """level: ok (blå wifi-symbol), wait (grå), bad (orange, överstruken). wifi_pct: Wi-Fi-styrka 1-100 eller None;
    visas som "78 %" närmast symbolen (orange under 30 %). batt: (procent, läge) eller None; batterigruppen sitter
    till vänster om wifigruppen (se draw_footer_battery)."""
    clear(img, 500, 566, W, 594)
    tw = text_width(msg, 400, 14)
    pct_s = ('%d %%' % wifi_pct) if wifi_pct is not None else None
    pw = text_width(pct_s, 500, 14) + 14 if pct_s else 0
    x = 1000.0 - (18 + 8 + pw + tw)
    if level == 'ok':
        icon(img, 'Wifi', 18, snap(x), 571, T.BLUE_L)
        col = T.FOOT
    elif level == 'bad':
        icon(img, 'WifiOff', 18, snap(x), 571, T.WARN)
        col = T.WARN
    else:
        icon(img, 'Wifi', 18, snap(x), 571, T.FOOT)
        col = T.FOOT
    cx = x + 26
    if pct_s:
        text(img, cx, 585, pct_s, 500, 14, T.WARN if wifi_pct < 30 else T.MUTED)
        cx += pw
    text(img, cx, 585, msg, 400, 14, col)
    if batt is not None:
        draw_footer_battery(img, x - BATT_GAP, batt[0], batt[1])


# ---------------------------------------------------------------- batteri i sidfoten
BATT_BODY = (26, 14)            # kroppens bredd och höjd i px (uttaget till höger kommer utanpå)
BATT_ICON_Y = 573               # ikonens överkant: mitten på samma höjd som texten och wifisymbolen
BATT_GAP = 22                   # luft mellan batterigruppen och wifigruppen
BATT_MIN_X = 504                # längre åt vänster får gruppen inte nå (datumet ligger till vänster om 500)
BATT_LABELS = {'charging': 'Laddar', 'full': 'Full', 'idle': 'Laddar inte', 'discharging': 'På batteri'}
_BOLT = [(0.62, 0.00), (0.12, 0.58), (0.46, 0.58), (0.34, 1.00), (0.88, 0.40), (0.52, 0.40)]
_batt_masks_cache = {}


def batt_colors(pct, state):
    """(fyllningens färg, procenttextens färg). Låg nivå utan laddning varnar: orange (till 20 %), röd (till 10 %)."""
    if state != 'charging':
        if pct <= 10:
            return T.RED, T.RED
        if pct <= 20:
            return T.WARN, T.WARN
    return T.BLUE_L, T.MUTED


def batt_masks(pct, charging):
    """Alfamasker (kontur med uttag, fyllning, blixt) för batterisymbolen, 8x översamplade och nedskalade. Fyllningen
    är urskuren runt blixten så att den syns tydligt. Samma stil som Material Design Icons: rundade hörn, jämn linje."""
    key = (pct, charging)
    hit = _batt_masks_cache.get(key)
    if hit is not None:
        return hit
    bw, bh = BATT_BODY
    stroke, pad, r, nub_w, nub_h, bolt_w = 1.7, 1.5, 2.8, 2.4, 5.6, 7.0
    tw = bw + int(round(nub_w)) + 1
    ss = 8
    big = lambda: Image.new('L', (tw * ss, bh * ss), 0)
    o, f, b = big(), big(), big()
    do, df, db = ImageDraw.Draw(o), ImageDraw.Draw(f), ImageDraw.Draw(b)
    do.rounded_rectangle((0, 0, bw * ss - 1, bh * ss - 1), radius=r * ss, fill=255)
    do.rounded_rectangle((stroke * ss, stroke * ss, (bw - stroke) * ss - 1, (bh - stroke) * ss - 1),
                         radius=max(0.6, r - stroke) * ss, fill=0)
    ny0 = (bh - nub_h) / 2.0
    do.rounded_rectangle(((bw + 0.7) * ss, ny0 * ss, (bw + 0.7 + nub_w) * ss - 1, (ny0 + nub_h) * ss - 1),
                         radius=1.0 * ss, fill=255)
    ix0, iy0 = stroke + pad, stroke + pad
    ix1, iy1 = bw - stroke - pad, bh - stroke - pad
    fw = max(0.0, min(1.0, pct / 100.0)) * (ix1 - ix0)
    if fw > 0.2:
        df.rounded_rectangle((ix0 * ss, iy0 * ss, (ix0 + fw) * ss - 1, iy1 * ss - 1), radius=1.0 * ss, fill=255)
    if charging:
        cx, cy, bh_ = bw / 2.0, bh / 2.0, bh - 3.0
        db.polygon([((cx - bolt_w / 2 + x * bolt_w) * ss, (cy - bh_ / 2 + y * bh_) * ss) for x, y in _BOLT], fill=255)
    box = getattr(getattr(Image, 'Resampling', Image), 'BOX')
    o, f, b = (m.resize((tw, bh), box) for m in (o, f, b))
    if charging:
        f = Image.composite(Image.new('L', f.size, 0), f, b.filter(ImageFilter.MaxFilter(3)))
    if len(_batt_masks_cache) >= 300:
        _batt_masks_cache.pop(next(iter(_batt_masks_cache)))
    hit = (o, f, b)
    _batt_masks_cache[key] = hit
    return hit


def batt_group_width():
    """Batterigruppens bredd: ikon, procent och text. Fast, så att inget flyttar sig när siffran eller läget byts."""
    iw = BATT_BODY[0] + int(round(2.4)) + 1
    pw = text_width('100 %', 500, 14)
    lw = max(text_width(s, 400, 14) for s in BATT_LABELS.values())
    return iw + 6 + pw + 7 + lw


def draw_footer_battery(img, right, pct, state):
    """Batterisymbol, procent och läge ("Laddar", "Full", "Laddar inte", "På batteri") med högerkant vid right. Ritar inget
    om gruppen inte ryms till höger om datumet. Rensas av draw_footer_status."""
    gx = right - batt_group_width()
    if gx < BATT_MIN_X:
        return
    pct = max(0, min(100, int(pct)))
    fill, tcol = batt_colors(pct, state)
    o, f, b = batt_masks(pct, state == 'charging')
    x = snap(gx)
    img.paste(T.FOOT, (x, BATT_ICON_Y), o)
    img.paste(fill, (x, BATT_ICON_Y), f)
    if state == 'charging':
        img.paste(T.YELLOW, (x, BATT_ICON_Y), b)
    pw = text_width('100 %', 500, 14)
    px = gx + o.size[0] + 6
    text(img, px + pw, 585, '%d %%' % pct, 500, 14, tcol, anchor='rs')
    text(img, px + pw + 7, 585, BATT_LABELS.get(state, ''), 400, 14, T.FOOT)


# ---------------------------------------------------------------- lampfliken (3a)
CELL_X = (16, 518)
CELL_W = 490
CELL_H = 108.5
CELL_STEP = 120.5
GRID_TOP = 86


def cell_origin(i):
    return CELL_X[i % 2], GRID_TOP + (i // 2) * CELL_STEP


def cell_rect(i):
    x, top = cell_origin(i)
    return (x, snap(top), x + CELL_W, snap(top + CELL_H))


def lamp_zones(i, dimmable):
    """Tryckytor i en cell: (växla-vänster, namn, växla-höger). För icke dimbar lampa: hela cellen = växla."""
    x0, y0, x1, y1 = cell_rect(i)
    if not dimmable:
        return {'toggle': [(x0, y0, x1, y1)], 'dim': []}
    return {'toggle': [(x0, y0, x0 + 93 - 8, y1), (x1 - 123, y0, x1, y1)],
            'dim': [(x0 + 93 - 8, y0, x1 - 123, y1)]}


def draw_toggle(img, x, y, on, enabled=True):
    if not enabled:
        border, fill, knob = (58, 58, 58), (30, 30, 30), (84, 84, 84)
        kx = x + 8
    elif on:
        border, fill, knob, kx = T.BLUE, T.BLUE_D, T.BLUE_L, x + 48
    else:
        border, fill, knob, kx = T.TOG_OFF_BORDER, T.TOG_OFF_BG, T.TOG_OFF_KNOB, x + 8
    bbox(img, x, y, x + 88, y + 48, 24, fill, border, 2)
    circle(img, kx, y + 8, 32, knob)


def draw_lamp_cell(img, i, vm):
    x, top = cell_origin(i)
    x0, y0, x1, y1 = cell_rect(i)
    clear(img, x0, y0, x1, y1)
    st = vm.state
    is_all = vm.kind == 'all'
    bw = 1
    on_icon, off_icon = vm.icons or ('Lightbulb', 'LightbulbOff')
    if st == 'on':
        if is_all:
            fill, border, circ, icol, scol, iname, bw = T.BLUE_BG, T.BLUE_D, T.BLUE_D, T.BLUE_L, T.BLUE_L, 'LightbulbMultiple', 2
        else:
            p = vm.pal or T.BLUE_PAL
            fill, border, circ, icol, scol, iname = p['bg'], p['border'], p['circle'], p['main'], p['main'], on_icon
    else:
        fill, border, circ, icol, scol = T.CARD, T.CARD_BORDER, T.OFF_CIRCLE, T.OFF_ICON, T.MUTED
        iname = 'LightbulbMultiple' if is_all else off_icon
        if st in ('na', 'stale'):
            circ, icol, scol = (31, 34, 38), (62, 78, 96), T.STALE_TEXT
    if vm.pressed:
        fill = blend(fill, (255, 255, 255), 0.07)
    bbox(img, x0, y0, x1, y1, 20, fill, border, bw)
    cy = snap(top + 24.25)
    circle(img, x + 17, cy, 60, circ)
    icon(img, iname, 36, x + 17 + 12, snap(top + 24.25 + 12), icol)
    maxw = 230 if vm.dimmable else 272
    name_col = T.TEXT if st in ('on', 'off') else (138, 138, 138)
    text(img, x + 93, ty(top + 50.25), fit(vm.name, 500, 22, maxw), 500, 22, name_col)
    text(img, x + 93, ty(top + 72.25), fit(vm.status, 400, 16, maxw), 400, 16, scol)
    if vm.dimmable:
        icon(img, 'ChevronRight', 28, x + 339, snap(top + 40.25), T.MUTED)
    if vm.kind == 'action':
        draw_action_btn(img, x + 381, snap(top + 30.25), st == 'on', enabled=st in ('on', 'off') and not vm.busy,
                        done=vm.done)
    else:
        draw_toggle(img, x + 381, snap(top + 30.25), st == 'on', enabled=st in ('on', 'off'))


def draw_action_btn(img, x, y, on, enabled=True, done=False):
    """Tryckknappen för scener, skript och knappar: samma storlek som växeln (88x48), med en spela-ikon
    (en bock när trycket gick igenom)."""
    if not enabled:
        border, fill, icol = (58, 58, 58), (30, 30, 30), (84, 84, 84)
    elif on:
        border, fill, icol = T.BLUE, T.BLUE_D, T.BLUE_L
    else:
        border, fill, icol = T.TOG_OFF_BORDER, T.TOG_OFF_BG, T.TEXT
    bbox(img, x, y, x + 88, y + 48, 24, fill, border, 2)
    icon(img, 'Check' if done else 'Play', 28, x + 30, y + 10, icol)


# ---------------------------------------------------------------- dimvyn (3b)
CARD_RECT = (16, 86, 752, 556)
SLIDER_RECT = (768, 86, 1008, 556)
TOGGLE_POS = (631, 131)
BTN_MINUS = (49, 447, 376, 527)
BTN_PLUS = (392, 447, 719, 527)
TOP_ROW_RECT = (40, 108, 728, 195)
VALUE_RECT = (40, 195, 728, 447)


def draw_dim_card(img):
    """Kortet med ram (tomt). Rita sedan rad, värde och knappar ovanpå."""
    bbox(img, *CARD_RECT, 20, T.CARD, T.CARD_BORDER, 1)


def draw_dim_top(img, state, status, pal):
    clear(img, *TOP_ROW_RECT, color=T.CARD)
    if state == 'on':
        circ, icol, iname, scol = pal['circle'], pal['main'], 'Lightbulb', pal['main']
    else:
        circ, icol, iname, scol = T.OFF_CIRCLE, T.OFF_ICON, 'LightbulbOff', T.MUTED
        if state in ('na', 'stale'):
            circ, icol, scol = (31, 34, 38), (62, 78, 96), T.STALE_TEXT
    circle(img, 49, 115, 80, circ)
    icon(img, iname, 52, 63, 129, icol)
    text(img, 149, 164, status, 500, 26, scol)
    draw_toggle(img, TOGGLE_POS[0], TOGGLE_POS[1], state == 'on', enabled=state in ('on', 'off'))


def draw_dim_value(img, value_text, dim=False):
    clear(img, *VALUE_RECT, color=T.CARD)
    text(img, 49, 244, 'Ljusstyrka', 400, 20, T.MUTED)
    col = (96, 96, 96) if dim else T.TEXT
    text(img, 49, 365, value_text, 300, 132, col)
    text(img, 49 + text_width(value_text, 300, 132) + 12, 365, '%', 300, 52, (96, 96, 96) if dim else T.MUTED)


def draw_dim_buttons(img, pressed=None, enabled=True):
    for name, rect in (('Minus', BTN_MINUS), ('Plus', BTN_PLUS)):
        fill = T.BTN_BG
        if pressed == name:
            fill = blend(fill, (255, 255, 255), 0.09)
        clear(img, *rect, color=T.CARD)
        bbox(img, *rect, 20, fill, T.CARD_BORDER, 1)
        cx = (rect[0] + rect[2]) / 2.0
        icon(img, name, 44, snap(cx - 22), 465, T.TEXT if enabled else (96, 96, 96))


def draw_slider(img, pct, state, pal):
    """Reglaget till höger. pct 0-100 eller None (okänd)."""
    x0, y0, x1, y1 = SLIDER_RECT
    if state == 'on':
        track, tborder, fillc = pal['bg'], pal['border'], pal['main']
    else:
        track, tborder, fillc = (24, 24, 24), T.CARD_BORDER, None
    clear(img, x0, y0, x1, y1)
    bbox(img, x0, y0, x1, y1, 28, track, tborder, 1)
    if fillc is None or not pct:
        return
    inner_w, inner_h = x1 - x0 - 2, y1 - y0 - 2
    top = snap((y1 - 1) - inner_h * pct / 100.0)
    m = rbox_mask(inner_w, inner_h, 27).copy()
    rel = top - (y0 + 1)
    if rel > 0:
        ImageDraw.Draw(m).rectangle((0, 0, inner_w - 1, rel - 1), fill=0)
    img.paste(fillc, (x0 + 1, y0 + 1), m)
    bar_top = snap((y1 - 1) - inner_h * pct / 100.0 + 16)
    if bar_top + 6 <= y1 - 1:
        rbox(img, x0 + 1 + (inner_w - 60) // 2, bar_top, x0 + 1 + (inner_w - 60) // 2 + 60, bar_top + 6, 3,
             blend(fillc, track, 0.55))


# ---------------------------------------------------------------- temperaturfliken (3c)
BIG_CARDS = ((16, 86, 356, 315), (16, 327, 356, 556))
SMALL_COLS = (368.0, 368.0 + 205.328125 + 12, 368.0 + 2 * (205.328125 + 12))
SMALL_W = 205.328125
SMALL_ROWS = (86.0, 86.0 + 148.65625 + 12, 86.0 + 2 * (148.65625 + 12))
SMALL_H = 148.65625


def small_rect(k):
    """Ruta (heltal) för liten kort nr k (0-8, rad för rad)."""
    c, r = k % 3, k // 3
    x, top = SMALL_COLS[c], SMALL_ROWS[r]
    return (snap(x), snap(top), snap(x + SMALL_W), snap(top + SMALL_H))


def draw_temp_big(img, k, label, value, unit, stale=False, iname='Thermometer', textual=False):
    """Stort värdekort. textual: värdet är text (binär sensor, val, datum), ritas mindre och kan ta två rader."""
    x0, y0, x1, y1 = BIG_CARDS[k]
    clear(img, x0, y0, x1, y1)
    bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
    icon(img, iname, 28, 43, y0 + 23, T.OFF_ICON if not stale else (62, 78, 96))
    text(img, 81, y0 + 44, fit(label, 400, 20, 340 - 81 - 26), 400, 20, T.MUTED)
    base = y1 - 57
    if stale:
        text(img, 43, base, '–', 300, 88, T.STALE_TEXT)
        return
    if textual:
        lines = wrap(value, 400, 40, 340 - 43 - 26)
        if len(lines) > 2:
            lines = [lines[0], fit(' '.join(lines[1:]), 400, 40, 340 - 43 - 26)]
        for n, ln in enumerate(lines):
            text(img, 43, base - 48 * (len(lines) - 1 - n), ln, 400, 40, T.TEXT)
        return
    value = fit(value, 300, 88, 340 - 43 - 26 - 60)
    text(img, 43, base, value, 300, 88, T.TEXT)
    if unit:
        text(img, 43 + text_width(value, 300, 88), base, ' ' + unit, 400, 36, T.MUTED)


def draw_temp_small(img, k, label, value, unit, stale=False, iname='Thermometer', textual=False):
    x0, y0, x1, y1 = small_rect(k)
    c, r = k % 3, k // 3
    fx, ftop = SMALL_COLS[c], SMALL_ROWS[r]
    fbottom = ftop + SMALL_H
    clear(img, x0, y0, x1, y1)
    bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
    icon(img, iname, 22, snap(fx + 19), snap(ftop + 17), T.OFF_ICON if not stale else (62, 78, 96))
    text(img, fx + 49, ty(ftop + 34), fit(label, 400, 17, 137), 400, 17, T.MUTED)
    base = ty(fbottom - 33)
    if stale:
        text(img, fx + 19, base, '–', 500, 42, T.STALE_TEXT)
        return
    if textual:
        text(img, fx + 19, base, fit(value, 500, 28, 167), 500, 28, T.TEXT)
        return
    value = fit(value, 500, 42, 167 - (28 if unit else 0))
    text(img, fx + 19, base, value, 500, 42, T.TEXT)
    if unit:
        text(img, fx + 19 + text_width(value, 500, 42), base, ' ' + unit, 400, 20, T.MUTED)


_SK_HEAD = (96, 84, 108, 92)
_SK_VAL = (84, 70, 90, 76)


def draw_temp_skeleton(img, k, variant=0):
    x0, y0, x1, y1 = small_rect(k)
    c, r = k % 3, k // 3
    fx, ftop = SMALL_COLS[c], SMALL_ROWS[r]
    fbottom = ftop + SMALL_H
    clear(img, x0, y0, x1, y1)
    bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
    circle(img, snap(fx + 19), snap(ftop + 17), 22, T.SKELETON)
    hw = _SK_HEAD[variant % 4]
    rbox(img, snap(fx + 49), snap(ftop + 23), snap(fx + 49 + hw), snap(ftop + 33), 5, T.SKELETON)
    vw = _SK_VAL[variant % 4]
    rbox(img, snap(fx + 19), snap(fbottom - 41), snap(fx + 19 + vw), snap(fbottom - 17), 8, T.SKELETON)


# ---------------------------------------------------------------- tomma flikar
def draw_empty(img, line1, line2=None):
    clear(img, 16, 86, 1008, 556)
    w1 = text_width(line1, 500, 30)
    text(img, 512 - w1 / 2.0, 300, line1, 500, 30, T.MUTED)
    if line2:
        w2 = text_width(line2, 400, 20)
        text(img, 512 - w2 / 2.0, 342, line2, 400, 20, T.FOOT)


# ---------------------------------------------------------------- välkomstskärmen (inga flikar)
WELCOME_LINES = ('Den här skärmen visar och styr ditt Home Assistant:',
                 '•  lampor, strömbrytare, scener, automationer och hjälpare',
                 '•  temperaturer och andra värden, med grafer över tid',
                 'Allt väljs på redigeringssidan, från mobilen eller datorn:')


def draw_welcome(img, url, ip=None):
    """Visas när panelen inte har några flikar: vad panelen gör och hur man kommer igång (adress och QR-kod)."""
    x0, y0, x1, y1 = 16, 86, 1008, 556
    clear(img, x0, y0, x1, y1)
    bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
    tx = 52
    text(img, tx, 160, 'Välkommen', 300, 52, T.TEXT)
    text(img, tx, 198, 'simple_ha_dash, en pekskärm för Home Assistant', 400, 20, T.MUTED)
    y = 254
    for i, line in enumerate(WELCOME_LINES):
        col = T.TEXT if i in (0, 3) else T.MUTED
        text(img, tx, y, line, 400, 20, col)
        y += 34 if i in (0, 1) else 52
    qr_x = 1008 - 40 - QR_TARGET
    maxw = qr_x - tx - 24
    if url:
        text(img, tx, y + 4, fit(url, 500, 30, maxw), 500, 30, T.BLUE_L)
        text(img, tx, y + 44, 'Skanna QR-koden eller skriv adressen i en webbläsare på samma nät.', 400, 16, T.FOOT)
        size = draw_qr(img, qr_x, 150, url)
        _centered(img, qr_x + size // 2, 150 + size + 26, 'Skanna med mobilens kamera', 400, 14, T.MUTED)
    else:
        text(img, tx, y + 4, 'Hittar ingen nätverksadress.', 500, 24, T.WARN)
        text(img, tx, y + 40, 'Kontrollera att plattan är ansluten till nätet.', 400, 18, T.FOOT)


# ---------------------------------------------------------------- inställningssidan (kugghjulet)
# Överst: kortet med QR-kod, adress och hur man startar panelen igen (vänster) och knapparna Uppdatera, Starta om,
# Stäng av och Avsluta (höger). Underst: två reglage, ljusstyrka och tid tills skärmen släcks.
SET_LEFT = (16, 86, 636, 378)
# fyra knappar i högerkolumnen (64 px höga, 12 px mellan): Uppdatera (med versionsnumret) överst, sedan Starta om,
# Stäng av och Avsluta. Spelet har fått en egen ikon i överraden (GAME_RECT).
SBTN_ORDER = ('update', 'reboot', 'poweroff', 'quit')
SBTN = {'update': (652, 86, 1008, 150), 'reboot': (652, 162, 1008, 226), 'poweroff': (652, 238, 1008, 302),
        'quit': (652, 314, 1008, 378)}
CONF_CARD = (16, 86, 1008, 556)
CBTN = {'cancel': (240, 448, 500, 528), 'ok': (524, 448, 784, 528)}
QR_XY = (32, 104)
QR_TARGET = 222
TXT_X = 270                         # textkolumnen till höger om QR-koden
START_CMD = 'systemctl start dash-panel'

SET_SLIDERS = (16, 388, 1008, 556)
SLIDER_ROWS = (388, 472)            # radernas överkant: 0 = ljusstyrka, 1 = tid tills skärmen släcks (84 px per rad)
SLIDER_ROW_RECT = ((36, 392, 988, 472), (36, 473, 988, 554))      # det som ritas om när ett reglage flyttas
SLIDER_HIT = ((24, SLIDER_ROWS[0] + 38, 1000, SLIDER_ROWS[0] + 84), (24, SLIDER_ROWS[1] + 38, 1000, SLIDER_ROWS[1] + 82))
SLIDER_N = ((BRIGHT_MAX - BRIGHT_MIN) // BRIGHT_STEP + 1, (OFF_MAX - OFF_MIN) // OFF_STEP + 1)     # 10 och 24 lägen
SL_TRACK = (52, 972)                # spårets ändar
SL_CX0, SL_CX1 = 70, 954            # kulans mittpunkt längst till vänster och höger
SLIDER_TEXT = ({'label': 'Ljusstyrka', 'icon': 'Brightness6'},
               {'label': 'Skärmen släcks efter', 'icon': 'MonitorOff'})

POWER_TEXT = {
    'update': {'icon': 'CloudDownload', 'label': 'Uppdatera', 'hint': 'Hämtar senaste versionen från GitHub',
               'ask': 'Uppdatera panelen?',
               'ask_sub': 'Hämtar den senaste versionen från GitHub. Finns en ny version startar panelen om '
                          'efter några sekunder. Finns ingen ny version händer ingenting.'},
    'reboot': {'icon': 'Restart', 'label': 'Starta om', 'hint': 'Tar ungefär 40 sekunder',
               'ask': 'Starta om enheten?',
               'ask_sub': 'Panelen är borta i ungefär 40 sekunder medan enheten startar om.',
               'busy': 'Startar om …', 'busy_sub': 'Panelen är tillbaka om ungefär 40 sekunder.',
               'fail': 'Det gick inte att starta om'},
    'poweroff': {'icon': 'Power', 'label': 'Stäng av', 'hint': 'Starta igen via strömsladden',
                 'ask': 'Stänga av enheten?',
                 'ask_sub': 'Enheten startar inte igen av sig själv. Dra ur och sätt i strömsladden när du vill starta den.',
                 'busy': 'Stänger av …', 'busy_sub': 'Dra ur och sätt i strömsladden när du vill starta den igen.',
                 'fail': 'Det gick inte att stänga av'},
    'quit': {'icon': 'ExitToApp', 'label': 'Avsluta', 'hint': 'Stänger panelen, enheten går kvar',
             'ask': 'Avsluta panelen?',
             'ask_sub': 'Skärmen går tillbaka till textkonsolen och enheten fortsätter köra. '
                        'Efter en omstart startar panelen av sig själv igen.',
             'busy': 'Avslutar …', 'busy_sub': 'Panelen stängs och skärmen går tillbaka till textkonsolen.',
             'fail': 'Det gick inte att avsluta'},
}


def _centered(img, cx, baseline, s, weight, size, color):
    text(img, cx - text_width(s, weight, size) / 2.0, baseline, s, weight, size, color)


def _power_icon_color(kind):
    return {'update': T.GREEN, 'reboot': T.BLUE_L, 'poweroff': T.RED, 'quit': T.WARN}[kind]


def draw_qr(img, x, y, url):
    """QR-kod som svarta moduler på en vit, avrundad ruta (tyst zon ingår). Ger rutans bredd."""
    size, mask = qr_mask(url, QR_TARGET)
    rbox(img, x, y, x + size, y + size, 14, (255, 255, 255))
    img.paste((0, 0, 0), (x, y), mask)
    return size


def start_lines(ip):
    """De två raderna som startar panelen igen efter Avsluta: logga in på dash och starta tjänsten."""
    return 'ssh root@%s' % (ip or '<IP-adress>'), START_CMD


def _draw_start_block(img, x, y, ip, width):
    """Avdelare och "Starta panelen igen"-raderna med början vid x, y (avdelarens höjd)."""
    clear(img, x, y, x + width, y + 1, color=T.CARD_BORDER)
    text(img, x, y + 26, 'Starta panelen igen efter Avsluta (via ssh):', 400, 15, T.MUTED)
    for i, line in enumerate(start_lines(ip)):
        text(img, x, y + 54 + 28 * i, fit(line, 500, 18, width), 500, 18, T.TEXT)


def draw_settings_left(img, url, ip, port):
    """Kortet till vänster: hur man når redigeringssidan (QR-kod, adress och IP i klartext) och hur man startar
    panelen igen efter Avsluta."""
    x0, y0, x1, y1 = SET_LEFT
    clear(img, x0, y0, x1, y1)
    bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
    if not url:
        text(img, 44, 128, 'Ställ in panelen från mobilen', 500, 22, T.TEXT)
        text(img, 44, 190, 'Hittar ingen nätverksadress.', 500, 24, T.MUTED)
        text(img, 44, 224, 'Kontrollera att dash är ansluten till nätet.', 400, 18, T.FOOT)
        _draw_start_block(img, 44, 262, None, 560)
        return
    size = draw_qr(img, QR_XY[0], QR_XY[1], url)
    cx = QR_XY[0] + size // 2
    _centered(img, cx, QR_XY[1] + size + 22, 'Skanna med mobilens kamera.', 400, 14, T.MUTED)
    _centered(img, cx, QR_XY[1] + size + 40, 'Mobilen måste vara på samma Wi-Fi.', 400, 14, T.MUTED)
    x = TXT_X
    text(img, x, 124, 'Ställ in panelen från mobilen', 500, 22, T.TEXT)
    text(img, x, 164, 'IP-adress', 400, 15, T.MUTED)
    text(img, x, 198, fit(ip or '', 500, 32, 250), 500, 32, T.TEXT)
    text(img, 540, 164, 'Port', 400, 15, T.MUTED)
    text(img, 540, 198, fit(port or '', 500, 32, 80), 500, 32, T.TEXT)
    text(img, x, 228, fit(url, 400, 19, 342), 400, 19, T.MUTED)
    _draw_start_block(img, x, 252, ip, 342)


def draw_settings_button(img, kind, pressed=False, hint=None):
    """Knapparna Uppdatera, Starta om, Stäng av och Avsluta. hint: texten under namnet om den ska vara en annan än
    standardtexten (Uppdatera visar versionsnumret)."""
    x0, y0, x1, y1 = SBTN[kind]
    tx = POWER_TEXT[kind]
    clear(img, x0, y0, x1, y1)
    fill = blend(T.CARD, (255, 255, 255), 0.07) if pressed else T.CARD
    bbox(img, x0, y0, x1, y1, 20, fill, T.CARD_BORDER, 1)
    icon(img, tx['icon'], 40, x0 + 24, y0 + (y1 - y0 - 40) // 2, _power_icon_color(kind))
    mid = y0 + (y1 - y0) // 2
    text(img, x0 + 84, mid - 3, tx['label'], 500, 24, T.TEXT)
    text(img, x0 + 84, mid + 19, fit(hint or tx['hint'], 400, 16, x1 - x0 - 84 - 16), 400, 16, T.MUTED)


# ---------------------------------------------------------------- reglagen: ljusstyrka och tid tills skärmen släcks
def fmt_seconds(s):
    """5 s, 60 s -> "1 min", 90 s -> "1 min 30 s"."""
    if s < 60:
        return '%d s' % s
    m, r = divmod(int(s), 60)
    return '%d min' % m if r == 0 else '%d min %d s' % (m, r)


def slider_value(row, idx):
    """Reglagets värde i läge idx: procent (rad 0) eller sekunder (rad 1)."""
    return BRIGHT_MIN + BRIGHT_STEP * idx if row == 0 else OFF_MIN + OFF_STEP * idx


def slider_idx_of(row, value):
    lo, step = (BRIGHT_MIN, BRIGHT_STEP) if row == 0 else (OFF_MIN, OFF_STEP)
    return max(0, min(SLIDER_N[row] - 1, int(round((value - lo) / float(step)))))


def slider_idx_at(row, x):
    """Läget som hör till ett tryck vid x."""
    n = SLIDER_N[row]
    return max(0, min(n - 1, int(round((x - SL_CX0) * (n - 1) / float(SL_CX1 - SL_CX0)))))


def slider_cx(row, idx):
    return snap(SL_CX0 + (SL_CX1 - SL_CX0) * idx / float(SLIDER_N[row] - 1))


def slider_text(row, idx):
    v = slider_value(row, idx)
    return '%d %%' % v if row == 0 else fmt_seconds(v)


def draw_sliders_card(img, available=True):
    """Kortet med de två reglagen (tomt). Raderna ritas sedan för sig med draw_slider_row."""
    x0, y0, x1, y1 = SET_SLIDERS
    clear(img, x0, y0, x1, y1)
    bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
    if not available:
        text(img, 44, 480, 'Ingen styrbar bakgrundsbelysning hittades på den här enheten.', 400, 18, T.FOOT)
        return
    clear(img, 40, SLIDER_ROWS[1], 984, SLIDER_ROWS[1] + 1, color=T.CARD_BORDER)


def draw_slider_row(img, row, idx, active=False):
    """En rad: ikon, namn, värde och reglaget. active: fingret ligger på reglaget."""
    y0 = SLIDER_ROWS[row]
    clear(img, *SLIDER_ROW_RECT[row], color=T.CARD)
    tx = SLIDER_TEXT[row]
    icon(img, tx['icon'], 28, 40, y0 + 14, T.MUTED)
    text(img, 80, y0 + 36, tx['label'], 500, 21, T.TEXT)
    text(img, 984, y0 + 36, slider_text(row, idx), 500, 24, T.BLUE_L if active else T.TEXT, anchor='rs')
    cy = y0 + 62
    cx = slider_cx(row, idx)
    rbox(img, SL_TRACK[0], cy - 6, SL_TRACK[1], cy + 6, 6, T.SLIDER_EMPTY)
    rbox(img, SL_TRACK[0], cy - 6, cx + 1, cy + 6, 6, T.BLUE)
    r = 19 if active else 16
    circle(img, cx - r, cy - r, 2 * r, T.BLUE_L if active else T.TEXT)


# ---------------------------------------------------------------- frågan före Starta om / Stäng av / Avsluta
def _centered_card(img, kind, title, sub, title_col=None, dy=0, icon_color=None):
    x0, y0, x1, y1 = CONF_CARD
    clear(img, 0, 84, W, 564)
    bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
    icon(img, POWER_TEXT[kind]['icon'], 64, 512 - 32, 132 + dy, icon_color or _power_icon_color(kind))
    _centered(img, 512, 262 + dy, title, 500, 34, title_col or T.TEXT)
    n = 0
    for i, line in enumerate(wrap(sub, 400, 20, 640)):
        _centered(img, 512, 306 + dy + 30 * i, line, 400, 20, T.MUTED)
        n = i + 1
    return 306 + dy + 30 * max(0, n - 1)           # sista radens baslinje


def _start_box(img, ip, label_y):
    """Rutan med kommandona som startar panelen igen (visas när man avslutar panelen)."""
    _centered(img, 512, label_y, 'Starta panelen igen från datorn:', 400, 18, T.MUTED)
    x0, y0, x1, y1 = 256, label_y + 12, 768, label_y + 12 + 78
    bbox(img, x0, y0, x1, y1, 14, T.BG, T.CARD_BORDER, 1)
    for i, line in enumerate(start_lines(ip)):
        text(img, x0 + 28, y0 + 33 + 28 * i, fit(line, 500, 22, x1 - x0 - 56), 500, 22, T.TEXT)


CBTN_AREA = (CBTN['cancel'][0], CBTN['cancel'][1], CBTN['ok'][2], CBTN['ok'][3])


def draw_confirm_card(img, kind, ip=None):
    """Frågan "Starta om enheten?" (knapparna ritas för sig med draw_confirm_buttons)."""
    tx = POWER_TEXT[kind]
    if kind == 'quit':
        last = _centered_card(img, kind, tx['ask'], tx['ask_sub'], dy=-30)
        _start_box(img, ip, last + 38)
    else:
        _centered_card(img, kind, tx['ask'], tx['ask_sub'], dy=20)


def draw_confirm_buttons(img, kind, pressed=None):
    """Avbryt och bekräftelseknappen (Starta om / Stäng av / Avsluta)."""
    tx = POWER_TEXT[kind]
    for name in ('cancel', 'ok'):
        r = CBTN[name]
        clear(img, r[0], r[1], r[2], r[3], color=T.CARD)
        if name == 'ok':
            fill, border = {'update': (T.GREEN_D, T.GREEN_BORDER), 'reboot': (T.BLUE_D, T.BLUE),
                            'poweroff': (T.RED_D, T.RED_BORDER), 'quit': (T.WARN_D, T.WARN_BORDER)}[kind]
            label = tx['label']
        else:
            fill, border, label = T.BTN_BG, T.CARD_BORDER, 'Avbryt'
        if pressed == name:
            fill = blend(fill, (255, 255, 255), 0.09)
        bbox(img, r[0], r[1], r[2], r[3], 20, fill, border, 1 if name == 'cancel' else 2)
        _centered(img, (r[0] + r[2]) // 2, (r[1] + r[3]) // 2 + 9, label, 500, 24, T.TEXT)


def draw_bye(img, kind, failed=False, ip=None):
    """Visas medan enheten stänger ned (eller om kommandot misslyckades)."""
    tx = POWER_TEXT[kind]
    if failed:
        _centered_card(img, kind, tx['fail'], 'Försök igen, eller kör kommandot via ssh.', T.WARN, dy=84)
    elif kind == 'quit':
        last = _centered_card(img, kind, tx['busy'], tx['busy_sub'], dy=30)
        _start_box(img, ip, last + 38)
    else:
        _centered_card(img, kind, tx['busy'], tx['busy_sub'], dy=84)


def draw_update_status(img, st):
    """Uppdateringens skärm: söker/installerar (kind busy) eller resultatet (current, ok, rolled, failed). st: dict med
    kind, title, sub och done (resultatet visas till man trycker, annars efter en stund)."""
    good = st['kind'] in ('busy', 'current', 'ok')
    _centered_card(img, 'update', st['title'], st['sub'], None if good else T.WARN, dy=40,
                   icon_color=T.GREEN if good else T.WARN)
    if st.get('done'):
        _centered(img, 512, 520, 'Tryck var som helst för att gå tillbaka', 400, 18, T.FOOT)
