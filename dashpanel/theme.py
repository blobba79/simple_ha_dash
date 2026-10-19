"""Färger och lampfärgsmallar (från designen: design/src/*.dc.html)."""
import colorsys

from .gfx import hex_rgb

BG = hex_rgb('111111')
CARD = hex_rgb('1c1c1c')
CARD_BORDER = hex_rgb('2c2c2c')
TEXT = hex_rgb('e1e1e1')
MUTED = hex_rgb('9b9b9b')
FOOT = hex_rgb('8f8f8f')
BLUE = hex_rgb('03a9f4')
BLUE_L = hex_rgb('4fc3f7')
GREEN = hex_rgb('66bb6a')        # "Uppdatera" (knappen på inställningssidan)
GREEN_D = hex_rgb('163a1c')
GREEN_BORDER = hex_rgb('2f7a36')
BLUE_D = hex_rgb('0b4a6e')
BLUE_BG = hex_rgb('0f2230')
OFF_ICON = hex_rgb('4b79a8')
OFF_CIRCLE = hex_rgb('242c36')
TOG_OFF_BORDER = hex_rgb('6b6b6b')
TOG_OFF_BG = hex_rgb('262626')
TOG_OFF_KNOB = hex_rgb('a0a0a0')
SKELETON = hex_rgb('262626')
BTN_BG = hex_rgb('242424')
WARN = hex_rgb('ffa726')       # "Ingen kontakt"
RED = hex_rgb('ef5350')        # "Stäng av"
RED_D = hex_rgb('3a1a1a')
RED_BORDER = hex_rgb('7a2c2c')
WARN_D = hex_rgb('3a2a0e')       # "Avsluta" (bärnsten)
WARN_BORDER = hex_rgb('8a5d12')
SLIDER_EMPTY = hex_rgb('363636')  # reglagens tomma spår
STALE_TEXT = hex_rgb('6b6b6b')

YELLOW = (255, 193, 7)         # #ffc107
ORANGE = (224, 131, 42)        # #e0832a

# exakta värden ur designen för de två färger som används där
_KNOWN = {
    YELLOW: {'main': YELLOW, 'bg': hex_rgb('2e2812'), 'circle': hex_rgb('43390f'), 'border': hex_rgb('4a3f12')},
    ORANGE: {'main': ORANGE, 'bg': hex_rgb('2e2013'), 'circle': hex_rgb('46301a'), 'border': hex_rgb('4a321a')},
}
_pal_cache = {}


def _hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def lamp_palette(rgb=None):
    """Färgmall för en tänd lampa med färgen rgb (annars gul): huvudfärg, cellbakgrund, kant, cirkel."""
    rgb = tuple(int(v) for v in rgb) if rgb else YELLOW
    p = _pal_cache.get(rgb)
    if p is not None:
        return p
    if rgb in _KNOWN:
        p = _KNOWN[rgb]
    else:
        h, l, s = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
        main = rgb if l >= 0.5 else _hsl(h, s, 0.5)       # läsbar mot mörk bakgrund
        sb = min(1.0, s * 1.3)
        p = {'main': main,
             'bg': _hsl(h, 0.43 * sb, 0.127),
             'circle': _hsl(h, 0.63 * s, 0.17),
             'border': _hsl(h, 0.62 * s, 0.19)}
    _pal_cache[rgb] = p
    return p
