"""Redigeringssidan: en liten webbserver i panelen (port ui.edit_port, standard 8099) där man väljer vilka lampor,
strömbrytare och sensorer som visas, i vilken ordning, med vilka namn och på vilka flikar.

Säkerhet: bara adresser på det lokala nätet (eller samma dator) släpps in. Sidan och API:t rör aldrig tokenen: den
läses bara av anslutningen till Home Assistant och finns varken i svar eller i konfigurationsfilen. Skrivande anrop
kräver JSON och att Origin (om den finns) är samma som Host, så en annan webbplats kan inte ändra något via din webbläsare."""
import asyncio
import copy
import ipaddress
import json
import socket
import traceback

from . import config as cfgmod, model
from .editor_page import APP_CSS, APP_JS, INDEX_HTML

MAX_BODY = 64 * 1024
MAX_CONNS = 8
READ_TIMEOUT = 15.0
STATUS = {200: 'OK', 204: 'No Content', 400: 'Bad Request', 403: 'Forbidden', 404: 'Not Found', 405: 'Method Not Allowed',
          413: 'Payload Too Large', 415: 'Unsupported Media Type', 500: 'Internal Server Error', 503: 'Service Unavailable'}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; "
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


def editable(cfg):
    """Det redigeringssidan får se och ändra (inte ha-sektionen med sökvägen till tokenen)."""
    ui = cfg['ui']
    return {'tabs': cfg['tabs'],
            'locale': {'decimal_separator': cfg['locale']['decimal_separator']},
            'ui': {'dim_step': ui['dim_step'], 'dim_timeout': ui['dim_timeout']},
            'limits': {'tabs': cfgmod.MAX_TABS, 'lamps': cfgmod.MAX_LAMPS, 'lamps_no_all': cfgmod.MAX_LAMPS_NO_ALL,
                       'sensors': cfgmod.MAX_SENSORS},
            'icons': list(cfgmod.TAB_ICONS)}


def hidden_ids(registry):
    """Enheter som Home Assistant själv döljer: dolda, avstängda eller tekniska (inställning/diagnostik).
    Typiskt strömbrytaren bakom en lampa som gjorts med "Switch as X"."""
    out = set()
    for r in registry or ():
        if isinstance(r, dict) and (r.get('hidden_by') or r.get('disabled_by') or r.get('entity_category')):
            out.add(r.get('entity_id'))
    return out


def summarize_entities(states, registry=None):
    hid = hidden_ids(registry)
    out = []
    for s in states or ():
        eid = s.get('entity_id') or ''
        dom = eid.split('.', 1)[0]
        if dom not in ('light', 'switch', 'sensor'):
            continue
        a = s.get('attributes') or {}
        e = {'id': eid, 'name': a.get('friendly_name') or eid, 'state': s.get('state')}
        if dom == 'sensor':
            e['unit'] = a.get('unit_of_measurement') or ''
            e['dc'] = a.get('device_class') or ''
            e['num'] = model.format_number(s.get('state'), 1) is not None
        elif dom == 'light':
            e['dim'] = model.dimmable_from_attrs('light', a)
        if eid in hid:
            e['hid'] = True
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
                method, path, headers, body = await asyncio.wait_for(self._read_request(reader), READ_TIMEOUT)
            except asyncio.TimeoutError:
                return
            except _BadRequest as e:
                await self._send(writer, e.status, 'text/plain; charset=utf-8', str(e).encode('utf-8'))
                return
            except (ConnectionError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, OSError):
                return
            status, ctype, payload = await self._route(method, path, headers, body)
            await self._send(writer, status, ctype, payload)
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
        path = target.split('?', 1)[0]
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
        return method, path, headers, body

    async def _send(self, writer, status, ctype, payload, extra=None):
        hdr = ['HTTP/1.1 %d %s' % (status, STATUS.get(status, 'OK')),
               'Content-Type: ' + ctype,
               'Content-Length: %d' % len(payload),
               'Cache-Control: no-store',
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

    def _json(self, status, obj):
        return status, 'application/json; charset=utf-8', json.dumps(obj, ensure_ascii=False).encode('utf-8')

    async def _route(self, method, path, headers, body):
        if not self._host_ok(headers.get('host')):
            return 403, 'text/plain; charset=utf-8', b'Ogiltigt Host'
        if method == 'GET':
            if path == '/':
                return 200, 'text/html; charset=utf-8', INDEX_HTML.encode('utf-8')
            if path == '/app.css':
                return 200, 'text/css; charset=utf-8', APP_CSS.encode('utf-8')
            if path == '/app.js':
                return 200, 'application/javascript; charset=utf-8', APP_JS.encode('utf-8')
            if path == '/favicon.ico':
                return 204, 'image/x-icon', b''
            if path == '/api/state':
                return await self._api_state()
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
        entities, error = None, None
        hidden_known = False
        if connected:
            states, registry = await asyncio.gather(app.ha.fetch_states(), app.ha.fetch_registry())
            if states is None:
                error = 'Home Assistant svarade inte, försök igen.'
            else:
                entities = summarize_entities(states, registry)
                hidden_known = registry is not None
        else:
            error = 'Ingen kontakt med Home Assistant. Enheterna går inte att lista just nu.'
        return self._json(200, {'config': editable(app.cfg), 'connected': connected, 'entities': entities, 'error': error,
                                'hidden_known': hidden_known})

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
