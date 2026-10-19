"""Ritytan (en RGB-bild i minnet) och utgångar: framebuffern /dev/fb0 på dash, eller ingenting (PNG vid test).
Panelen ritar bara ändrade rutor: Surface samlar smutsiga rektanglar och skickar dem till utgången."""
import mmap
import os

from PIL import Image

from . import theme as T
from .gfx import H, W


class NullSink(object):
    """Utveckling/test: gör ingenting, men räknar."""

    def __init__(self):
        self.flushes = 0
        self.pixels = 0
        self.last_rects = []

    def write(self, img, rects):
        self.flushes += 1
        self.last_rects = list(rects)
        self.pixels += sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects)

    def close(self):
        pass


class FbSink(object):
    """Skriver rutor rakt in i framebuffern (simplefb, 32 bit, B G R X)."""

    def __init__(self, path='/dev/fb0'):
        base = '/sys/class/graphics/' + os.path.basename(path)
        try:
            self.stride = int(open(base + '/stride').read())
            bpp = int(open(base + '/bits_per_pixel').read())
            vs = open(base + '/virtual_size').read().strip().split(',')
            if bpp != 32 or (int(vs[0]), int(vs[1])) != (W, H):
                raise RuntimeError('oväntad framebuffer: %s bpp, %s' % (bpp, vs))
        except (OSError, ValueError):
            self.stride = W * 4
        self.fd = os.open(path, os.O_RDWR)
        self.mm = mmap.mmap(self.fd, self.stride * H, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)

    def write(self, img, rects):
        mm, stride = self.mm, self.stride
        for (x0, y0, x1, y1) in rects:
            full = (x0 == 0 and x1 == W)
            data = (img if (full and y0 == 0 and y1 == H) else img.crop((x0, y0, x1, y1))).tobytes('raw', 'BGRX')
            w4 = (x1 - x0) * 4
            if full and w4 == stride:
                mm[y0 * stride:y1 * stride] = data
            else:
                off = y0 * stride + x0 * 4
                pos = 0
                for _ in range(y1 - y0):
                    mm[off:off + w4] = data[pos:pos + w4]
                    off += stride
                    pos += w4

    def close(self):
        try:
            self.mm.close()
            os.close(self.fd)
        except Exception:
            pass


def _merge(rects):
    """Slår ihop överlappande rutor; en hel skärm sluger allt."""
    out = []
    for r in rects:
        r = (max(0, r[0]), max(0, r[1]), min(W, r[2]), min(H, r[3]))
        if r[2] <= r[0] or r[3] <= r[1]:
            continue
        if r == (0, 0, W, H):
            return [r]
        out.append(r)
    changed = True
    while changed and len(out) > 1:
        changed = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = out[i], out[j]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    out[i] = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
                    del out[j]
                    changed = True
                    break
            if changed:
                break
    return out


class Surface(object):
    def __init__(self, sink):
        self.img = Image.new('RGB', (W, H), T.BG)
        self.sink = sink
        self._dirty = []

    def mark(self, rect):
        self._dirty.append(rect)

    def mark_all(self):
        self._dirty = [(0, 0, W, H)]

    def flush(self):
        if not self._dirty:
            return 0
        rects = _merge(self._dirty)
        self._dirty = []
        if rects:
            self.sink.write(self.img, rects)
        return len(rects)
