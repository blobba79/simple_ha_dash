"""Batteriet: läser spänning, ström och status ur /sys/class/power_supply (skrivskyddat) och uppskattar laddnivån.

Varför inte PMIC:ns egen procentsiffra (`capacity`)? På dash saknar devicetree batterinoden vid PMIC:ns mätare (se
dash-batteri.md), så siffran är okalibrerad och går än för långsamt, än för fort. Spänningen är däremot pålitlig.
Nivån uppskattas därför ur cellens *vilospänning*:

  1. Spänningen under laddning ligger högre än vilospänningen (cellens inre resistans, ca 0,17 ohm mätt på dash).
     Vilospänning = spänning - ström * R vid laddning (+ vid urladdning), annars spänningen som den är.
  2. Medianen av de senaste avläsningarna används, så att enstaka felaktiga ADC-värden inte slår igenom.
  3. Vilospänningen översätts till laddnivå med en vanlig tabell för en LiPo-cell (1S).
  4. Nivån skalas så att 100 % betyder "fullladdad enligt den här installationens gräns" (FULL_UV, 4,0 V; samma
     värde som mjukvarugränsen dash-batt-limit pausar laddningen vid) och 0 % betyder tom (EMPTY_UV, 3,3 V).
     Cellens egna 100 % (4,2 V) används alltså inte: laddningen stannar medvetet lägre för att spara cellen.

Det är en uppskattning: tabellen är en allmän LiPo-kurva, inte uppmätt på just den här cellen, och cellens inre
resistans är en uppskattning. Räkna med 10-15 procentenheters osäkerhet, mest under laddning (där spänningsfallet
måste räknas bort); när laddningen är pausad och cellen vilar är den bättre, och vid toppen (100 % = 4,0 V) är den
säkrast. Mätt på dash 2026-10-09: ca 21 procentenheter på 16 minuter vid 0,93 A, där 2400 mAh bara borde ge ca 10,
medan hela laddningen sedan tom stämde bra med 2400 mAh. Kurvan kan alltså vara för brant mitt i intervallet.

"Full": när laddningen stoppats vid en av gränserna (mjukvarugränsen 4,0 V där dash-batt-limit pausar laddningen,
eller hårdvarugränsen 4,1 V där PMIC:n själv avslutar) visar PMIC:n "Not charging" (eller "Full"), och då visas
"100 % Full". Orsaken skiljs inte åt; det räcker att laddningen står still med nätdelen inkopplad och att nivån är
minst FULL_SNAP. Strax efter en paus har cellens spänning sjunkit något av sig själv (vilar ut) trots att nästan
ingen energi gått åt (ca 1 mA), så den uppskattade nivån ligger då på 90-95 % fast cellen står kvar vid gränsen.
Ligger nivån under FULL_SNAP (till exempel för att cellen drivit ner mot släppgränsen 3,85 V) visas i stället den
uppskattade nivån med "Laddar inte".

Statusen debounceas: "Laddar" blir "Laddar inte" först när det varit så ett tag (HOLD_SAMPLES avläsningar i rad).
Annars skulle dash-batt-limit, som pausar laddningen en halv minut i taget nära gränsen, få sidfoten att blinka."""
import collections
import os

POWER_SUPPLY = '/sys/class/power_supply'

FULL_UV = int(os.environ.get('DASH_BATT_FULL_UV', 4000000))     # vilospänning som räknas som 100 %
EMPTY_UV = int(os.environ.get('DASH_BATT_EMPTY_UV', 3300000))   # vilospänning som räknas som 0 %
R_MOHM = int(os.environ.get('DASH_BATT_R_MOHM', 170))           # cellens inre resistans i milliohm (uppmätt 130-180)
WINDOW = 5                  # antal avläsningar som medianen tas över
HOLD_SAMPLES = 6            # så många avläsningar i rad måste statusen ha ändrats innan sidfoten följer med
DEADBAND = 2                # procentsiffran flyttas först när den ändrats så här mycket (utom 0 och 100)
FULL_SNAP = int(os.environ.get('DASH_BATT_FULL_SNAP', 85))      # lägsta nivå (%) som får visas som "100 % Full"
FULL_SNAP_EXIT = 3          # "Full" släpps först när nivån sjunkit så här långt under FULL_SNAP (hindrar fladder)

# vilospänning (V) -> laddnivå (%), allmän kurva för en LiPo-cell (1S)
OCV_TABLE = [(3.27, 0.0), (3.61, 5.0), (3.69, 10.0), (3.71, 15.0), (3.73, 20.0), (3.75, 25.0), (3.77, 30.0),
             (3.79, 35.0), (3.80, 40.0), (3.82, 45.0), (3.84, 50.0), (3.85, 55.0), (3.87, 60.0), (3.91, 65.0),
             (3.95, 70.0), (3.98, 75.0), (4.02, 80.0), (4.08, 85.0), (4.11, 90.0), (4.15, 95.0), (4.20, 100.0)]

Batt = collections.namedtuple('Batt', 'pct state')      # state: charging | full | idle | discharging


