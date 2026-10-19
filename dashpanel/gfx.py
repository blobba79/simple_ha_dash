"""Ritprimitiver (Pillow): typsnitt, text, kantutjämnade avrundade rutor, cirklar och ikoner.
Samma kod ritar till PNG (utveckling) och till framebuffern (dash). Koordinater är heltal i pixlar."""
import math
import os

from PIL import Image, ImageDraw, ImageFont

ASSETS = os.environ.get('DASH_ASSETS') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
W, H = 1024, 600

_RESAMPLE_BOX = getattr(getattr(Image, 'Resampling', Image), 'BOX')
_T = getattr(Image, 'Transpose', Image)


def snap(v):
    """Avrunda som Chrome gör med rutkanter: halvt uppåt."""
    return int(math.floor(v + 0.5))


# ---------------------------------------------------------------- typsnitt och text
_FONT_FILES = {300: 'Roboto-Light.ttf', 400: 'Roboto-Regular.ttf', 500: 'Roboto-Medium.ttf'}
_fonts = {}


def font(weight, size):
    key = (weight, size)
    f = _fonts.get(key)
    if f is None:
        f = ImageFont.truetype(os.path.join(ASSETS, 'fonts', _FONT_FILES[weight]), size)
        _fonts[key] = f
    return f


def _ss(size):
    """Översamplingsfaktor: Pillow/FreeType avrundar teckenbredder till hela pixlar när texten hintas.
    Genom att rita i större storlek och skala ned får texten Chromes jämna avstånd."""
    return 4 if size <= 40 else (2 if size <= 100 else 1)


def text_width(s, weight, size):
    ss = _ss(size)
    return font(weight, size * ss).getlength(s) / float(ss)


_GAMMA = [int(round(255 * ((i / 255.0) ** 0.88))) for i in range(256)]
_tcache = {}
_TCACHE_MAX = 400


def _text_mask(s, weight, size, fq):
    key = (s, weight, size, fq)
    hit = _tcache.get(key)
    if hit is not None:
        return hit
    ss = _ss(size)
    f = font(weight, size * ss)
    wpx = f.getlength(s) / float(ss)
    pad = 3
    asc = int(size * 0.95) + 2
    desc = int(size * 0.30) + 2
    w = int(math.ceil(wpx + fq)) + 2 * pad
    h = asc + desc
    big = Image.new('L', (w * ss, h * ss), 0)
    ImageDraw.Draw(big).text(((pad + fq) * ss, asc * ss), s, font=f, fill=255, anchor='ls')
    m = big.resize((w, h), _RESAMPLE_BOX) if ss > 1 else big
    m = m.point(_GAMMA)
    if len(_tcache) >= _TCACHE_MAX:
        _tcache.pop(next(iter(_tcache)))
    hit = (m, -pad, -asc)
    _tcache[key] = hit
    return hit


def text(img, x, baseline, s, weight, size, color, anchor='ls'):
    """Ritar s med vänster/höger kant (anchor ls/rs) vid x och baslinjen på heltalet baseline."""
    if not s:
        return
    if anchor == 'rs':
        x = x - text_width(s, weight, size)
    xi = int(math.floor(x))
    fq = int((x - xi) * 4) / 4.0
    m, ox, oy = _text_mask(s, weight, size, fq)
    img.paste(color, (xi + ox, baseline + oy), m)


def fit(s, weight, size, maxw):
    """Kortar s med … så att den ryms i maxw pixlar."""
    f = font(weight, size)
    if f.getlength(s) <= maxw:
        return s
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if f.getlength(s[:mid].rstrip() + '…') <= maxw:
            lo = mid
        else:
            hi = mid - 1
    return s[:lo].rstrip() + '…'


def wrap(s, weight, size, maxw):
    """Delar s i rader (vid mellanslag) så att varje rad ryms i maxw pixlar. Ett ord som är för långt kortas med …."""
    f = font(weight, size)
    lines, cur = [], ''
    for word in s.split():
        trial = word if not cur else cur + ' ' + word
        if f.getlength(trial) <= maxw:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = word if f.getlength(word) <= maxw else fit(word, weight, size, maxw)
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- former
_corners = {}


def _corner_masks(r):
    """Fyra hörnmasker (vä-upp, hö-upp, vä-ned, hö-ned) för radie r, 8x översampling."""
    m = _corners.get(r)
    if m is None:
        ss = 8
        big = Image.new('L', (r * ss, r * ss), 0)
        ImageDraw.Draw(big).ellipse((0, 0, 2 * r * ss - 1, 2 * r * ss - 1), fill=255)
        tl = big.resize((r, r), _RESAMPLE_BOX)
        m = (tl, tl.transpose(_T.FLIP_LEFT_RIGHT), tl.transpose(_T.FLIP_TOP_BOTTOM), tl.transpose(_T.ROTATE_180))
        _corners[r] = m
    return m


def rbox(img, x0, y0, x1, y1, r, color):
    """Fyller [x0,x1) x [y0,y1) med avrundade hörn (radie r). Fungerar för RGB- och L-bilder."""
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    r = max(0, min(r, w // 2, h // 2))
    d = ImageDraw.Draw(img)
    if r == 0:
        d.rectangle((x0, y0, x1 - 1, y1 - 1), fill=color)
        return
    if w - 2 * r > 0:
        d.rectangle((x0 + r, y0, x1 - r - 1, y1 - 1), fill=color)
    if h - 2 * r > 0:
        d.rectangle((x0, y0 + r, x0 + r - 1, y1 - r - 1), fill=color)
        d.rectangle((x1 - r, y0 + r, x1 - 1, y1 - r - 1), fill=color)
    tl, tr, bl, br = _corner_masks(r)
    img.paste(color, (x0, y0), tl)
    img.paste(color, (x1 - r, y0), tr)
    img.paste(color, (x0, y1 - r), bl)
    img.paste(color, (x1 - r, y1 - r), br)


def bbox(img, x0, y0, x1, y1, r, fill, border, bw):
    """Avrundad ruta med kant (bw px) som i CSS: inre radie = r - bw."""
    rbox(img, x0, y0, x1, y1, r, border)
    rbox(img, x0 + bw, y0 + bw, x1 - bw, y1 - bw, max(0, r - bw), fill)


def circle(img, x, y, d, color):
    rbox(img, x, y, x + d, y + d, d // 2, color)


_masks = {}


def rbox_mask(w, h, r):
    k = (w, h, r)
    m = _masks.get(k)
    if m is None:
        m = Image.new('L', (w, h), 0)
        rbox(m, 0, 0, w, h, r, 255)
        _masks[k] = m
    return m


# ---------------------------------------------------------------- ikoner
_icons = {}


def icon_mask(name, size):
    k = (name, size)
    m = _icons.get(k)
    if m is None:
        m = Image.open(os.path.join(ASSETS, 'icons', '%s_%d.png' % (name, size))).convert('L')
        m.load()
        _icons[k] = m
    return m


def icon(img, name, size, x, y, color):
    img.paste(color, (x, y), icon_mask(name, size))


# ---------------------------------------------------------------- färghjälp
def blend(a, b, t):
    """a*(1-t) + b*t, per kanal, avrundat."""
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))


def hex_rgb(s):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
