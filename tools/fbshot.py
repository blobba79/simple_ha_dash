#!/usr/bin/env python3
"""Skärmbild av det panelen visar just nu: läser framebuffern (1024x600, BGRX) och sparar en PNG.
  python3 tools/fbshot.py /tmp/skarm.png          (kör på dash; Pillow finns där)"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))

from PIL import Image


def read_fb(path='/dev/fb0', w=1024, h=600):
    try:
        stride = int(open('/sys/class/graphics/%s/stride' % os.path.basename(path)).read())
    except (OSError, ValueError):
        stride = w * 4
    with open(path, 'rb') as f:
        data = f.read(stride * h)
    return Image.frombuffer('RGBA', (w, h), data, 'raw', 'BGRA', stride, 1).convert('RGB')


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/skarm.png'
    read_fb().save(out)
    print('sparad', out)
