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


def make_local(tzname):
    """Ger en funktion som gör om en Unix-tid (sekunder) till lokal tid (naiv datetime) i tidszonen tzname."""
    tz = None
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tzname)
    except Exception:
        tz = None

    def local(ts):
        if tz is not None:
            return datetime.datetime.fromtimestamp(ts, tz).replace(tzinfo=None)
        return _eu_local(datetime.datetime.utcfromtimestamp(ts))
    return local


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


# ---------------------------------------------------------------- fler sorters enheter (knappar och värden)
LAMP_DOMAINS = ('light', 'switch')
ACTION_DOMAINS = ('scene', 'script', 'button', 'input_button')
ACTION_SERVICE = {'scene': 'turn_on', 'script': 'turn_on', 'button': 'press', 'input_button': 'press'}
# ikon tänd/släckt per domän (Material Design Icons, förrenderade i assets/icons)
BUTTON_ICONS = {'light': ('Lightbulb', 'LightbulbOff'), 'switch': ('Lightbulb', 'LightbulbOff'),
                'fan': ('Fan', 'FanOff'), 'input_boolean': ('ToggleSwitch', 'ToggleSwitchOff'),
                'automation': ('Robot', 'RobotOff'), 'scene': ('Palette', 'Palette'),
                'script': ('ScriptTextPlay', 'ScriptText'), 'button': ('GestureTapButton', 'GestureTapButton'),
                'input_button': ('GestureTapButton', 'GestureTapButton'), 'media_player': ('Speaker', 'SpeakerOff'),
                'climate': ('Thermostat', 'Thermostat'), 'humidifier': ('AirHumidifier', 'AirHumidifierOff')}
ACTION_LABEL = {'scene': 'Scen', 'script': 'Skript', 'button': 'Knapp', 'input_button': 'Knapp'}
ACTION_DONE = {'scene': 'Aktiverad', 'script': 'Startat', 'button': 'Tryckt', 'input_button': 'Tryckt'}


def domain(eid):
    return (eid or '').split('.', 1)[0]


def onoff(eid, raw):
    """Läget som 'on'/'off' för knappar (None om okänt). Mediaspelare och klimat har fler lägen än på/av."""
    if raw in (None, '', 'unavailable', 'unknown'):
        return None
    d = domain(eid)
    if d == 'media_player':
        return 'off' if raw in ('off', 'standby') else 'on'
    if d == 'climate':
        return 'off' if raw == 'off' else 'on'
    return raw if raw in ('on', 'off') else None


def button_kind(eid):
    """'lamp' (lampa/strömbrytare: räknas i "3 tända" och "Alla lampor"), 'toggle' (annat på/av) eller 'action'."""
    d = domain(eid)
    if d in LAMP_DOMAINS:
        return 'lamp'
    if d in ACTION_DOMAINS:
        return 'action'
    return 'toggle'


# binära sensorer: (på, av) efter device_class, som Home Assistant visar dem på svenska
_BIN_TEXT = {
    'door': ('Öppen', 'Stängd'), 'garage_door': ('Öppen', 'Stängd'), 'window': ('Öppet', 'Stängt'),
    'opening': ('Öppen', 'Stängd'), 'motion': ('Rörelse', 'Ingen rörelse'), 'occupancy': ('Upptaget', 'Ledigt'),
    'presence': ('Hemma', 'Borta'), 'moisture': ('Fukt', 'Torrt'), 'battery': ('Låg', 'Normal'),
    'connectivity': ('Ansluten', 'Frånkopplad'), 'problem': ('Problem', 'OK'), 'lock': ('Olåst', 'Låst'),
    'smoke': ('Rök', 'Ingen rök'), 'gas': ('Gas', 'Ingen gas'), 'light': ('Ljust', 'Mörkt'),
    'running': ('Igång', 'Stannad'), 'heat': ('Varm', 'Normal'), 'cold': ('Kall', 'Normal'),
    'vibration': ('Vibration', 'Stilla'), 'plug': ('Inkopplad', 'Urkopplad'), 'power': ('På', 'Av'),
    'safety': ('Osäkert', 'Säkert'), 'tamper': ('Manipulerad', 'OK'), 'update': ('Uppdatering', 'Senaste'),
}


