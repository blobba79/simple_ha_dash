"""Konfiguration (JSON-fil på dash, /etc/dash-panel/config.json): vilka flikar, lampor och sensorer som
visas, deras ordning och visningsnamn. Två sorters flikar: 'lights' (knappar: lampor, strömbrytare, fläktar,
automationer, hjälpare av/på, scener, skript och knappar) och 'sensors' (värden: sensorer, binära sensorer och
hjälpare med värde). Läses och valideras här; sparas atomiskt (temporär fil + fsync + rename)."""
import copy
import json
import os
import re
import shutil

DEFAULT_PATH = '/etc/dash-panel/config.json'
MAX_TABS = 4
MAX_LAMPS = 7           # 8 celler på lampfliken: sju lampor + "Alla lampor"
MAX_LAMPS_NO_ALL = 8    # utan "Alla lampor" (show_all: false) går alla åtta cellerna till lampor
MAX_SENSORS = 11        # två stora kort + 3x3 små
MAX_GRAPH = 3           # kurvor i en graf
GRAPH_HOURS = (6, 24, 168, 720)     # intervallen på grafen: 6 tim, 24 tim, 7 dagar, 30 dagar
TAB_TYPES = ('lights', 'sensors', 'graph')
TAB_ICONS = ('Lightbulb', 'LightbulbMultiple', 'Thermometer', 'ChartLine', 'WaterPercent', 'Home', 'Sofa', 'Flower',
             'Paw', 'Robot', 'Palette', 'ToggleSwitch', 'Fan')
LIGHT_DOMAINS = ('light', 'switch')     # räknas som lampor ("3 tända", knappen "Alla lampor")
TOGGLE_DOMAINS = LIGHT_DOMAINS + ('fan', 'input_boolean', 'automation', 'media_player', 'climate', 'humidifier')  # på/av
ACTION_DOMAINS = ('scene', 'script', 'button', 'input_button')              # tryck = kör/aktivera
BUTTON_DOMAINS = TOGGLE_DOMAINS + ACTION_DOMAINS        # det som får ligga på en knappflik (typen 'lights')
VALUE_DOMAINS = ('sensor', 'binary_sensor', 'input_number', 'counter', 'input_select', 'input_text', 'input_datetime',
                 'number', 'select', 'climate', 'cover', 'lock', 'media_player', 'person', 'device_tracker', 'weather',
                 'sun', 'update', 'timer', 'fan', 'humidifier', 'water_heater')     # visas som värde (bara läsning)
GRAPH_DOMAINS = ('sensor', 'input_number', 'counter', 'number')     # har ett tal som Home Assistant sparar historik för

DEFAULTS = {
    'version': 1,
    'ha': {'url': 'ws://homeassistant.local:8123/api/websocket', 'token_file': '/etc/dash-panel/token'},
    'locale': {'timezone': 'Europe/Stockholm', 'decimal_separator': ','},
    'ui': {'dim_step': 10, 'confirm_timeout': 2.0, 'heartbeat': 20.0, 'dim_timeout': 90, 'stale_after': 4.0,
           'edit_port': 8099},
    'tabs': [
        {'id': 'belysning', 'title': 'Belysning', 'type': 'lights', 'icon': 'Lightbulb', 'all_label': 'Alla lampor',
         'show_all': True, 'items': []},
        {'id': 'temperaturer', 'title': 'Temperaturer', 'type': 'sensors', 'icon': 'Thermometer', 'items': []},
    ],
}

_HEX = re.compile(r'^#?[0-9a-fA-F]{6}$')


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _slug(s, used):
    base = re.sub(r'[^a-z0-9]+', '-', (s or 'flik').lower()).strip('-') or 'flik'
    base = base.replace('å', 'a').replace('ä', 'a').replace('ö', 'o')
    cand, n = base, 2
    while cand in used:
        cand = '%s-%d' % (base, n)
        n += 1
    used.add(cand)
    return cand


