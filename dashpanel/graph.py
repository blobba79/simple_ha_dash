"""Grafer över hur värden har ändrats, ur Home Assistants historik.

Upp till två dygn hämtas rå historik (history/history_during_period); längre perioder hämtas som timvärden ur
långtidsstatistiken (recorder/statistics_during_period, medel, min och max per timme), med historiken som reserv
upp till en vecka för sensorer som inte har statistik. Max och min räknas på det som hämtats (för statistik på
timmarnas min och max, så att toppar inte jämnas ut) och visas tydligt med tid.

Ritningen är Pillow, översamplad två gånger så att kurvorna blir mjuka även på A33."""
import datetime
import math

from PIL import Image, ImageDraw

from . import config as cfgmod, model, theme as T
from .gfx import bbox, blend, circle, fit, rbox, snap, text, text_width

COLORS = ((79, 195, 247), (255, 183, 77), (129, 199, 132))     # blå, orange, grön
MAX_COL = (239, 154, 154)
MIN_COL = (144, 202, 249)
RANGES = ((6, '6 tim'), (24, '24 tim'), (168, '7 dagar'), (720, '30 dagar'))
HISTORY_MAX_HOURS = 48        # längre perioder: långtidsstatistik
HISTORY_FALLBACK_HOURS = 168  # reserv om statistik saknas (längre än så blir för mycket data för plattan)
CACHE_SECONDS = 120.0         # så länge en hämtad graf får visas innan den hämtas igen
GRAPH_DOMAINS = cfgmod.GRAPH_DOMAINS

CARD = (16, 86, 1008, 556)
BTN_W, BTN_H, BTN_GAP = 96, 46, 8
BTN_Y = 102
PLOT = (86, 222, 980, 504)
SS = 2                        # översampling för kurvorna

WEEKDAYS = ('mån', 'tis', 'ons', 'tor', 'fre', 'lör', 'sön')
MONTHS = ('jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec')


def range_rects():
    """Knapparna för tidsintervall, högerjusterade överst i kortet: [(timmar, text, ruta)]."""
    n = len(RANGES)
    x = CARD[2] - 18 - n * BTN_W - (n - 1) * BTN_GAP
    out = []
    for h, label in RANGES:
        out.append((h, label, (x, BTN_Y, x + BTN_W, BTN_Y + BTN_H)))
        x += BTN_W + BTN_GAP
    return out