_STATE_TEXT = {
    'cover': {'open': 'Öppen', 'closed': 'Stängd', 'opening': 'Öppnas', 'closing': 'Stängs'},
    'lock': {'locked': 'Låst', 'unlocked': 'Olåst', 'locking': 'Låser', 'unlocking': 'Låser upp', 'jammed': 'Fastnat',
             'open': 'Öppen', 'opening': 'Öppnas'},
    'media_player': {'off': 'Av', 'on': 'På', 'playing': 'Spelar', 'paused': 'Pausad', 'idle': 'Inaktiv',
                     'standby': 'Vila', 'buffering': 'Buffrar'},
    'person': {'home': 'Hemma', 'not_home': 'Borta'}, 'device_tracker': {'home': 'Hemma', 'not_home': 'Borta'},
    'sun': {'above_horizon': 'Uppe', 'below_horizon': 'Nere'},
    'update': {'on': 'Uppdatering finns', 'off': 'Senaste'},
    'timer': {'idle': 'Inaktiv', 'active': 'Igång', 'paused': 'Pausad'},
    'climate': {'off': 'Av', 'heat': 'Värme', 'cool': 'Kyla', 'auto': 'Auto', 'heat_cool': 'Värme och kyla',
                'dry': 'Avfuktning', 'fan_only': 'Fläkt'},
    'weather': {'sunny': 'Soligt', 'clear-night': 'Klart', 'cloudy': 'Molnigt', 'partlycloudy': 'Halvklart',
                'rainy': 'Regn', 'pouring': 'Skyfall', 'snowy': 'Snö', 'snowy-rainy': 'Snöblandat regn', 'fog': 'Dimma',
                'hail': 'Hagel', 'lightning': 'Åska', 'lightning-rainy': 'Åska och regn', 'windy': 'Blåsigt',
                'windy-variant': 'Blåsigt', 'exceptional': 'Extremt väder'},
}


def value_text(eid, raw, attrs):
    """Text för ett värde som inte är ett tal (binär sensor, val, text, datum). None om okänt/ej tillgängligt."""
    if raw in (None, '', 'unavailable', 'unknown'):
        return None
    d = domain(eid)
    attrs = attrs or {}
    if d == 'binary_sensor':
        on, off = _BIN_TEXT.get(attrs.get('device_class') or '', ('På', 'Av'))
        return on if raw == 'on' else (off if raw == 'off' else str(raw))
    if d == 'weather':
        txt = _STATE_TEXT['weather'].get(raw, str(raw))
        t = format_number(attrs.get('temperature'), 0)
        return '%s, %s %s' % (txt, t, attrs.get('temperature_unit') or '°C') if t is not None else txt
    if d in ('fan', 'humidifier', 'water_heater') and raw in ('on', 'off'):
        return 'På' if raw == 'on' else 'Av'
    if d in _STATE_TEXT:
        return _STATE_TEXT[d].get(raw, str(raw))
    if d == 'input_datetime':
        s = str(raw)
        if len(s) >= 8 and s[-3:] == ':00' and s[-6] == ':':
            s = s[:-3]          # 07:30:00 -> 07:30, 2026-10-19 07:30:00 -> 2026-10-19 07:30
        return s
    return str(raw)


_DOMAIN_ICON = {'climate': 'Thermostat', 'cover': 'WindowShutter', 'lock': 'Lock', 'media_player': 'Speaker',
                'person': 'Account', 'device_tracker': 'Account', 'weather': 'WeatherPartlyCloudy',
                'sun': 'WhiteBalanceSunny', 'update': 'PackageUp', 'timer': 'TimerOutline', 'fan': 'Fan',
                'humidifier': 'AirHumidifier', 'water_heater': 'WaterBoiler'}


def value_icon(eid, attrs, unit=''):
    """Ikon på värdekorten."""
    d = domain(eid)
    dc = (attrs or {}).get('device_class') or ''
    if d == 'binary_sensor':
        if dc in ('door', 'garage_door', 'window', 'opening'):
            return 'DoorOpen'
        if dc in ('motion', 'occupancy', 'presence'):
            return 'MotionSensor'
        return 'Eye'
    if d in ('input_number', 'number'):
        return 'RayVertex'
    if d == 'select':
        return 'FormatListBulleted'
    if d in _DOMAIN_ICON:
        return _DOMAIN_ICON[d]
    if d == 'counter':
        return 'Counter'
    if d == 'input_datetime':
        return 'CalendarClock'
    if d in ('input_text', 'input_select'):
        return 'FormTextbox'
    if dc == 'temperature' or unit in ('°C', '°F', 'K'):
        return 'Thermometer'
    if dc in ('humidity', 'moisture'):
        return 'WaterPercent'
    if dc == 'battery':
        return 'Battery'
    if dc == 'signal_strength':
        return 'Wifi'
    if dc == 'illuminance' or unit == 'lx':
        return 'Brightness5'
    if dc in ('carbon_dioxide', 'co2'):
        return 'MoleculeCo2'
    if dc in ('power', 'energy', 'voltage', 'current', 'apparent_power', 'reactive_power') or unit in ('W', 'kW', 'kWh', 'Wh', 'V', 'A'):
        return 'Flash'
    return 'Gauge'
