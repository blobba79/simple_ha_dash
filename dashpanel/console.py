"""Hindrar att konsolen (fbcon: inloggningstext, markör, skärmsläckare) ritar över panelen.
Konsolen kopplas bort från framebuffern via sysfs; ingenting stoppas eller ändras permanent."""
import glob
import os


def _fbcon_bind_file():
    for d in sorted(glob.glob('/sys/class/vtconsole/vtcon*')):
        try:
            if 'frame buffer' in open(d + '/name').read():
                return d + '/bind'
        except OSError:
            pass
    return None


def release_console():
    """Koppla bort fbcon. Returnerar True om det lyckades."""
    f = _fbcon_bind_file()
    if not f:
        return False
    try:
        with open(f, 'w') as fh:
            fh.write('0')
        return True
    except OSError:
        return False


def restore_console():
    f = _fbcon_bind_file()
    if not f:
        return False
    try:
        with open(f, 'w') as fh:
            fh.write('1')
        return True
    except OSError:
        return False
