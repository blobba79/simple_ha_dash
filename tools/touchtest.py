#!/usr/bin/env python3
"""Testbild och pekkalibrering för dash: visar en testbild, ber om fyra tryck (ringar), räknar ut
kalibreringen (skala, förskjutning, ev. växlade/inverterade axlar), kontrollerar med fyra hörnkors och
visar sedan en prick där man trycker. Sparar kalibreringen i /etc/dash-panel/touch.json.
Provkörs med: systemd-run --unit=dash-touchtest -p RuntimeMaxSec=420 -p MemoryMax=150M -p Nice=5 ..."""
import asyncio
import json
import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from PIL import ImageDraw

from dashpanel import console, theme as T
from dashpanel.gfx import H, W, circle, text, text_width
from dashpanel.surface import FbSink, NullSink, Surface
from dashpanel.touch import Calibration, TouchReader, find_touch_device

CAL_PATH = os.environ.get('DASH_TOUCH_CAL', '/etc/dash-panel/touch.json')
RESULT_PATH = os.environ.get('DASH_TEST_RESULT', '/tmp/touchtest.json')
TARGETS = [(70, 70), (954, 70), (954, 530), (70, 530)]
CORNERS = [(14, 14), (1009, 14), (1009, 585), (14, 585)]
DOT_SECONDS = float(os.environ.get('DASH_DOT_SECONDS', '90'))


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def ring(img, cx, cy, r, w, color, fill=None):
    circle(img, cx - r, cy - r, 2 * r, color)
    circle(img, cx - r + w, cy - r + w, 2 * (r - w), fill if fill is not None else T.BG)


def base_scene(img):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W - 1, H - 1), fill=T.BG)
    for x in range(0, W, 128):
        d.line((x, 0, x, H), fill=(34, 34, 34))
    for y in range(0, H, 100):
        d.line((0, y, W, y), fill=(34, 34, 34))
    d.rectangle((0, 0, W - 1, H - 1), outline=T.BLUE, width=2)
    # färgfält: kontrollerar röd/grön/blå-ordningen
    bars = [((255, 0, 0), 'röd'), ((0, 255, 0), 'grön'), ((0, 0, 255), 'blå'), ((255, 255, 255), 'vit'), ((128, 128, 128), 'grå')]
    x0 = 262
    for i, (c, name) in enumerate(bars):
        d.rectangle((x0 + i * 100, 470, x0 + i * 100 + 94, 500), fill=c)
        w = text_width(name, 400, 16)
        text(img, x0 + i * 100 + 47 - w / 2.0, 522, name, 400, 16, T.MUTED)
    t = 'dash-panel: skärm- och pektest'
    text(img, W / 2.0 - text_width(t, 500, 30) / 2.0, 150, t, 500, 30, T.TEXT)


def draw_target(img, i, active, done):
    cx, cy = TARGETS[i]
    if done:
        ring(img, cx, cy, 36, 3, (60, 120, 60))
    elif active:
        ring(img, cx, cy, 36, 3, T.BLUE_L, fill=T.BLUE_D)
    else:
        ring(img, cx, cy, 36, 3, (70, 70, 70))
    s = str(i + 1)
    text(img, cx - text_width(s, 500, 34) / 2.0, cy + 12, s, 500, 34, T.TEXT if not done else (120, 200, 120))


def draw_cross(img, i, active, done):
    cx, cy = CORNERS[i]
    d = ImageDraw.Draw(img)
    col = (120, 200, 120) if done else (T.WARN if active else (90, 90, 90))
    d.line((cx - 12, cy, cx + 12, cy), fill=col, width=3)
    d.line((cx, cy - 12, cx, cy + 12), fill=col, width=3)


def centered(img, y, s, weight, size, color):
    text(img, W / 2.0 - text_width(s, weight, size) / 2.0, y, s, weight, size, color)


