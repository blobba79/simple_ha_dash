"""QR-kod som bild av en text (adressen till redigeringssidan). Själva kodningen görs av qrcodegen.py (Project
Nayuki, MIT-licens, medföljer oförändrad), så inget behöver installeras på dash."""
from PIL import Image, ImageDraw

from .qrcodegen import QrCode

QUIET = 4               # tyst zon runt koden, i moduler (kraven för att mobilkameror ska läsa den)
_cache = {}


def qr_mask(text, target=296):
    """Ger (bredd i pixlar, mask) där masken är 255 för mörka moduler. Heltalsskala, tyst zon ingår i bredden."""
    key = (text, target)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
    n = qr.get_size()
    scale = max(3, target // (n + 2 * QUIET))
    size = (n + 2 * QUIET) * scale
    mask = Image.new('L', (size, size), 0)
    d = ImageDraw.Draw(mask)
    for y in range(n):
        for x in range(n):
            if qr.get_module(x, y):
                x0, y0 = (x + QUIET) * scale, (y + QUIET) * scale
                d.rectangle((x0, y0, x0 + scale - 1, y0 + scale - 1), fill=255)
    if len(_cache) > 4:
        _cache.clear()
    _cache[key] = (size, mask)
    return size, mask
