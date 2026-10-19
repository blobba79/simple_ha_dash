"""Färg i dimvyn: färgtemperatur (vitt, varmt till kallt) och färg (nyans och mättnad) för lampor som kan det.

Dimvyns kort får tre lägen överst, Ljusstyrka, Vitt och Färg (bara de lampan klarar). Ljusstyrkereglaget till höger
finns kvar i alla lägen. Vitt: en färgad list från varmt till kallt (tryck eller dra) och tre snabbval. Färg: ett fält
med nyans åt sidan och mättnad uppifrån (vitt längst ned), och åtta färdiga färger.

Home Assistant: light.turn_on med color_temp_kelvin respektive hs_color [nyans 0-360, mättnad 0-100]."""
import colorsys
import math

from PIL import Image

from . import theme as T
from .gfx import bbox, blend, circle, rbox_mask, snap, text, text_width

COLOR_MODES = ('hs', 'xy', 'rgb', 'rgbw', 'rgbww')
MODE_LABELS = (('bright', 'Ljusstyrka'), ('ct', 'Vitt'), ('color', 'Färg'))

X0, X1 = 49, 719
MODES_Y = (204, 252)
VALUE2_RECT = (40, 256, 728, 447)        # ljusstyrkans stora siffra när lägesraden visas
CONTENT_RECT = (40, 256, 728, 540)       # vitt- och färgpanelen
CT_BAR = (X0, 350, X1, 414)
HS_FIELD = (X0, 268, X1, 428)
PRESET_Y = (447, 527)
HS_PRESETS = ((0, 100, 'Röd'), (28, 100, 'Orange'), (52, 100, 'Gul'), (120, 100, 'Grön'), (178, 100, 'Turkos'),
              (225, 100, 'Blå'), (275, 100, 'Lila'), (320, 70, 'Rosa'))
CT_PRESETS = ((2700, 'Varmt'), (4000, 'Neutralt'), (6000, 'Kallt'))


# ---------------------------------------------------------------- vad lampan kan
def caps(attrs):
    """{'ct': (min_kelvin, max_kelvin) eller None, 'color': bool} ur supported_color_modes."""
    attrs = attrs or {}
    modes = attrs.get('supported_color_modes') or ()
    ct = None
    if 'color_temp' in modes:
        lo, hi = attrs.get('min_color_temp_kelvin'), attrs.get('max_color_temp_kelvin')
        if not (lo and hi):
            mx, mn = attrs.get('max_mireds'), attrs.get('min_mireds')        # äldre Home Assistant
            if mx and mn:
                lo, hi = 1e6 / float(mx), 1e6 / float(mn)
        try:
            lo, hi = int(round(float(lo or 2000))), int(round(float(hi or 6500)))
        except (TypeError, ValueError):
            lo, hi = 2000, 6500
        if hi - lo >= 100:
            ct = (lo, hi)
    return {'ct': ct, 'color': any(m in modes for m in COLOR_MODES)}


def modes_for(c):
    out = ['bright']
    if c['ct']:
        out.append('ct')
    if c['color']:
        out.append('color')
    return out


def current_ct(attrs):
    attrs = attrs or {}
    k = attrs.get('color_temp_kelvin')
    if not k and attrs.get('color_temp'):
        try:
            k = 1e6 / float(attrs['color_temp'])
        except (TypeError, ValueError, ZeroDivisionError):
            k = None
    try:
        return int(round(float(k))) if k else None
    except (TypeError, ValueError):
        return None


def current_hs(attrs):
    hs = (attrs or {}).get('hs_color')
    if isinstance(hs, (list, tuple)) and len(hs) == 2:
        try:
            return float(hs[0]), float(hs[1])
        except (TypeError, ValueError):
            return None
    return None


def in_color_mode(attrs):
    return (attrs or {}).get('color_mode') in COLOR_MODES


# ---------------------------------------------------------------- färgräkning
def kelvin_rgb(k):
    """Ungefärlig färg för en färgtemperatur (Tanner Hellands formel)."""
    t = max(1000.0, min(40000.0, float(k))) / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255.0
    return tuple(int(max(0, min(255, v))) for v in (r, g, b))


