"""Redigeringssidan: en liten webbserver i panelen (port ui.edit_port, standard 8099) där man väljer vad som visas på
flikarna (lampor, strömbrytare, scener, automationer, skript, hjälpare och sensorer), i vilken ordning, med vilka namn.
Listan kan sorteras grovt på område och typ (områdena hämtas ur Home Assistants register).

Säkerhet: bara adresser på det lokala nätet (eller samma dator) släpps in. Sidan och API:t rör aldrig tokenen: den
läses bara av anslutningen till Home Assistant och finns varken i svar eller i konfigurationsfilen. Skrivande anrop
kräver JSON och att Origin (om den finns) är samma som Host, så en annan webbplats kan inte ändra något via din webbläsare."""
import asyncio
import copy
import datetime
import ipaddress
import json
import os
import socket
import time
import traceback
import urllib.parse

from . import __version__, colorui, config as cfgmod, graph as graphmod, model
from .editor_page import APP_CSS, APP_JS, INDEX_HTML
from .gfx import ASSETS

# typsnittet på sidan är panelens eget (Roboto, assets/fonts), så att inget hämtas utifrån
FONTS = {'/fonts/300.ttf': 'Roboto-Light.ttf', '/fonts/400.ttf': 'Roboto-Regular.ttf', '/fonts/500.ttf': 'Roboto-Medium.ttf'}

