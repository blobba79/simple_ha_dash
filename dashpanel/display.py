"""Skärmens bakgrundsbelysning och skärminställningar: ljusstyrka och tid tills skärmen släcks.

Bakgrundsbelysningen styrs via sysfs (/sys/class/backlight/<enhet>/brightness, 0..max_brightness; 0 = släckt).
Inställningarna sparas atomiskt i /var/lib/dash-panel/settings.json och gäller från nästa uppstart.
Allt här är försiktigt: finns ingen styrbar bakgrundsbelysning, eller går det inte att skriva, ändras ingenting
och panelen går vidare som vanligt."""
import glob
import json
import math
import os

BACKLIGHT_ROOT = '/sys/class/backlight'
DEFAULT_SETTINGS = '/var/lib/dash-panel/settings.json'
BRIGHT_MIN, BRIGHT_MAX, BRIGHT_STEP = 10, 100, 10           # procent, i tiosteg
OFF_MIN, OFF_MAX, OFF_STEP, OFF_DEFAULT = 5, 120, 5, 60     # sekunder, i femsteg


def _snap(v, lo, hi, step, default):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return default
    return int(max(lo, min(hi, math.floor(v / float(step) + 0.5) * step)))


def snap_brightness(v, default=BRIGHT_MAX):
    return _snap(v, BRIGHT_MIN, BRIGHT_MAX, BRIGHT_STEP, default)


def snap_off(v, default=OFF_DEFAULT):
    return _snap(v, OFF_MIN, OFF_MAX, OFF_STEP, default)


def find_backlight(root=BACKLIGHT_ROOT):
    """Första bakgrundsbelysningen som går att styra (har brightness och max_brightness), annars None."""
    for d in sorted(glob.glob(os.path.join(root, '*'))):
        if os.path.isfile(os.path.join(d, 'brightness')) and os.path.isfile(os.path.join(d, 'max_brightness')):
            return d
    return None


def _read(path):
    with open(path, encoding='ascii') as f:
        return f.read().strip()


class Backlight(object):
    """En bakgrundsbelysning i sysfs. Utan styrbar enhet gör alla anrop ingenting (available är False)."""

    def __init__(self, path=None, log=None):
        self.log = log or (lambda *a: None)
        self.path = path
        self.max = 0
        self._warned = False
        if path:
            try:
                self.max = int(_read(os.path.join(path, 'max_brightness')))
            except (OSError, ValueError):
                self.max = 0
        if self.max <= 0:
            self.path = None

    @property
    def available(self):
        return self.path is not None

    def get(self):
        if not self.available:
            return None
        try:
            return max(0, min(self.max, int(_read(os.path.join(self.path, 'brightness')))))
        except (OSError, ValueError):
            return None

    def set(self, level):
        """Sätter nivån 0..max. True om det lyckades."""
        if not self.available:
            return False
        level = max(0, min(self.max, int(level)))
        try:
            with open(os.path.join(self.path, 'brightness'), 'w') as f:
                f.write(str(level))
            return True
        except OSError as e:
            if not self._warned:
                self._warned = True
                self.log('kunde inte ställa in bakgrundsbelysningen (%s): %s' % (self.path, e))
            return False

    def level_for(self, pct):
        """Nivån som motsvarar pct procent. Aldrig 0 (0 är släckt)."""
        return max(1, min(self.max, int(math.floor(pct * self.max / 100.0 + 0.5))))

    def pct_for(self, level):
        return int(math.floor(level * 100.0 / self.max + 0.5)) if self.max else 100


class Display(object):
    """Skärmens inställningar (ljusstyrka 10-100 %, tid tills skärmen släcks 5-120 s) och själva av/på."""

    def __init__(self, backlight=None, path=None, log=None):
        self.log = log or (lambda *a: None)
        self.bl = backlight if backlight is not None else Backlight(find_backlight(), self.log)
        self.path = path if path not in (None, '', 'none') else None
        self.is_off = False
        self._dirty = False
        self._warned = False
        self.brightness, self.off_after = self._load()

    # ------------------------------------------------------------ läsa och spara
    def _load(self):
        d = {}
        if self.path:
            try:
                with open(self.path, encoding='utf-8') as f:
                    d = json.load(f)
            except (OSError, ValueError):
                d = {}
        if not isinstance(d, dict):
            d = {}
        b = d.get('brightness')
        if isinstance(b, (int, float)) and not isinstance(b, bool):
            bright = snap_brightness(b)
        else:
            cur = self.bl.get()             # första gången: behåll ljusstyrkan skärmen har nu
            bright = snap_brightness(self.bl.pct_for(cur)) if cur else BRIGHT_MAX
        off = snap_off(d.get('screen_off_s'))
        return bright, off

    def save(self):
        """Sparar inställningarna om något ändrats sedan sist. True om det är sparat."""
        if not self.path or not self._dirty:
            return True
        try:
            dirn = os.path.dirname(self.path)
            if dirn:
                os.makedirs(dirn, exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump({'brightness': self.brightness, 'screen_off_s': self.off_after}, f, indent=1)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            self._dirty = False
            return True
        except OSError as e:
            if not self._warned:
                self._warned = True
                self.log('kunde inte spara skärminställningarna (%s): %s' % (self.path, e))
            return False

    # ------------------------------------------------------------ inställningar
    @property
    def can_blank(self):
        """Går skärmen att släcka? Utan styrbar bakgrundsbelysning görs aldrig något försök."""
        return self.bl.available

    def set_brightness(self, pct):
        v = snap_brightness(pct)
        if v == self.brightness:
            return
        self.brightness = v
        self._dirty = True
        if not self.is_off:
            self.bl.set(self.bl.level_for(v))       # syns direkt medan reglaget dras

    def set_off_after(self, seconds):
        v = snap_off(seconds)
        if v != self.off_after:
            self.off_after = v
            self._dirty = True

    # ------------------------------------------------------------ av och på
    def screen_on(self):
        """Tänder skärmen med den inställda ljusstyrkan (gör också att sparad ljusstyrka tas i bruk vid start)."""
        self.is_off = False
        if self.bl.available:
            self.bl.set(self.bl.level_for(self.brightness))

    def screen_off(self):
        self.is_off = True
        self.bl.set(0)

    def restore(self):
        """Vid avslut: lämna skärmen tänd (konsolen ska synas) och spara."""
        self.screen_on()
        self.save()

    def describe(self):
        if not self.bl.available:
            return 'ingen styrbar bakgrundsbelysning'
        return 'bakgrundsbelysning %s (0-%d), ljusstyrka %d %%, släcks efter %d s' % (
            self.bl.path, self.bl.max, self.brightness, self.off_after)