def normalize(raw):
    """Fyller i standardvärden och rättar uppenbart fel. Ger (config, varningar)."""
    warns = []
    cfg = _merge(DEFAULTS, {k: v for k, v in (raw or {}).items() if k != 'tabs'})
    tabs_in = (raw or {}).get('tabs')
    if not isinstance(tabs_in, list):           # ingen lista alls (ny installation): två tomma standardflikar
        tabs_in = copy.deepcopy(DEFAULTS['tabs'])
    # en tom lista är ett medvetet val: panelen visar då en välkomstskärm
    tabs, used = [], set()
    for t in tabs_in[:MAX_TABS]:
        if not isinstance(t, dict):
            continue
        typ = t.get('type') if t.get('type') in TAB_TYPES else 'lights'
        title = str(t.get('title') or {'lights': 'Belysning', 'sensors': 'Temperaturer', 'graph': 'Graf'}[typ])[:24]
        icon = t.get('icon') if t.get('icon') in TAB_ICONS else \
            {'lights': 'Lightbulb', 'sensors': 'Thermometer', 'graph': 'ChartLine'}[typ]
        tab = {'id': _slug(t.get('id') or title, used), 'title': title, 'type': typ, 'icon': icon, 'items': []}
        if typ == 'lights':
            tab['all_label'] = str(t.get('all_label') or 'Alla lampor')[:24]
            tab['show_all'] = t['show_all'] if isinstance(t.get('show_all'), bool) else True    # visa knappen "Alla lampor"?
        if typ == 'graph':
            try:
                h = int(t.get('hours', 24))
            except (TypeError, ValueError):
                h = 24
            tab['hours'] = h if h in GRAPH_HOURS else 24
        seen = set()
        limit = {'lights': MAX_LAMPS_NO_ALL, 'sensors': MAX_SENSORS, 'graph': MAX_GRAPH}[typ]  # "Alla lampor" räknas nedan
        for it in t.get('items') or []:
            if not isinstance(it, dict):
                continue
            if typ == 'sensors' and it.get('placeholder'):
                tab['items'].append({'placeholder': True})
                continue
            eid = str(it.get('entity_id') or '').strip()
            dom = eid.split('.')[0] if '.' in eid else ''
            if typ == 'lights' and dom not in BUTTON_DOMAINS:
                warns.append('hoppade över %r (går inte att trycka på)' % eid)
                continue
            if typ == 'sensors' and dom not in VALUE_DOMAINS:
                warns.append('hoppade över %r (inget värde att visa)' % eid)
                continue
            if typ == 'graph' and dom not in GRAPH_DOMAINS:
                warns.append('hoppade över %r (inget tal att rita)' % eid)
                continue
            if eid in seen:
                continue
            seen.add(eid)
            item = {'entity_id': eid}
            name = it.get('name')
            if name:
                item['name'] = str(name)[:40]
            if typ == 'lights':
                col = it.get('color')
                if isinstance(col, str) and _HEX.match(col):
                    item['color'] = '#' + col.lstrip('#').lower()
                if isinstance(it.get('dimmable'), bool) and dom == 'light':
                    item['dimmable'] = it['dimmable']
            else:
                try:
                    item['decimals'] = max(0, min(3, int(it.get('decimals', 1))))
                except (TypeError, ValueError):
                    item['decimals'] = 1
                if it.get('unit'):
                    item['unit'] = str(it['unit'])[:8]
            if len(tab['items']) >= limit:
                warns.append('fliken "%s" rymmer högst %d, resten hoppades över' % (title, limit))
                break
            tab['items'].append(item)
        if typ == 'lights' and tab['show_all'] and len(tab['items']) > MAX_LAMPS and \
                any(it['entity_id'].split('.')[0] in LIGHT_DOMAINS for it in tab['items']):
            # knappen "Alla lampor" visas bara om fliken har lampor, och tar då den åttonde platsen
            warns.append('fliken "%s" rymmer högst %d med knappen för alla lampor, resten hoppades över' % (title, MAX_LAMPS))
            del tab['items'][MAX_LAMPS:]
        tabs.append(tab)
    cfg['tabs'] = tabs
    try:
        cfg['ui']['dim_step'] = max(1, min(50, int(cfg['ui']['dim_step'])))
        cfg['ui']['confirm_timeout'] = max(0.5, min(10.0, float(cfg['ui']['confirm_timeout'])))
        cfg['ui']['heartbeat'] = max(5.0, min(120.0, float(cfg['ui']['heartbeat'])))
        cfg['ui']['dim_timeout'] = max(0, int(cfg['ui']['dim_timeout']))
        cfg['ui']['stale_after'] = max(0.0, min(60.0, float(cfg['ui']['stale_after'])))
        cfg['ui']['edit_port'] = int(cfg['ui']['edit_port'])
    except (TypeError, ValueError):
        cfg['ui'] = copy.deepcopy(DEFAULTS['ui'])
        warns.append('ogiltiga ui-värden, använder standard')
    if cfg['locale'].get('decimal_separator') not in (',', '.'):
        cfg['locale']['decimal_separator'] = ','
    return cfg, warns


def load(path=DEFAULT_PATH):
    """Läser konfigurationen. Saknas filen används standard (tomma flikar). Ger (config, varningar)."""
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except FileNotFoundError:
        cfg, w = normalize({})
        return cfg, ['konfigurationsfilen %s saknas, använder tomma flikar' % path] + w
    except ValueError as e:
        try:
            shutil.copy2(path, path + '.broken')     # så att inget går förlorat om redigeringssidan sparar över den
        except OSError:
            pass
        cfg, w = normalize({})
        return cfg, ['konfigurationsfilen är trasig (%s), kopia i %s.broken, använder tomma flikar' % (e, path)] + w
    return normalize(raw)


def save(cfg, path=DEFAULT_PATH):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def entity_ids(cfg):
    out = []
    for t in cfg['tabs']:
        for it in t['items']:
            e = it.get('entity_id')
            if e and e not in out:
                out.append(e)
    return out