def hs_rgb(h, s):
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, max(0.0, min(100.0, s)) / 100.0, 1.0)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def ct_label(k):
    if k < 3200:
        return 'Varmvitt'
    if k < 4500:
        return 'Neutralvitt'
    return 'Kallvitt'


# ---------------------------------------------------------------- tryck
def mode_rects(modes):
    n = len(modes)
    gap = 10
    w = (X1 - X0 - gap * (n - 1)) / float(n)
    out = []
    for i, m in enumerate(modes):
        x = X0 + i * (w + gap)
        out.append((m, (snap(x), MODES_Y[0], snap(x + w), MODES_Y[1])))
    return out


def preset_rects(items):
    n = len(items)
    gap = 10
    w = (X1 - X0 - gap * (n - 1)) / float(n)
    return [(it, (snap(X0 + i * (w + gap)), PRESET_Y[0], snap(X0 + i * (w + gap) + w), PRESET_Y[1])) for i, it in enumerate(items)]


def ct_presets(rng):
    lo, hi = rng
    out, seen = [], set()
    for k, label in CT_PRESETS:
        kk = max(lo, min(hi, k))
        if kk not in seen:
            seen.add(kk)
            out.append((kk, label))
    return out


def ct_from_x(x, rng):
    lo, hi = rng
    f = (x - CT_BAR[0]) / float(CT_BAR[2] - CT_BAR[0])
    f = max(0.0, min(1.0, f))
    return int(round((lo + f * (hi - lo)) / 50.0) * 50)


def hs_from_xy(x, y):
    fx = max(0.0, min(1.0, (x - HS_FIELD[0]) / float(HS_FIELD[2] - HS_FIELD[0])))
    fy = max(0.0, min(1.0, (y - HS_FIELD[1]) / float(HS_FIELD[3] - HS_FIELD[1])))
    return round(fx * 359.0, 1), round((1.0 - fy) * 100.0, 1)


# ---------------------------------------------------------------- ritning
def draw_modes(img, modes, active, enabled=True):
    for m, r in mode_rects(modes):
        on = m == active
        bbox(img, *r, 14, T.BLUE_D if on else T.BTN_BG, T.BLUE if on else T.CARD_BORDER, 1)
        label = dict(MODE_LABELS)[m]
        col = T.TEXT if on else (T.MUTED if enabled else (96, 96, 96))
        tw = text_width(label, 500, 19)
        text(img, (r[0] + r[2]) / 2.0 - tw / 2.0, r[1] + 31, label, 500, 19, col)


def draw_bright_value(img, value_text, dim=False):
    """Ljusstyrkans siffra när lägesraden tar platsen för rubriken "Ljusstyrka"."""
    x0, y0, x1, y1 = VALUE2_RECT
    img.paste(T.CARD, (x0, y0, x1, y1))
    col = (96, 96, 96) if dim else T.TEXT
    text(img, 49, 400, value_text, 300, 120, col)
    text(img, 49 + text_width(value_text, 300, 120) + 12, 400, '%', 300, 48, (96, 96, 96) if dim else T.MUTED)


_cache = {}


def _gradient_bar(rng):
    key = ('ct', rng)
    im = _cache.get(key)
    if im is None:
        w, h = CT_BAR[2] - CT_BAR[0], CT_BAR[3] - CT_BAR[1]
        row = Image.new('RGB', (w, 1))
        lo, hi = rng
        row.putdata([kelvin_rgb(lo + (hi - lo) * i / float(w - 1)) for i in range(w)])
        im = row.resize((w, h))
        _cache[key] = im
    return im


def _hs_field():
    im = _cache.get('hs')
    if im is None:
        w, h = HS_FIELD[2] - HS_FIELD[0], HS_FIELD[3] - HS_FIELD[1]
        row = Image.new('RGB', (w, 1))
        row.putdata([hs_rgb(360.0 * i / (w - 1), 100) for i in range(w)])
        hue = row.resize((w, h))
        col = Image.new('L', (1, h))
        col.putdata([int(round(255 * (i / float(h - 1)) ** 1.6)) for i in range(h)])     # vitt nedåt
        im = Image.composite(Image.new('RGB', (w, h), (255, 255, 255)), hue, col.resize((w, h)))
        _cache['hs'] = im
    return im


