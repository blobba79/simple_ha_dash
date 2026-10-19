"""Pekskärmen (Silead, /dev/input/event2, multitouch typ B): läser rå händelser utan bibliotek,
räknar om med kalibrering till skärmkoordinater (1024x600) och ger down/move/up till ett återanrop."""
import json
import os
import struct

from .gfx import H, W

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = 0x2f, 0x35, 0x36, 0x39
_EV = struct.Struct('@llHHi')


def find_touch_device(default='/dev/input/event2', proc='/proc/bus/input/devices'):
    """Pekskärmens enhet. Event-numret kan skifta mellan uppstarter, så leta efter namnet (silead_ts på dash)."""
    try:
        with open(proc) as f:
            txt = f.read()
    except OSError:
        return default
    for block in txt.split('\n\n'):
        name, handlers = '', ''
        for ln in block.splitlines():
            if ln.startswith('N: Name='):
                name = ln.split('=', 1)[1].strip().strip('"').lower()
            elif ln.startswith('H: Handlers='):
                handlers = ln.split('=', 1)[1]
        if any(k in name for k in ('silead', 'gsl', 'touch')):
            for h in handlers.split():
                if h.startswith('event'):
                    return '/dev/input/' + h
    return default


class Calibration(object):
    """skärm_x = ax[0]*rå_u + ax[1]; skärm_y = ay[0]*rå_v + ay[1]; (u,v) = (rå_x, rå_y) eller bytta (swap)."""

    def __init__(self, swap=False, ax=None, ay=None):
        self.swap = bool(swap)
        self.ax = tuple(ax) if ax else (W / 1272.0, 0.0)
        self.ay = tuple(ay) if ay else (H / 768.0, 0.0)

    def map(self, rx, ry):
        u, v = (ry, rx) if self.swap else (rx, ry)
        x = int(round(self.ax[0] * u + self.ax[1]))
        y = int(round(self.ay[0] * v + self.ay[1]))
        return max(0, min(W - 1, x)), max(0, min(H - 1, y))

    def to_dict(self):
        return {'swap': self.swap, 'ax': list(self.ax), 'ay': list(self.ay)}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get('swap', False), d.get('ax'), d.get('ay'))

    @classmethod
    def load(cls, path):
        try:
            with open(path) as f:
                return cls.from_dict(json.load(f))
        except (OSError, ValueError):
            return cls()

    def save(self, path):
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(self.to_dict(), f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    @classmethod
    def fit(cls, samples):
        """samples: [((rå_x, rå_y), (mål_x, mål_y)), ...]. Ger (kalibrering, största felet i px)."""
        n = float(len(samples))

        def stats(us, ts):
            mu, mt = sum(us) / n, sum(ts) / n
            var = sum((u - mu) ** 2 for u in us)
            cov = sum((u - mu) * (t - mt) for u, t in zip(us, ts))
            return mu, mt, var, cov

        rxs = [s[0][0] for s in samples]
        rys = [s[0][1] for s in samples]
        txs = [s[1][0] for s in samples]
        tys = [s[1][1] for s in samples]
        _, _, vx, cxx = stats(rxs, txs)
        _, _, _, cxy = stats(rxs, tys)
        swap = abs(cxy) > abs(cxx)
        us, vs = (rys, rxs) if swap else (rxs, rys)
        mu, mt, var, cov = stats(us, txs)
        if var <= 0:
            raise ValueError('pekpunkterna ligger för nära varandra i x')
        ax = (cov / var, mt - cov / var * mu)
        mv, mtv, varv, covv = stats(vs, tys)
        if varv <= 0:
            raise ValueError('pekpunkterna ligger för nära varandra i y')
        ay = (covv / varv, mtv - covv / varv * mv)
        cal = cls(swap, ax, ay)
        err = 0.0
        for (rx, ry), (tx, ty) in samples:
            x = cal.ax[0] * (ry if swap else rx) + cal.ax[1]
            y = cal.ay[0] * (rx if swap else ry) + cal.ay[1]
            err = max(err, abs(x - tx), abs(y - ty))
        return cal, err


class TouchReader(object):
    """Ger cb('down'|'move'|'up', x, y) för det första fingret. Ett enda läsanrop när något händer."""

    def __init__(self, loop, path, calib, cb, raw_cb=None):
        self.loop, self.calib, self.cb, self.raw_cb = loop, calib, cb, raw_cb
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self.slots = {}
        self.cur = 0
        self.active = None
        self.last = (0, 0)
        loop.add_reader(self.fd, self._readable)

    def close(self):
        try:
            self.loop.remove_reader(self.fd)
            os.close(self.fd)
        except Exception:
            pass

    def _readable(self):
        try:
            data = os.read(self.fd, _EV.size * 128)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            return
        for off in range(0, len(data) - _EV.size + 1, _EV.size):
            _, _, typ, code, val = _EV.unpack_from(data, off)
            if typ == EV_ABS:
                if code == ABS_MT_SLOT:
                    self.cur = val
                else:
                    s = self.slots.setdefault(self.cur, [-1, 0, 0])
                    if code == ABS_MT_TRACKING_ID:
                        s[0] = val
                    elif code == ABS_MT_POSITION_X:
                        s[1] = val
                    elif code == ABS_MT_POSITION_Y:
                        s[2] = val
            elif typ == EV_SYN and code == 0:
                self._sync()

    def _sync(self):
        if self.active is None:
            for k in sorted(self.slots):
                s = self.slots[k]
                if s[0] >= 0:
                    self.active = k
                    x, y = self._pos(s)
                    self.last = (x, y)
                    self.cb('down', x, y)
                    return
            return
        s = self.slots.get(self.active)
        if s is None or s[0] < 0:
            self.active = None
            self.cb('up', self.last[0], self.last[1])
            return
        x, y = self._pos(s)
        if (x, y) != self.last:
            self.last = (x, y)
            self.cb('move', x, y)

    def _pos(self, s):
        if self.raw_cb:
            self.raw_cb(s[1], s[2])
        return self.calib.map(s[1], s[2])
