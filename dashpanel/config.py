"""Konfiguration (JSON-fil på dash, /etc/dash-panel/config.json): vilka flikar, lampor och sensorer som
visas, deras ordning och visningsnamn. Läses och valideras här; sparas atomiskt (temporär fil + fsync + rename)."""
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
TAB_ICONS = ('Lightbulb', 'LightbulbMultiple', 'Thermometer')
LIGHT_DOMAINS = ('light', 'switch')

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
    if not isinstance(tabs_in, list):
        tabs_in = copy.deepcopy(DEFAULTS['tabs'])
    tabs, used = [], set()
    for t in tabs_in[:MAX_TABS]:
        if not isinstance(t, dict):
            continue
        typ = t.get('type') if t.get('type') in ('lights', 'sensors') else 'lights'
        title = str(t.get('title') or ('Belysning' if typ == 'lights' else 'Temperaturer'))[:24]
        icon = t.get('icon') if t.get('icon') in TAB_ICONS else ('Lightbulb' if typ == 'lights' else 'Thermometer')
        tab = {'id': _slug(t.get('id') or title, used), 'title': title, 'type': typ, 'icon': icon, 'items': []}
        if typ == 'lights':
            tab['all_label'] = str(t.get('all_label') or 'Alla lampor')[:24]
            tab['show_all'] = t['show_all'] if isinstance(t.get('show_all'), bool) else True    # visa knappen "Alla lampor"?
        seen = set()
        limit = (MAX_LAMPS if tab['show_all'] else MAX_LAMPS_NO_ALL) if typ == 'lights' else MAX_SENSORS
        for it in t.get('items') or []:
            if not isinstance(it, dict):
                continue
            if typ == 'sensors' and it.get('placeholder'):
                tab['items'].append({'placeholder': True})
                continue
            eid = str(it.get('entity_id') or '').strip()
            dom = eid.split('.')[0] if '.' in eid else ''
            if typ == 'lights' and dom not in LIGHT_DOMAINS:
                warns.append('hoppade över %r (ingen lampa/strömbrytare)' % eid)
                continue
            if typ == 'sensors' and dom != 'sensor':
                warns.append('hoppade över %r (ingen sensor)' % eid)
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
                if isinstance(it.get('dimmable'), bool):
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
        tabs.append(tab)
    if not tabs:
        tabs = copy.deepcopy(DEFAULTS['tabs'])
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