class Test(object):
    def __init__(self, loop, surface, touch_path):
        self.loop, self.s = loop, surface
        self.phase = 'cal'          # cal -> verify -> dot
        self.idx = 0
        self.samples = []
        self.raws = []
        self.down_t = 0.0
        self.cal = Calibration()
        self.result = {'start': time.time(), 'raw_targets': [], 'verify': [], 'taps': []}
        self.dot_base = None
        self.dot_rect = None
        self.dot_deadline = None
        self.done = asyncio.Event()
        self.reader = TouchReader(loop, touch_path, self.cal, self.on_touch, self.on_raw)
        self.render_prompt()

    # ------------------------------------------------------------ ritning
    def render_prompt(self):
        img = self.s.img
        base_scene(img)
        msg = {'cal': ('Tryck mitt i ring %d' % (self.idx + 1), 'Ring 1 till 4 i ordning, ett tryck på varje.'),
               'verify': ('Tryck på korset i hörnet (%d av 4)' % (self.idx + 1), 'Kontrollerar kalibreringen.'),
               'dot': ('Klart. Rör skärmen.', 'Pricken visar var du trycker.')}[self.phase]
        centered(img, 250, msg[0], 500, 40, T.TEXT)
        centered(img, 296, msg[1], 400, 22, T.MUTED)
        if self.phase == 'cal':
            for i in range(4):
                draw_target(img, i, i == self.idx, i < self.idx)
        else:
            for i in range(4):
                draw_target(img, i, False, True)
        if self.phase == 'verify':
            for i in range(4):
                draw_cross(img, i, i == self.idx, i < self.idx)
        elif self.phase == 'dot':
            for i in range(4):
                draw_cross(img, i, False, True)
        self.s.mark_all()
        self.s.flush()
        self.dot_base = img.copy() if self.phase == 'dot' else None

    def draw_dot(self, x, y, info=None):
        img = self.s.img
        if self.dot_rect:
            r = self.dot_rect
            img.paste(self.dot_base.crop(r), (r[0], r[1]))
            self.s.mark(r)
            self.dot_rect = None
        if x is not None:
            circle(img, x - 18, y - 18, 36, T.BLUE_L)
            circle(img, x - 6, y - 6, 12, T.BG)
            self.dot_rect = (max(0, x - 20), max(0, y - 20), min(W, x + 21), min(H, y + 21))
            self.s.mark(self.dot_rect)
        if info is not None:
            r = (212, 340, 812, 400)
            img.paste(self.dot_base.crop(r), (r[0], r[1]))
            centered(img, 380, info, 400, 24, T.TEXT)
            self.s.mark(r)
        self.s.flush()

    # ------------------------------------------------------------ pek
    def on_raw(self, rx, ry):
        self.raws.append((rx, ry))

    def on_touch(self, kind, x, y):
        if kind == 'down':
            self.raws = []
            self.down_t = time.time()
            if self.phase == 'dot':
                self.draw_dot(x, y, 'x=%d y=%d  (rå %d, %d)' % (x, y, self.raws[-1][0] if self.raws else -1, self.raws[-1][1] if self.raws else -1))
            return
        if self.phase == 'dot':
            if kind == 'move':
                rx, ry = self.raws[-1] if self.raws else (-1, -1)
                self.draw_dot(x, y, 'x=%d y=%d  (rå %d, %d)' % (x, y, rx, ry))
            elif kind == 'up':
                self.result['taps'].append([x, y])
                log('tryck (kalibrerat)', x, y)
            return
        if kind != 'up':
            return
        if len(self.raws) < 2 or time.time() - self.down_t < 0.05:
            log('för kort tryck, ignorerar', len(self.raws))
            return
        xs = sorted(r[0] for r in self.raws)
        ys = sorted(r[1] for r in self.raws)
        raw = (xs[len(xs) // 2], ys[len(ys) // 2])
        if self.phase == 'cal':
            self.samples.append((raw, TARGETS[self.idx]))
            self.result['raw_targets'].append([raw[0], raw[1], TARGETS[self.idx][0], TARGETS[self.idx][1], len(self.raws)])
            log('mål', self.idx + 1, 'rå', raw, 'prov', len(self.raws), 'min/max x', xs[0], xs[-1], 'y', ys[0], ys[-1])
            self.idx += 1
            if self.idx >= 4:
                self.finish_cal()
            else:
                self.render_prompt()
        elif self.phase == 'verify':
            mx, my = self.cal.map(*raw)
            tx, ty = CORNERS[self.idx]
            self.result['verify'].append([raw[0], raw[1], mx, my, tx, ty])
            log('hörn', self.idx + 1, 'rå', raw, 'ger', (mx, my), 'mål', (tx, ty), 'fel', (mx - tx, my - ty))
            self.idx += 1
            if self.idx >= 4:
                self.phase = 'dot'
                self.dot_deadline = time.time() + DOT_SECONDS
                self.render_prompt()
                self.loop.call_later(DOT_SECONDS, self.done.set)
                self.save_result()
            else:
                self.render_prompt()

    def finish_cal(self):
        try:
            cal, err = Calibration.fit(self.samples)
        except ValueError as e:
            log('kalibreringen misslyckades:', e)
            self.restart('Misslyckades, försök igen')
            return
        log('kalibrering', cal.to_dict(), 'största fel', round(err, 1), 'px')
        self.result['cal'] = cal.to_dict()
        self.result['fit_err'] = err
        if err > 60:
            self.restart('För stort fel (%d px), försök igen' % err)
            return
        self.cal = cal
        self.reader.calib = cal
        try:
            os.makedirs(os.path.dirname(CAL_PATH), exist_ok=True)
            cal.save(CAL_PATH)
            log('sparade', CAL_PATH)
        except OSError as e:
            log('kunde inte spara kalibreringen:', e)
        self.phase = 'verify'
        self.idx = 0
        self.render_prompt()

    def restart(self, why):
        self.samples = []
        self.idx = 0
        self.phase = 'cal'
        self.render_prompt()
        centered(self.s.img, 340, why, 500, 24, T.WARN)
        self.s.mark_all()
        self.s.flush()

    def save_result(self):
        try:
            with open(RESULT_PATH, 'w') as f:
                json.dump(self.result, f, indent=1)
        except OSError:
            pass


async def run():
    loop = asyncio.get_running_loop()
    fb = os.environ.get('DASH_FB', '/dev/fb0')
    sink = NullSink() if fb == 'none' else FbSink(fb)
    if fb != 'none':
        log('konsol bortkopplad:', console.release_console())
    surface = Surface(sink)
    test = Test(loop, surface, os.environ.get('DASH_INPUT') or find_touch_device())
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, test.done.set)     # avsluta snabbt och lämna tillbaka konsolen
    log('testbild visas, väntar på tryck')
    try:
        await test.done.wait()
    finally:
        test.save_result()
        if fb != 'none':
            log('konsol tillbaka:', console.restore_console())
    log('klar')


if __name__ == '__main__':
    asyncio.run(run())