def _knob(img, x, y, fill, enabled=True):
    circle(img, x - 15, y - 15, 30, (17, 17, 17))
    circle(img, x - 12, y - 12, 24, (255, 255, 255) if enabled else (120, 120, 120))
    circle(img, x - 8, y - 8, 16, fill)


def _preset_button(img, r, swatch, label, pressed, enabled, selected=False):
    fill = T.BTN_BG
    if pressed:
        fill = blend(fill, (255, 255, 255), 0.09)
    bbox(img, *r, 18, fill, T.BLUE if selected else T.CARD_BORDER, 2 if selected else 1)
    cx = (r[0] + r[2]) // 2
    if label:
        circle(img, r[0] + 18, r[1] + 26, 28, swatch if enabled else (70, 70, 70))
        text(img, r[0] + 56, r[1] + 47, label, 500, 18, T.TEXT if enabled else (96, 96, 96))
    else:
        circle(img, cx - 20, r[1] + 20, 40, swatch if enabled else (70, 70, 70))


def draw_ct(img, k, rng, enabled=True, pressed=None):
    x0, y0, x1, y1 = CONTENT_RECT
    img.paste(T.CARD, (x0, y0, x1, y1))
    if k is not None:
        lab = '%d K' % k
        text(img, 49, 326, lab, 300, 56, T.TEXT if enabled else (96, 96, 96))
        text(img, 49 + text_width(lab, 300, 56) + 16, 326, ct_label(k), 400, 22, T.MUTED)
    else:
        text(img, 49, 326, 'Färg just nu', 400, 22, T.MUTED)
    bx0, by0, bx1, by1 = CT_BAR
    bar = _gradient_bar(rng)
    if not enabled:
        bar = Image.blend(bar, Image.new('RGB', bar.size, T.CARD), 0.7)
    img.paste(bar, (bx0, by0), rbox_mask(bx1 - bx0, by1 - by0, 18))
    text(img, bx0, by1 + 22, 'Varmt', 400, 15, T.MUTED)
    tw = text_width('Kallt', 400, 15)
    text(img, bx1 - tw, by1 + 22, 'Kallt', 400, 15, T.MUTED)
    if k is not None:
        lo, hi = rng
        f = max(0.0, min(1.0, (k - lo) / float(hi - lo)))
        _knob(img, snap(bx0 + f * (bx1 - bx0)), (by0 + by1) // 2, kelvin_rgb(k), enabled)
    for (kk, label), r in preset_rects(ct_presets(rng)):
        _preset_button(img, r, kelvin_rgb(kk), label, pressed == kk, enabled, selected=(k is not None and abs(k - kk) < 60))


def draw_hs(img, hs, enabled=True, pressed=None):
    x0, y0, x1, y1 = CONTENT_RECT
    img.paste(T.CARD, (x0, y0, x1, y1))
    fx0, fy0, fx1, fy1 = HS_FIELD
    field = _hs_field()
    if not enabled:
        field = Image.blend(field, Image.new('RGB', field.size, T.CARD), 0.7)
    img.paste(field, (fx0, fy0), rbox_mask(fx1 - fx0, fy1 - fy0, 18))
    if hs is not None:
        h, s = hs
        kx = snap(fx0 + (h % 360) / 359.0 * (fx1 - fx0))
        ky = snap(fy0 + (1.0 - max(0.0, min(100.0, s)) / 100.0) * (fy1 - fy0))
        _knob(img, max(fx0 + 4, min(fx1 - 4, kx)), max(fy0 + 4, min(fy1 - 4, ky)), hs_rgb(h, s), enabled)
    for (it, r) in preset_rects(HS_PRESETS):
        h, s, _ = it
        sel = hs is not None and abs(((hs[0] - h + 180) % 360) - 180) < 6 and abs(hs[1] - s) < 8
        _preset_button(img, r, hs_rgb(h, s), None, pressed == (h, s), enabled, selected=sel)
