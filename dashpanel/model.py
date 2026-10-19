"""Tillstånd och formatering: lagret med Home Assistants lägen, svenska datum och tal, tidszon."""
import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DAYS = ('måndag', 'tisdag', 'onsdag', 'torsdag', 'fredag', 'lördag', 'söndag')
MONTHS = ('januari', 'februari', 'mars', 'april', 'maj', 'juni', 'juli', 'augusti', 'september', 'oktober',
          'november', 'december')


class Store(object):
    """states: entity_id -> {'state': str, 'attributes': dict}.
    status: connecting (första försöket), connected, down. have_full: fullt läge hämtat på den här anslutningen.
    live är sant bara när båda stämmer; annars är värdena okända och visas aldrig som aktuella."""

    def __init__(self):
        self.states = {}
        self.status = 'connecting'
        self.reason = ''                # net, no_token, auth, proto
        self.have_full = False

    @property
    def live(self):
        return self.status == 'connected' and self.have_full


def hhmm(dt):
    return '%02d:%02d' % (dt.hour, dt.minute)


def date_text(dt):
    return '%s %d %s' % (DAYS[dt.weekday()], dt.day, MONTHS[dt.month - 1])


def format_number(raw, decimals=1, sep=','):
    """'21.25' -> '21,3' (avrundar .5 uppåt som Home Assistants eget gränssnitt). None om det inte är ett tal."""
    try:
        d = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    q = Decimal(1).scaleb(-decimals)
    d = d.quantize(q, rounding=ROUND_HALF_UP)
    s = '{:f}'.format(d)
    if s.startswith('-') and d == 0:
        s = s[1:]
    return s.replace('-', '−').replace('.', sep)


def count_text(n):
    return '%d tänd' % n if n == 1 else '%d tända' % n


def dimmable_from_attrs(domain, attrs):
    if domain != 'light':
        return False
    modes = attrs.get('supported_color_modes')
    if modes:
        return any(m not in ('onoff', 'unknown') for m in modes)
    return bool((attrs.get('supported_features') or 0) & 1)


def brightness_pct(attrs):
    """Home Assistants brightness 0-255 -> procent 1-100 (None om okänt)."""
    b = attrs.get('brightness')
    try:
        b = float(b)
    except (TypeError, ValueError):
        return None
    pct = int(b * 100.0 / 255.0 + 0.5)
    if b > 0 and pct < 1:
        pct = 1
    return max(0, min(100, pct))


# ---------------------------------------------------------------- tid
def _last_sunday(year, month):
    d = datetime.date(year, month, 31)
    return d - datetime.timedelta(days=(d.weekday() + 1) % 7)


def _eu_local(utc, std_hours=1):
    """Reserv om tidszonsdatabasen saknas: EU:s sommartid (sista söndagen i mars till sista i oktober, kl 01 UTC)."""
    y = utc.year
    start = datetime.datetime.combine(_last_sunday(y, 3), datetime.time(1))
    end = datetime.datetime.combine(_last_sunday(y, 10), datetime.time(1))
    off = std_hours + (1 if start <= utc < end else 0)
    return utc + datetime.timedelta(hours=off)


def make_clock(tzname):
    """Ger en funktion som returnerar aktuell lokal tid (naiv datetime) i tidszonen tzname."""
    tz = None
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tzname)
    except Exception:
        tz = None

    def now():
        if tz is not None:
            return datetime.datetime.now(tz).replace(tzinfo=None)
        return _eu_local(datetime.datetime.utcnow())
    return now