MAX_BODY = 64 * 1024
MAX_CONNS = 8
READ_TIMEOUT = 15.0
STATUS = {200: 'OK', 204: 'No Content', 400: 'Bad Request', 403: 'Forbidden', 404: 'Not Found', 405: 'Method Not Allowed',
          413: 'Payload Too Large', 415: 'Unsupported Media Type', 500: 'Internal Server Error', 503: 'Service Unavailable'}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; font-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def peer_allowed(addr):
    """Lokalt nät: loopback, privata adresser (10/8, 172.16/12, 192.168/16) och länklokala. Allt annat nekas."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if getattr(ip, 'ipv4_mapped', None):
        ip = ip.ipv4_mapped
    return bool(ip.is_loopback or ip.is_private or ip.is_link_local)


def thin(points, t0, t1, n=240):
    """Tunnar en kurva till ungefär n punkter (medel per del), hål (None) behålls."""
    if len(points) <= n:
        return [[round(t), v] for t, v in points]
    width = (t1 - t0) / float(n) or 1.0
    out, bucket, cur = [], [], None
    for t, v in points:
        b = int((t - t0) / width)
        if b != cur and bucket:
            vals = [x for x in bucket if x[1] is not None]
            out.append([round(bucket[0][0]), (sum(x[1] for x in vals) / len(vals)) if vals else None])
            bucket = []
        cur = b
        bucket.append((t, v))
    if bucket:
        vals = [x for x in bucket if x[1] is not None]
        out.append([round(bucket[0][0]), (sum(x[1] for x in vals) / len(vals)) if vals else None])
    return out


def editable(cfg):
    """Det redigeringssidan får se och ändra (inte ha-sektionen med sökvägen till tokenen)."""
    ui = cfg['ui']
    return {'tabs': cfg['tabs'],
            'locale': {'decimal_separator': cfg['locale']['decimal_separator']},
            'ui': {'dim_step': ui['dim_step'], 'dim_timeout': ui['dim_timeout']},
            'limits': {'tabs': cfgmod.MAX_TABS, 'lamps': cfgmod.MAX_LAMPS, 'lamps_no_all': cfgmod.MAX_LAMPS_NO_ALL,
                       'sensors': cfgmod.MAX_SENSORS, 'graph': cfgmod.MAX_GRAPH},
            'graph_hours': list(cfgmod.GRAPH_HOURS),
            'icons': list(cfgmod.TAB_ICONS),
            'domains': {'lights': list(cfgmod.BUTTON_DOMAINS), 'sensors': list(cfgmod.VALUE_DOMAINS),
                        'graph': list(cfgmod.GRAPH_DOMAINS), 'lamps': list(cfgmod.LIGHT_DOMAINS)}}


def export_doc(cfg):
    """Hela konfigurationen som fil, för att flytta den till en annan platta. Utan Home Assistants adress och token
    (de hör till varje platta)."""
    e = editable(cfg)
    return {'simple_ha_dash_config': 1, 'version': __version__,
            'exported': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
            'tabs': e['tabs'], 'locale': e['locale'], 'ui': e['ui']}


def hidden_ids(registry):
    """Enheter som Home Assistant själv döljer: dolda, avstängda eller tekniska (inställning/diagnostik).
    Typiskt strömbrytaren bakom en lampa som gjorts med "Switch as X"."""
    out = set()
    for r in registry or ():
        if isinstance(r, dict) and (r.get('hidden_by') or r.get('disabled_by') or r.get('entity_category')):
            out.add(r.get('entity_id'))
    return out


def device_names(devices=None):
    """device_id -> namnet som Home Assistant visar (användarens eget namn om det finns)."""
    out = {}
    for d in devices or ():
        if isinstance(d, dict) and d.get('id'):
            n = d.get('name_by_user') or d.get('name')
            if n:
                out[d['id']] = str(n)
    return out


def entity_areas(registry=None, devices=None):
    """entity_id -> area_id, som Home Assistant räknar: entitetens eget område, annars apparatens."""
    dev_area = {}
    for d in devices or ():
        if isinstance(d, dict) and d.get('id'):
            dev_area[d['id']] = d.get('area_id')
    out = {}
    for r in registry or ():
        if not isinstance(r, dict) or not r.get('entity_id'):
            continue
        a = r.get('area_id') or dev_area.get(r.get('device_id'))
        if a:
            out[r['entity_id']] = a
    return out


def summarize_areas(areas):
    out = []
    for a in areas or ():
        if isinstance(a, dict) and a.get('area_id'):
            out.append({'id': a['area_id'], 'name': a.get('name') or a['area_id'], 'icon': a.get('icon') or ''})
    out.sort(key=lambda a: a['name'].lower())
    return out


SHOWN_DOMAINS = tuple(cfgmod.BUTTON_DOMAINS) + tuple(cfgmod.VALUE_DOMAINS)


def summarize_entities(states, registry=None, devices=None):
    hid = hidden_ids(registry)
    area_of = entity_areas(registry, devices)
    dev_of = {}
    for r in registry or ():
        if isinstance(r, dict) and r.get('entity_id') and r.get('device_id'):
            dev_of[r['entity_id']] = r['device_id']
    out = []
    for s in states or ():
        eid = s.get('entity_id') or ''
        dom = eid.split('.', 1)[0]
        if dom not in SHOWN_DOMAINS:
            continue
        a = s.get('attributes') or {}
        e = {'id': eid, 'name': a.get('friendly_name') or eid, 'state': s.get('state')}
        if dom in cfgmod.VALUE_DOMAINS:
            e['unit'] = a.get('unit_of_measurement') or ''
            e['dc'] = a.get('device_class') or ''
            e['num'] = model.format_number(s.get('state'), 1) is not None
        elif dom == 'light':
            e['dim'] = model.dimmable_from_attrs('light', a)
            c = colorui.caps(a)
            if c['ct']:
                e['ct'] = list(c['ct'])
            if c['color']:
                e['rgb'] = True
        ic = a.get('icon')
        if isinstance(ic, str) and ic.startswith('mdi:'):
            e['icon'] = ic[4:]
        if eid in hid:
            e['hid'] = True
        if eid in area_of:
            e['area'] = area_of[eid]
        if eid in dev_of:
            e['dev'] = dev_of[eid]
        out.append(e)
    out.sort(key=lambda e: (e['name'] or '').lower())
    return out


class EditServer(object):
    def __init__(self, loop, app, host='0.0.0.0'):
        self.loop, self.app, self.host = loop, app, host
        self.server = None
        self.port = None
        self._writers = set()
        self._names = {'localhost'}
        try:
            hn = socket.gethostname().lower()
            self._names |= {hn, hn + '.local', hn + '.lan'}
        except OSError:
            pass

    async def start(self):
        port = int(self.app.cfg['ui']['edit_port'])
        self.server = await asyncio.start_server(self._handle, self.host, port, backlog=8, limit=MAX_BODY + 8192)
        self.port = self.server.sockets[0].getsockname()[1]
        self.app.log_fn('redigeringssidan på port %d' % self.port)

    async def stop(self):
        if self.server:
            self.server.close()
        for w in list(self._writers):
            try:
                w.transport.abort()
            except Exception:
                pass
        if self.server:
            try:
                await asyncio.wait_for(self.server.wait_closed(), 1.0)
            except Exception:
                pass

    # ------------------------------------------------------------ HTTP
    async def _handle(self, reader, writer):
        peer = writer.get_extra_info('peername')
        if len(self._writers) >= MAX_CONNS:
            writer.transport.abort()
            return
        self._writers.add(writer)
        try:
            if not peer or not peer_allowed(peer[0]):
                await self._send(writer, 403, 'text/plain; charset=utf-8', b'Bara lokala natet.')
                return
            try:
                method, path, headers, body, query = await asyncio.wait_for(self._read_request(reader), READ_TIMEOUT)
            except asyncio.TimeoutError:
                return
            except _BadRequest as e:
                await self._send(writer, e.status, 'text/plain; charset=utf-8', str(e).encode('utf-8'))
                return
            except (ConnectionError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, OSError):
                return
            res = await self._route(method, path, headers, body, query)
            await self._send(writer, res[0], res[1], res[2], res[3] if len(res) > 3 else None)
        except Exception:
            self.app.log_fn('fel på redigeringssidan:\n' + traceback.format_exc())
            try:
                await self._send(writer, 500, 'text/plain; charset=utf-8', b'Internt fel')
            except Exception:
                pass
        finally:
            self._writers.discard(writer)
            try:
                writer.close()
            except Exception:
                pass

    async def _read_request(self, reader):
        head = await reader.readuntil(b'\r\n\r\n')
        lines = head.decode('latin-1').split('\r\n')
        parts = lines[0].split(' ')
        if len(parts) != 3 or not parts[2].startswith('HTTP/1.'):
            raise _BadRequest(400, 'Felaktig begaran')
        method, target = parts[0], parts[1]
        headers = {}
        for ln in lines[1:]:
            if not ln:
                continue
            k, sep, v = ln.partition(':')
            if sep:
                headers[k.strip().lower()] = v.strip()
        path, _, query = target.partition('?')
        body = b''
        if method == 'POST':
            try:
                n = int(headers.get('content-length', '0'))
            except ValueError:
                raise _BadRequest(400, 'Felaktig langd')
            if n < 0 or n > MAX_BODY:
                raise _BadRequest(413, 'For stor')
            if n:
                body = await reader.readexactly(n)
        return method, path, headers, body, query

    async def _send(self, writer, status, ctype, payload, extra=None):
        hdr = ['HTTP/1.1 %d %s' % (status, STATUS.get(status, 'OK')),
               'Content-Type: ' + ctype,
               'Content-Length: %d' % len(payload),
               'Cache-Control: ' + ('max-age=604800' if ctype == 'font/ttf' else 'no-store'),
               'X-Content-Type-Options: nosniff',
               'Referrer-Policy: no-referrer',
               'Content-Security-Policy: ' + CSP,
               'Connection: close']
        if extra:
            hdr.extend(extra)
        writer.write(('\r\n'.join(hdr) + '\r\n\r\n').encode('latin-1') + payload)
        await asyncio.wait_for(writer.drain(), 10)

    def _host_ok(self, host):
        """Skydd mot DNS-omdirigering: Host måste vara en IP-adress eller dashens eget namn."""
        if not host:
            return False
        h = host.strip().lower()
        if h.startswith('['):                       # IPv6: [::1]:8099
            name = h[1:h.find(']')] if ']' in h else h
        else:
            name = h.rsplit(':', 1)[0] if h.count(':') == 1 else h
        try:
            ipaddress.ip_address(name)
            return True
        except ValueError:
            return name in self._names

    def _font(self, name):
        try:
            with open(os.path.join(ASSETS, 'fonts', name), 'rb') as f:     # läses vid behov, hålls inte i minnet
                return 200, 'font/ttf', f.read()
        except OSError:
            return 404, 'text/plain; charset=utf-8', b'Hittades inte'

    def _json(self, status, obj):
        return status, 'application/json; charset=utf-8', json.dumps(obj, ensure_ascii=False).encode('utf-8')

    async def _route(self, method, path, headers, body, query=''):
        if not self._host_ok(headers.get('host')):
            return 403, 'text/plain; charset=utf-8', b'Ogiltigt Host'
        if method == 'GET':
            if path == '/':
                return 200, 'text/html; charset=utf-8', INDEX_HTML.encode('utf-8')
            if path == '/app.css':
                return 200, 'text/css; charset=utf-8', APP_CSS.encode('utf-8')
            if path == '/app.js':
                return 200, 'application/javascript; charset=utf-8', APP_JS.encode('utf-8')
            if path in FONTS:
                return self._font(FONTS[path])
            if path == '/favicon.ico':
                return 204, 'image/x-icon', b''
            if path == '/api/state':
                return await self._api_state()
            if path == '/api/history':
                return await self._api_history(query)
            if path == '/api/export':
                doc = json.dumps(export_doc(self.app.cfg), ensure_ascii=False, indent=1).encode('utf-8')
                name = 'simple_ha_dash-%s.json' % datetime.date.today().isoformat()
                return 200, 'application/json; charset=utf-8', doc, ['Content-Disposition: attachment; filename="%s"' % name]
            return 404, 'text/plain; charset=utf-8', b'Hittades inte'
        if method == 'POST' and path == '/api/save':
            origin = headers.get('origin')
            if origin and origin.split('//', 1)[-1] != headers.get('host'):
                return 403, 'text/plain; charset=utf-8', b'Fel Origin'
            if not headers.get('content-type', '').lower().startswith('application/json'):
                return 415, 'text/plain; charset=utf-8', b'Kraver application/json'
            return self._api_save(body)
        return 405, 'text/plain; charset=utf-8', b'Metoden stods inte'

    # ------------------------------------------------------------ API
    async def _api_state(self):
        app = self.app
        connected = bool(app.panel and app.panel.store.live)
        entities, areas, devs, error = None, [], {}, None
        hidden_known = False
        if connected:
            states, registry, devices, area_reg = await asyncio.gather(
                app.ha.fetch_states(), app.ha.fetch_registry('entity'), app.ha.fetch_registry('device'),
                app.ha.fetch_registry('area'))
            if states is None:
                error = 'Home Assistant svarade inte, försök igen.'
            else:
                entities = summarize_entities(states, registry, devices)
                areas = summarize_areas(area_reg)
                names = device_names(devices)
                used = {e['dev'] for e in entities if e.get('dev')}
                devs = {d: names[d] for d in used if d in names}
                hidden_known = registry is not None
        else:
            error = 'Ingen kontakt med Home Assistant. Enheterna går inte att lista just nu.'
        return self._json(200, {'config': editable(app.cfg), 'connected': connected, 'entities': entities, 'error': error,
                                'hidden_known': hidden_known, 'areas': areas, 'devices': devs})

    async def _api_history(self, query):
        """Historik för förhandsvisningen av en graf: ?ids=a,b&hours=24. Högst tre entiteter, tunnat till ca 240 punkter."""
        q = urllib.parse.parse_qs(query)
        ids = [i for i in (q.get('ids', [''])[0]).split(',') if i][:cfgmod.MAX_GRAPH]
        try:
            hours = int(q.get('hours', ['24'])[0])
        except ValueError:
            hours = 24
        if hours not in cfgmod.GRAPH_HOURS or not ids or \
                any(i.split('.', 1)[0] not in cfgmod.GRAPH_DOMAINS or len(i) > 120 for i in ids):
            return self._json(400, {'ok': False, 'error': 'Ogiltig fråga'})
        ha = self.app.ha
        if not (ha and ha.connected):
            return self._json(200, {'ok': False, 'error': 'Ingen kontakt med Home Assistant.'})
        now = time.time()
        data = await graphmod.fetch(ha, ids, hours, now)
        if data is None:
            return self._json(200, {'ok': False, 'error': 'Home Assistant svarade inte.'})
        out = {}
        for e, d in data.items():
            out[e] = {'points': thin([(t, v) for t, v in d.get('points') or ()], now - hours * 3600.0, now),
                      'band': [[round(t), mn, mx] for t, _, mn, mx in (d.get('band') or ())][::max(1, len(d.get('band') or ()) // 240)]
                      if d.get('band') else None,
                      'nostats': bool(d.get('nostats'))}
            hi, lo = graphmod.extremes(d)
            out[e]['max'] = list(hi) if hi else None
            out[e]['min'] = list(lo) if lo else None
        return self._json(200, {'ok': True, 'from': now - hours * 3600.0, 'to': now, 'series': out})

    def _api_save(self, body):
        app = self.app
        try:
            data = json.loads(body.decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError('förväntade ett objekt')
        except ValueError as e:
            return self._json(400, {'ok': False, 'error': 'Ogiltig JSON: %s' % e})
        new = copy.deepcopy(app.cfg)
        if isinstance(data.get('tabs'), list):
            new['tabs'] = data['tabs']
        loc = data.get('locale')
        if isinstance(loc, dict) and loc.get('decimal_separator') in (',', '.'):
            new['locale']['decimal_separator'] = loc['decimal_separator']
        ui = data.get('ui')
        if isinstance(ui, dict):
            for k in ('dim_step', 'dim_timeout'):
                if k in ui:
                    new['ui'][k] = ui[k]
        cfg, warns = cfgmod.normalize(new)
        try:
            cfgmod.save(cfg, app.config_path)
        except OSError as e:
            return self._json(500, {'ok': False, 'error': 'Kunde inte spara: %s' % e})
        app.note_saved()
        app.apply_config(cfg)
        app.log_fn('konfigurationen sparad från redigeringssidan')
        return self._json(200, {'ok': True, 'warnings': warns, 'config': editable(cfg)})


class _BadRequest(Exception):
    def __init__(self, status, msg):
        Exception.__init__(self, msg)
        self.status = status