# ---------------------------------------------------------------- hämtning och tolkning
def _iso(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def parse_history(rows, t0, t1):
    """[{s, lu|lc}] -> [(t, v)] för tal inom [t0, t1]. Första raden är läget vid start (kan ha äldre tid)."""
    out = []
    for r in rows or ():
        if not isinstance(r, dict):
            continue
        v = _num(r.get('s', r.get('state')))
        t = r.get('lu', r.get('lc', r.get('last_updated')))
        if isinstance(t, str):
            try:
                t = datetime.datetime.fromisoformat(t.replace('Z', '+00:00')).timestamp()
            except ValueError:
                t = None
        t = _num(t)
        if t is None:
            continue
        if v is None:
            out.append((max(t, t0), None))         # ej tillgänglig: ett hål i kurvan
            continue
        out.append((min(max(t, t0), t1), v))
    return out


def parse_stats(rows):
    """[{start, mean, min, max}] -> [(mitt i perioden, medel, min, max)]. start är ms (nyare HA), s eller ISO-text."""
    out = []
    for r in rows or ():
        if not isinstance(r, dict):
            continue
        st, en = r.get('start'), r.get('end')
        vals = []
        for t in (st, en):
            if isinstance(t, str):
                try:
                    t = datetime.datetime.fromisoformat(t.replace('Z', '+00:00')).timestamp()
                except ValueError:
                    t = None
            t = _num(t)
            if t is not None and t > 1e11:
                t /= 1000.0
            vals.append(t)
        s0, s1 = vals
        if s0 is None:
            continue
        mid = s0 + ((s1 - s0) / 2.0 if s1 else 1800.0)
        mean, mn, mx = _num(r.get('mean')), _num(r.get('min')), _num(r.get('max'))
        if mean is None and mn is None and mx is None:
            continue
        if mean is None:
            mean = (mn + mx) / 2.0 if (mn is not None and mx is not None) else (mn if mn is not None else mx)
        out.append((mid, mean, mn if mn is not None else mean, mx if mx is not None else mean))
    return out


async def fetch(ha, ids, hours, now_ts):
    """Hämtar data för ids de senaste hours timmarna. Ger {entity_id: {'points': [(t, v)], 'band': [(t, medel, min, max)]|None}}
    eller None om Home Assistant inte svarade."""
    t1 = now_ts
    t0 = now_ts - hours * 3600.0
    out = {}
    need_hist = list(ids)
    if hours > HISTORY_MAX_HOURS:
        res = await ha.request({'type': 'recorder/statistics_during_period', 'start_time': _iso(t0), 'end_time': _iso(t1),
                                'statistic_ids': list(ids), 'period': 'hour', 'types': ['mean', 'min', 'max']}, timeout=40.0)
        if res is None:
            return None
        result = res.get('result') if res.get('success') else {}
        need_hist = []
        for e in ids:
            band = parse_stats((result or {}).get(e))
            if band:
                out[e] = {'points': [(b[0], b[1]) for b in band], 'band': band}
            elif hours <= HISTORY_FALLBACK_HOURS:
                need_hist.append(e)
            else:
                out[e] = {'points': [], 'band': None, 'nostats': True}
    if need_hist:
        res = await ha.request({'type': 'history/history_during_period', 'start_time': _iso(t0), 'end_time': _iso(t1),
                                'entity_ids': need_hist, 'minimal_response': True, 'no_attributes': True,
                                'significant_changes_only': False}, timeout=40.0)
        if res is None:
            return None
        result = res.get('result') if res.get('success') else {}
        for e in need_hist:
            out[e] = {'points': parse_history((result or {}).get(e), t0, t1), 'band': None}
    return out


def extremes(data):
    """((max, tid), (min, tid)) ur en serie, eller (None, None)."""
    hi = lo = None
    if data.get('band'):
        for t, _, mn, mx in data['band']:
            if hi is None or mx > hi[0]:
                hi = (mx, t)
            if lo is None or mn < lo[0]:
                lo = (mn, t)
    else:
        for t, v in data.get('points') or ():
            if v is None:
                continue
            if hi is None or v > hi[0]:
                hi = (v, t)
            if lo is None or v < lo[0]:
                lo = (v, t)
    return hi, lo


# ---------------------------------------------------------------- axlar
def nice_ticks(lo, hi, want=5):
    """Jämna steg för y-axeln: (lägsta, högsta, steg)."""
    if hi - lo < 1e-9:
        pad = max(abs(hi) * 0.05, 0.5)
        lo, hi = lo - pad, hi + pad
    raw = (hi - lo) / float(max(1, want - 1))
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    return math.floor(lo / step) * step, math.ceil(hi / step) * step, step


def time_ticks(t0, t1, hours, local_fn):
    """[(tid, text)] för x-axeln, på jämna lokala timmar eller dagar."""
    off = local_fn(t0) - datetime.datetime.utcfromtimestamp(t0)
    if hours <= 6:
        step_h, fmt = 1, 'hm'
    elif hours <= 24:
        step_h, fmt = 3, 'hm'
    elif hours <= 48:
        step_h, fmt = 6, 'hm'
    elif hours <= 168:
        step_h, fmt = 24, 'wd'
    else:
        step_h, fmt = 24 * 5, 'dm'
    lt0 = datetime.datetime.utcfromtimestamp(t0) + off
    if step_h < 24:
        first = lt0.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
        while first.hour % step_h:
            first += datetime.timedelta(hours=1)
    else:
        first = lt0.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        if step_h > 24:
            while first.day % 5 != 0 or first.day > 30:
                first += datetime.timedelta(days=1)
    out = []
    cur = first
    while True:
        t = t0 + (cur - lt0).total_seconds()
        if t >= t1:
            break
        if fmt == 'hm':
            lab = '%02d:%02d' % (cur.hour, cur.minute)
        elif fmt == 'wd':
            lab = '%s %d' % (WEEKDAYS[cur.weekday()], cur.day)
        else:
            lab = '%d %s' % (cur.day, MONTHS[cur.month - 1])
        out.append((t, lab))
        cur += datetime.timedelta(hours=step_h)
        if step_h > 24 and cur.day > 30:
            cur = cur.replace(day=1) + datetime.timedelta(days=32)
            cur = cur.replace(day=5)
    return out


def when_text(ts, now_ts, local_fn):
    """Tidpunkt för max/min: "14:20" i dag, "i går 14:20", "tis 14:20" inom en vecka, annars "12 okt 14:20"."""
    lt, ln = local_fn(ts), local_fn(now_ts)
    hm = '%02d:%02d' % (lt.hour, lt.minute)
    days = (ln.date() - lt.date()).days
    if days == 0:
        return 'i dag ' + hm
    if days == 1:
        return 'i går ' + hm
    if days < 7:
        return '%s %s' % (WEEKDAYS[lt.weekday()], hm)
    return '%d %s %s' % (lt.day, MONTHS[lt.month - 1], hm)


# ---------------------------------------------------------------- ritning
def fmt(v, decimals, sep):
    s = model.format_number(v, decimals, sep)
    return s if s is not None else '–'


def draw_ranges(img, hours, pressed=None, enabled=True):
    for h, label, r in range_rects():
        on = h == hours
        fill = T.BLUE_D if on else T.BTN_BG
        if pressed == h:
            fill = blend(fill, (255, 255, 255), 0.09)
        bbox(img, *r, 14, fill, T.BLUE if on else T.CARD_BORDER, 1)
        col = T.TEXT if on else (T.MUTED if enabled else (96, 96, 96))
        tw = text_width(label, 500, 17)
        text(img, (r[0] + r[2]) / 2.0 - tw / 2.0, r[1] + 30, label, 500, 17, col)


def _stat_block(img, x, label, value, unit, sub, col):
    text(img, x, 124, label, 400, 16, T.MUTED)
    text(img, x, 166, value, 500, 36, col)
    if unit and value != '–':
        text(img, x + text_width(value, 500, 36) + 4, 166, unit, 400, 18, T.MUTED)
    if sub:
        text(img, x, 192, sub, 400, 15, T.FOOT)


STATS_RECT = (24, 96, 576, 206)       # siffrorna överst (ritas om för sig när ett värde ändras)


def draw_stats(img, series, t1, local_fn, sep, clear_first=True):
    """Max, min och nu överst i kortet (en kurva: stora siffror med tid; flera: en rad per kurva)."""
    if clear_first:
        x0, y0, x1, y1 = STATS_RECT
        img.paste(T.CARD, (x0, y0, x1, y1))
    if len(series) == 1:
        s = series[0]
        hi, lo = extremes(s['data']) if s.get('data') else (None, None)
        d, u = s.get('decimals', 1), s.get('unit') or ''
        _stat_block(img, 40, 'Max', fmt(hi[0], d, sep) if hi else '–', u, when_text(hi[1], t1, local_fn) if hi else '', MAX_COL)
        _stat_block(img, 216, 'Min', fmt(lo[0], d, sep) if lo else '–', u, when_text(lo[1], t1, local_fn) if lo else '', MIN_COL)
        _stat_block(img, 392, 'Nu', fmt(s.get('now'), d, sep) if s.get('now') is not None else '–', u, None, T.TEXT)
    else:
        for i, s in enumerate(series):
            y = 120 + 30 * i
            col = COLORS[i % len(COLORS)]
            rbox(img, 40, y - 13, 54, y + 1, 3, col)
            text(img, 64, y, fit(s['name'], 500, 17, 150), 500, 17, T.TEXT)
            hi, lo = extremes(s['data']) if s.get('data') else (None, None)
            d, u = s.get('decimals', 1), s.get('unit') or ''
            parts = (('Nu', s.get('now'), T.TEXT), ('Max', hi[0] if hi else None, MAX_COL), ('Min', lo[0] if lo else None, MIN_COL))
            x = 226
            xmax = range_rects()[0][2][0] - 10
            for lab, v, c in parts:
                vs = fmt(v, d, sep) + ((' ' + u) if (u and v is not None) else '')
                if x + 34 + text_width(vs, 500, 17) > xmax:
                    break
                text(img, x, y, lab, 400, 15, T.MUTED)
                text(img, x + 34, y, vs, 500, 17, c)
                x += 34 + max(80, text_width(vs, 500, 17) + 14)


def _halo_text(img, x, y, s, weight, size, col):
    """Text med en mörk kant runt, så att den syns ovanpå kurvan."""
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        text(img, x + dx, y + dy, s, weight, size, T.CARD)
    text(img, x, y, s, weight, size, col)


def draw(img, series, hours, t0, t1, local_fn, sep, status=None, pressed=None):
    """Ritar hela grafkortet. series: [{'name', 'unit', 'decimals', 'data': {...}|None, 'now': tal|None}].
    status: None (data finns), 'loading', 'error' eller en egen text."""
    x0, y0, x1, y1 = CARD
    bbox(img, x0, y0, x1, y1, 20, T.CARD, T.CARD_BORDER, 1)
    draw_ranges(img, hours, pressed)
    draw_stats(img, series, t1, local_fn, sep, clear_first=False)
    px0, py0, px1, py1 = PLOT
    vals = []
    for s in series:
        dta = s.get('data') or {}
        if dta.get('band'):
            for _, m, mn, mx in dta['band']:
                vals.extend((mn, mx))
        else:
            vals.extend(v for _, v in dta.get('points') or () if v is not None)
    msg = None
    if status == 'loading' and not vals:
        msg = 'Hämtar historik från Home Assistant …'
    elif status == 'error' and not vals:
        msg = 'Kunde inte hämta historiken. Försöker igen om en stund.'
    elif isinstance(status, str) and status not in ('loading', 'error') and not vals:
        msg = status
    elif not vals:
        msg = 'Ingen historik för den här perioden.'
    # rutnät och axlar
    lo_v, hi_v, step = nice_ticks(min(vals), max(vals)) if vals else (0.0, 1.0, 0.25)
    span = (hi_v - lo_v) or 1.0

    def ymap(v):
        return py1 - (v - lo_v) / span * (py1 - py0)

    def xmap(t):
        return px0 + (t - t0) / float(t1 - t0) * (px1 - px0)
    sdec = 0 if abs(step - round(step)) < 1e-9 else (1 if abs(step * 10 - round(step * 10)) < 1e-9 else 2)
    g = (40, 40, 40)
    if vals:
        v = lo_v
        n = 0
        while v <= hi_v + step * 0.001 and n < 12:
            y = snap(ymap(v))
            img.paste(g, (px0, y, px1, y + 1))
            lab = model.format_number(v, sdec, sep) or ''
            text(img, px0 - 10 - text_width(lab, 400, 14), y + 5, lab, 400, 14, T.MUTED)
            v += step
            n += 1
    for t, lab in time_ticks(t0, t1, hours, local_fn):
        x = snap(xmap(t))
        img.paste((34, 34, 34), (x, py0, x + 1, py1))
        tw = text_width(lab, 400, 14)
        if px0 <= x - tw / 2 and x + tw / 2 <= px1 + 20:
            text(img, x - tw / 2.0, py1 + 24, lab, 400, 14, T.MUTED)
    img.paste((70, 70, 70), (px0, py1, px1, py1 + 1))
    if msg:
        tw = text_width(msg, 400, 19)
        text(img, (px0 + px1) / 2.0 - tw / 2.0, snap((py0 + py1) / 2.0 + 6), msg, 400, 19, T.MUTED)
        return
    # kurvorna (översamplade)
    W2, H2 = (px1 - px0) * SS, (py1 - py0 + 8) * SS
    for i, s in enumerate(series):
        dta = s.get('data') or {}
        col = COLORS[i % len(COLORS)]
        if dta.get('band') and len(series) == 1:
            band = Image.new('L', (W2, H2), 0)
            poly = [((xmap(t) - px0) * SS, (ymap(mx) - py0) * SS) for t, _, mn, mx in dta['band']]
            poly += [((xmap(t) - px0) * SS, (ymap(mn) - py0) * SS) for t, _, mn, mx in reversed(dta['band'])]
            if len(poly) >= 3:
                ImageDraw.Draw(band).polygon(poly, fill=70)
                img.paste(col, (px0, py0), band.resize((W2 // SS, H2 // SS), Image.BOX))
        mask = Image.new('L', (W2, H2), 0)
        dr = ImageDraw.Draw(mask)
        seg = []
        for t, v in dta.get('points') or ():
            if v is None:
                if len(seg) > 1:
                    dr.line(seg, fill=255, width=int(2.6 * SS), joint='curve')
                seg = []
                continue
            seg.append(((xmap(t) - px0) * SS, (ymap(v) - py0) * SS))
        if seg and not dta.get('band'):
            seg.append(((px1 - px0) * SS if s.get('now') is not None else seg[-1][0], seg[-1][1]))    # läget står kvar till nu
        if len(seg) > 1:
            dr.line(seg, fill=255, width=int(2.6 * SS), joint='curve')
        elif len(seg) == 1:
            dr.ellipse((seg[0][0] - 4, seg[0][1] - 4, seg[0][0] + 4, seg[0][1] + 4), fill=255)
        img.paste(col, (px0, py0), mask.resize((W2 // SS, H2 // SS), Image.BOX))
    # max och min markerade i grafen (en kurva)
    if len(series) == 1 and series[0].get('data'):
        s = series[0]
        hi, lo = extremes(s['data'])
        d = s.get('decimals', 1)
        for ext, col, above in ((hi, MAX_COL, True), (lo, MIN_COL, False)):
            if not ext:
                continue
            x, y = snap(xmap(ext[1])), snap(ymap(ext[0]))
            circle(img, x - 6, y - 6, 12, col)
            circle(img, x - 3, y - 3, 6, T.CARD)
            lab = fmt(ext[0], d, sep)
            tw = text_width(lab, 500, 16)
            lx = min(max(x - tw / 2.0, px0 + 2), px1 - tw - 2)
            ly = y - 12 if above else y + 26
            if above and ly < py0 + 4:
                ly = y + 26
            if not above and ly > py1 + 2:
                ly = y - 12
            _halo_text(img, lx, ly, lab, 500, 16, col)