def soc(volts):
    """Cellens laddnivå (0-100) vid vilospänningen volts, ur OCV_TABLE (linjär mellan punkterna)."""
    t = OCV_TABLE
    if volts <= t[0][0]:
        return t[0][1]
    if volts >= t[-1][0]:
        return t[-1][1]
    for (v0, s0), (v1, s1) in zip(t, t[1:]):
        if volts <= v1:
            return s0 + (s1 - s0) * (volts - v0) / (v1 - v0)
    return t[-1][1]


def percent(rest_uv, full_uv=None, empty_uv=None):
    """Vilospänning (µV) -> procent 0-100, där full_uv är 100 % och empty_uv är 0 %."""
    full = soc((FULL_UV if full_uv is None else full_uv) / 1e6)
    empty = soc((EMPTY_UV if empty_uv is None else empty_uv) / 1e6)
    if full <= empty:
        return 0
    p = (soc(rest_uv / 1e6) - empty) / (full - empty) * 100.0
    return max(0, min(100, int(round(p))))


def rest_voltage(v_uv, i_ua, status, r_mohm=None):
    """Uppskattad vilospänning (µV): spänningen minus spänningsfallet över cellens inre resistans under laddning
    (plus vid urladdning). µA * mΩ / 1000 = µV."""
    r = R_MOHM if r_mohm is None else r_mohm
    drop = abs(i_ua) * r // 1000
    if status == 'Charging':
        return v_uv - drop
    if status == 'Discharging':
        return v_uv + drop
    return v_uv


def state_of(status):
    """Läget ur PMIC:ns status. "full" är bara en kandidat: BatteryMeter gör om det till "idle" om nivån är låg."""
    if status == 'Charging':
        return 'charging'
    if status == 'Discharging':
        return 'discharging'
    if status in ('Not charging', 'Full'):
        return 'full'                   # nätdel kopplad men laddningen står still (gräns nådd, paus eller Full)
    return 'idle'                       # Unknown med mera


def _read_text(path):
    try:
        with open(path, encoding='ascii', errors='replace') as f:
            return f.read().strip()
    except OSError:
        return None


def _read_int(path):
    s = _read_text(path)
    if s is None:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def find_battery(root=POWER_SUPPLY):
    """Katalogen för första batteriet (type = Battery) under root, annars None."""
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return None
    for n in names:
        d = os.path.join(root, n)
        if _read_text(os.path.join(d, 'type')) == 'Battery':
            return d
    return None


def read_battery(path):
    """(status, spänning µV, ström µA) ur batterikatalogen, eller None om batteriet saknas eller värdena är orimliga."""
    if path is None:
        return None
    if _read_text(os.path.join(path, 'present')) == '0':
        return None
    status = _read_text(os.path.join(path, 'status'))
    v = _read_int(os.path.join(path, 'voltage_now'))
    i = _read_int(os.path.join(path, 'current_now'))
    if status is None or v is None or not (2000000 <= v <= 5000000):
        return None
    return status, v, (i or 0)


class BatteryMeter(object):
    """Läser batteriet och ger Batt(pct, state), eller None när det saknas (då visas inget i sidfoten).
    read: () -> (status, µV, µA) | None (för prov). path: batterikatalog, annars hittas den, "none" stänger av."""

    def __init__(self, path=None, read=None, root=POWER_SUPPLY, window=WINDOW, hold=HOLD_SAMPLES, deadband=DEADBAND):
        self.path = path
        self.root = root
        self._read = read
        self.hold = hold
        self.deadband = deadband
        self._rest = collections.deque(maxlen=window)
        self._state = None
        self._cand = None
        self._cand_n = 0
        self._pct = None
        self._snap = False

    def _raw(self):
        if self._read is not None:
            return self._read()
        if self.path == 'none':
            return None
        p = self.path or find_battery(self.root)
        return read_battery(p)

    def sample(self):
        """En avläsning. Anropas med jämna mellanrum (panelen gör det var 10:e sekund)."""
        r = self._raw()
        if r is None:
            self._rest.clear()
            self._state = self._cand = self._pct = None
            self._cand_n = 0
            self._snap = False
            return None
        status, v, i = r
        self._rest.append(rest_voltage(v, i, status))
        med = sorted(self._rest)[len(self._rest) // 2]
        p = percent(med)
        if self._pct is None or abs(p - self._pct) >= self.deadband or p in (0, 100):
            self._pct = p
        raw = state_of(status)
        if self._state is None:
            self._state = raw
        elif raw == self._state:
            self._cand, self._cand_n = None, 0
        else:
            self._cand_n = self._cand_n + 1 if raw == self._cand else 1
            self._cand = raw
            if self._cand_n >= self.hold:
                self._state, self._cand, self._cand_n = raw, None, 0
        pct, state = self._pct, self._state
        if state == 'full':
            limit = FULL_SNAP - (FULL_SNAP_EXIT if self._snap else 0)
            self._snap = pct >= limit
            if self._snap:
                pct = 100               # gränsen nådd: 100 % betyder FULL_UV (4,0 V), laddningen står kvar där
            else:
                state = 'idle'          # laddar inte och nivån är inte nära gränsen: visa nivån som den är
        else:
            self._snap = False
        return Batt(pct, state)
