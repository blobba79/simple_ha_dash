#!/usr/bin/env python3
"""Fiktiva tryck i pekskärmens enhet på dash (som evemu-play): panelen läser dem som riktiga tryck, med kalibreringen
och allt. Bra för att prova reglage, släck/väck och Avsluta när ingen sitter vid skärmen.
Skärmkoordinater 1024x600. RÖR INTE SKÄRMEN medan det körs: riktiga fingrar och fiktiva trycker i varandra.

  python3 tools/touch_inject.py screen                  skriver vilken sida som visas (flik, settings, confirm-quit, game ...)
  python3 tools/touch_inject.py tap X Y [hold_s]
  python3 tools/touch_inject.py drag X0 Y0 X1 Y1 [steg] [paus_s]
  python3 tools/touch_inject.py guard-tap SIDA X Y      trycker bara om sidan som visas är SIDA (annars avbryts, utgångskod 2)

Tryck aldrig blint: på flikarna ligger lampor och "Alla lampor" där knapparna på andra sidor sitter. Använd guard-tap
för allt som kan träffa en lampa eller bekräfta Starta om/Stäng av. Några koordinater:
  kugghjulet 984,46 · spelikonen (öppnar spelväljaren) 930,46 · första/andra spelet i spelväljaren 264,192 / 760,192 (tredje/fjärde 264,400 / 760,400) · Uppdatera spel i spelväljaren 204,550 · Uppdatera på inställningssidan 830,118 · Avsluta på inställningssidan 830,346 ·
  Avbryt/bekräfta i frågan 370,488 / 654,488 ·
  tomt område som bara väcker skärmen 5,300 · ljusstyrkereglaget y=449 (x 70..954) · släcktidsreglaget y=532"""
import os
import random
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)

from dashpanel.touch import Calibration, find_touch_device

EV = struct.Struct('@llHHi')
EV_SYN, EV_ABS = 0, 3
SLOT, TRACKING_ID, POS_X, POS_Y = 0x2f, 0x39, 0x35, 0x36

# färger i panelens teman (dashpanel/theme.py) som skiljer sidorna åt
GEAR_BLUE = (3, 169, 244)
GAME_BACK = (28, 28, 28)            # Tillbaka-knappens fyllning (spelväljaren och alla spel har den uppe till vänster)
PAGE_BG = (17, 17, 17)              # sidans bakgrund: på spelsidorna ligger den där kugghjulet sitter på flikarna
CONFIRM_OK_FILL = {'quit': (58, 42, 14), 'reboot': (11, 74, 110), 'poweroff': (58, 26, 26), 'update': (22, 58, 28)}


def _close(a, b, tol):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def classify(img):
    """Vilken sida bilden visar: 'settings', 'confirm-quit', 'confirm-reboot', 'confirm-poweroff', 'confirm-update', 'okand' (kugghjulet är
    markerat men sidan känns inte igen), 'game' (spelväljaren eller ett spel) eller 'flik' (flikarna, dimvyn,
    nedstängningsbilden eller annat). Går på kugghjulets blå kant, QR-rutans vita hörn och bekräftelseknappens fyllning;
    spelsidorna (inget kugghjul) känns igen på Tillbaka-knappen uppe till vänster, som alla har, och på att kugghjulets
    plats är tom bakgrund (på flikarna och i dimvyn sitter kugghjulet där)."""
    gear = _close(img.getpixel((984, 17)), GEAR_BLUE, 40)
    if not gear:
        if img.getpixel((100, 22)) == GAME_BACK and img.getpixel((984, 17)) == PAGE_BG:
            return 'game'
        return 'flik'
    if img.getpixel((40, 112)) == (255, 255, 255):
        return 'settings'
    ok = img.getpixel((654, 470))
    for kind, col in CONFIRM_OK_FILL.items():
        if _close(ok, col, 12):
            return 'confirm-' + kind
    return 'okand'


class Injector(object):
    def __init__(self, touch_json='/etc/dash-panel/touch.json', device=None):
        self.cal = Calibration.load(touch_json)
        self.fd = os.open(device or find_touch_device(), os.O_WRONLY)

    def _raw(self, x, y):
        u = (x - self.cal.ax[1]) / self.cal.ax[0]
        v = (y - self.cal.ay[1]) / self.cal.ay[0]
        return (int(round(v)), int(round(u))) if self.cal.swap else (int(round(u)), int(round(v)))

    def _send(self, *evs):
        t = time.time()
        os.write(self.fd, b''.join(EV.pack(int(t), int((t % 1) * 1e6), a, b, c) for a, b, c in evs))

    def down(self, x, y):
        rx, ry = self._raw(x, y)
        self._send((EV_ABS, SLOT, 0), (EV_ABS, TRACKING_ID, random.randint(100, 30000)),
                   (EV_ABS, POS_X, rx), (EV_ABS, POS_Y, ry), (EV_SYN, 0, 0))

    def move(self, x, y):
        rx, ry = self._raw(x, y)
        self._send((EV_ABS, POS_X, rx), (EV_ABS, POS_Y, ry), (EV_SYN, 0, 0))

    def up(self):
        self._send((EV_ABS, TRACKING_ID, -1), (EV_SYN, 0, 0))

    def tap(self, x, y, hold=0.08):
        self.down(x, y)
        time.sleep(hold)
        self.up()

    def drag(self, x0, y0, x1, y1, steps=10, pause=0.03):
        self.down(x0, y0)
        for i in range(1, steps + 1):
            time.sleep(pause)
            self.move(x0 + (x1 - x0) * i // steps, y0 + (y1 - y0) * i // steps)
        time.sleep(pause)
        self.up()


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd, a = argv[0], argv[1:]
    if cmd == 'screen':
        from fbshot import read_fb
        print(classify(read_fb()))
        return 0
    inj = Injector()
    if cmd == 'tap':
        inj.tap(int(a[0]), int(a[1]), float(a[2]) if len(a) > 2 else 0.08)
    elif cmd == 'drag':
        inj.drag(int(a[0]), int(a[1]), int(a[2]), int(a[3]), int(a[4]) if len(a) > 4 else 10,
                 float(a[5]) if len(a) > 5 else 0.03)
    elif cmd == 'guard-tap':
        from fbshot import read_fb
        now = classify(read_fb())
        if now != a[0]:
            print('avbryter: visar %s, inte %s' % (now, a[0]))
            return 2
        inj.tap(int(a[1]), int(a[2]))
    else:
        print(__doc__)
        return 1
    print('klart', cmd, a)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
