"""Anslutningen till Home Assistant över WebSocket-API:t: inloggning med långlivad token, prenumeration på
ändringar (subscribe_entities, reserv subscribe_events), call_service, hjärtslag och återanslutning.
Visar aldrig gammal data som aktuell: varje avbrott rapporteras direkt och fullt läge hämtas vid återanslutning."""
import asyncio
import json
import os
import random
import time

from . import ws as wsmod

# status: 'connecting' (första försöket), 'connected', 'down'. Orsak: net, no_token, auth, proto
BACKOFF = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0)


class HASession(object):
    def __init__(self, loop, url, token_path, on_status, on_full, on_update, log=None, hb_interval=20.0, hb_timeout=10.0):
        self.loop = loop
        self.url, self.token_path = url, token_path
        self.on_status, self.on_full, self.on_update = on_status, on_full, on_update
        self.log = log or (lambda *a: None)
        self.hb_interval, self.hb_timeout = hb_interval, hb_timeout
        self.entities = set()
        self.ws = None
        self.connected = False
        self.version = None
        self._id = 0
        self._pending = {}
        self._sub_id = None
        self._mode = None
        self._states = {}
        self._task = None
        self._wake = asyncio.Event()
        self._resub = asyncio.Event()
        self._stop = False
        self.last_error = ''

    # ------------------------------------------------------------ livscykel
    def start(self):
        self._task = self.loop.create_task(self._run())

    async def stop(self):
        self._stop = True
        self._wake.set()
        if self.ws:
            self.ws.abort()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    def set_entities(self, entities):
        """Nya entiteter att följa (konfigurationen ändrad). Prenumerationen byts i den pågående anslutningen."""
        new = set(entities)
        if new != self.entities:
            self.entities = new
            self._resub.set()

    # ------------------------------------------------------------ huvudloop
    def _token(self):
        try:
            with open(self.token_path) as f:
                return f.read().strip()
        except OSError:
            return ''

    async def _sleep(self, secs):
        """Sov men vakna om token-filen ändras eller något annat kräver det."""
        end = self.loop.time() + secs
        try:
            mt = os.stat(self.token_path).st_mtime
        except OSError:
            mt = None
        while self.loop.time() < end and not self._stop:
            try:
                await asyncio.wait_for(self._wake.wait(), min(2.0, end - self.loop.time()))
                self._wake.clear()
                return
            except asyncio.TimeoutError:
                pass
            try:
                m2 = os.stat(self.token_path).st_mtime
            except OSError:
                m2 = None
            if m2 != mt:
                return

    async def _run(self):
        attempt = 0
        first = True
        while not self._stop:
            token = self._token()
            if not token:
                self._status('down', 'no_token')
                await self._sleep(5.0)
                continue
            if first:
                self._status('connecting', '')
                first = False
            t0 = self.loop.time()
            reason = 'net'
            try:
                await self._session(token)
            except asyncio.CancelledError:
                raise
            except AuthError as e:
                reason = 'auth'
                self.last_error = str(e)
                self.log('inloggning nekad:', e)
            except Exception as e:  # nät, protokoll, tidsgräns
                self.last_error = '%s: %s' % (type(e).__name__, e)
                self.log('anslutning avbröts:', self.last_error)
            self._drop()
            if self._stop:
                return
            self._status('down', reason)
            if reason == 'auth':
                await self._sleep(300.0)
                attempt = 0
                continue
            if self.loop.time() - t0 > 30:
                attempt = 0
            delay = BACKOFF[min(attempt, len(BACKOFF) - 1)] * (0.85 + 0.3 * random.random())
            attempt += 1
            await self._sleep(delay)

    def _status(self, status, reason):
        try:
            self.on_status(status, reason)
        except Exception as e:  # skärmkoden får aldrig fälla anslutningen
            self.log('fel i statusåteranrop:', repr(e))

    def _drop(self):
        was = self.connected
        self.connected = False
        self._sub_id = None
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_result(None)
        self._pending.clear()
        if self.ws:
            self.ws.abort()
            self.ws = None
        return was

    # ------------------------------------------------------------ en anslutning
    async def _session(self, token):
        ws = await wsmod.connect(self.url, timeout=8.0)
        self.ws = ws
        msg = await asyncio.wait_for(ws.recv(), 10)
        if msg is None:
            raise ConnectionError('stängdes direkt')
        first = json.loads(msg)
        if first.get('type') != 'auth_required':
            raise ProtoError('väntade auth_required, fick %s' % first.get('type'))
        self.version = first.get('ha_version')
        ws.send_text(json.dumps({'type': 'auth', 'access_token': token}))
        msg = await asyncio.wait_for(ws.recv(), 10)
        if msg is None:
            raise ConnectionError('stängdes under inloggning')
        res = json.loads(msg)
        if res.get('type') == 'auth_invalid':
            raise AuthError(res.get('message', 'ogiltig token'))
        if res.get('type') != 'auth_ok':
            raise ProtoError('väntade auth_ok, fick %s' % res.get('type'))
        self.version = res.get('ha_version', self.version)
        reader = self.loop.create_task(self._reader(ws))
        try:
            await self._subscribe()
            self.connected = True
            self._status('connected', '')
            hb = self.loop.create_task(self._heartbeat(ws))
            try:
                while True:
                    done, _ = await asyncio.wait([reader, hb], timeout=1.0, return_when=asyncio.FIRST_COMPLETED)
                    if done:
                        for d in done:
                            d.result()
                        raise ConnectionError('anslutningen föll')
                    if self._resub.is_set():
                        self._resub.clear()
                        await self._subscribe()
            finally:
                hb.cancel()
        finally:
            reader.cancel()
            try:
                await ws.close()
            except Exception:
                pass

    async def _reader(self, ws):
        while True:
            msg = await ws.recv()
            if msg is None:
                raise ConnectionError('stängd av Home Assistant')
            try:
                data = json.loads(msg)
            except ValueError:
                continue
            self._dispatch(data)

    async def _heartbeat(self, ws):
        while True:
            await asyncio.sleep(self.hb_interval)
            sent = self.loop.time()
            res = await self.request({'type': 'ping'}, timeout=self.hb_timeout)
            if res is None and ws.last_rx < sent:
                raise ConnectionError('inget svar på hjärtslaget')

    # ------------------------------------------------------------ meddelanden
    def _dispatch(self, data):
        t = data.get('type')
        if t in ('result', 'pong'):
            fut = self._pending.pop(data.get('id'), None)
            if fut is not None and not fut.done():
                fut.set_result(data)
        elif t == 'event':
            if data.get('id') != self._sub_id:
                return
            ev = data.get('event') or {}
            try:
                if self._mode == 'entities':
                    self._apply_compressed(ev)
                else:
                    self._apply_state_changed(ev)
            except Exception as e:
                self.log('kunde inte tolka händelse:', repr(e))

    def _next_id(self):
        self._id += 1
        return self._id

    async def request(self, msg, timeout=10.0):
        """Skickar ett kommando och väntar på svaret (dict) eller None vid tidsgräns/avbrott."""
        ws = self.ws
        if ws is None or ws.closed:
            return None
        mid = self._next_id()
        msg = dict(msg)
        msg['id'] = mid
        fut = self.loop.create_future()
        self._pending[mid] = fut
        try:
            ws.send_text(json.dumps(msg))
            return await asyncio.wait_for(fut, timeout)
        except (asyncio.TimeoutError, wsmod.WSError, ConnectionError, OSError):
            return None
        finally:
            self._pending.pop(mid, None)

    # ------------------------------------------------------------ prenumeration
    async def _subscribe(self):
        ents = sorted(self.entities)
        if self._sub_id is not None:
            old = self._sub_id
            self._sub_id = None
            await self.request({'type': 'unsubscribe_events', 'subscription': old}, timeout=5.0)
        self._states = {}
        if not ents:
            self.on_full({})
            return
        mid = self._next_id()
        fut = self.loop.create_future()
        self._pending[mid] = fut
        self._sub_id = mid
        self._mode = 'entities'
        self.ws.send_text(json.dumps({'id': mid, 'type': 'subscribe_entities', 'entity_ids': ents}))
        res = await asyncio.wait_for(fut, 10)
        if res is None:
            raise ConnectionError('ingen bekräftelse på prenumerationen')
        if not res.get('success'):
            self.log('subscribe_entities fungerade inte (%s), använder subscribe_events' % (res.get('error') or {}).get('code'))
            await self._subscribe_events(ents)
            return
        # första händelsen med fullt läge kommer direkt efter bekräftelsen; ge den tid
        for _ in range(100):
            if self._states or not ents:
                break
            await asyncio.sleep(0.05)
        if not self._states:
            # tomt: inga av entiteterna finns i HA (eller händelsen uteblev). Rapportera tomt läge.
            self.on_full({})

    async def _subscribe_events(self, ents):
        mid = self._next_id()
        fut = self.loop.create_future()
        self._pending[mid] = fut
        self._sub_id = mid
        self._mode = 'events'
        self.ws.send_text(json.dumps({'id': mid, 'type': 'subscribe_events', 'event_type': 'state_changed'}))
        res = await asyncio.wait_for(fut, 10)
        if res is None or not res.get('success'):
            raise ProtoError('subscribe_events misslyckades')
        allst = await self.request({'type': 'get_states'}, timeout=30.0)
        if not allst or not allst.get('success'):
            raise ProtoError('get_states misslyckades')
        want = set(ents)
        self._states = {}
        for s in allst['result']:
            if s['entity_id'] in want:
                self._states[s['entity_id']] = {'state': s.get('state'), 'attributes': s.get('attributes') or {}}
        self.on_full(dict(self._states))

    def _apply_compressed(self, ev):
        full = False
        first = not self._states
        added = ev.get('a')
        if added:
            for eid, st in added.items():
                self._states[eid] = {'state': st.get('s'), 'attributes': dict(st.get('a') or {})}
            if first:
                full = True
        changes = ev.get('c')
        upd = []
        if changes:
            for eid, diff in changes.items():
                cur = self._states.get(eid)
                if cur is None:
                    continue
                plus = diff.get('+') or {}
                if 's' in plus:
                    cur['state'] = plus['s']
                if 'a' in plus:
                    cur['attributes'].update(plus['a'])
                minus = diff.get('-') or {}
                for k in minus.get('a') or ():
                    cur['attributes'].pop(k, None)
                upd.append(eid)
        removed = ev.get('r')
        if removed:
            for eid in removed:
                self._states.pop(eid, None)
                upd.append(eid)
        if full:
            self.on_full(dict(self._states))
        else:
            if added:
                upd.extend(added.keys())
            for eid in upd:
                self.on_update(eid, self._states.get(eid))

    def _apply_state_changed(self, ev):
        d = ev.get('data') or {}
        eid = d.get('entity_id')
        if eid not in self.entities:
            return
        new = d.get('new_state')
        if new is None:
            self._states.pop(eid, None)
        else:
            self._states[eid] = {'state': new.get('state'), 'attributes': new.get('attributes') or {}}
        self.on_update(eid, self._states.get(eid))

    # ------------------------------------------------------------ anrop utåt
    async def call_service(self, domain, service, entity_ids, data=None, timeout=10.0):
        """True om Home Assistant bekräftade anropet."""
        if not self.connected:
            return False
        msg = {'type': 'call_service', 'domain': domain, 'service': service,
               'target': {'entity_id': list(entity_ids)}}
        if data:
            msg['service_data'] = data
        res = await self.request(msg, timeout=timeout)
        if res is None:
            return False
        if not res.get('success'):
            self.log('call_service nekades:', domain, service, res.get('error'))
            return False
        return True

    async def fetch_states(self):
        """Alla entiteter (för redigeringssidan). None om ingen kontakt."""
        if not self.connected:
            return None
        res = await self.request({'type': 'get_states'}, timeout=30.0)
        if not res or not res.get('success'):
            return None
        return res['result']

    async def fetch_registry(self, kind='entity'):
        """Ett register ur Home Assistant, bara för redigeringssidan: 'entity' (vilka enheter som är dolda eller
        tekniska, och deras område), 'area' (områdena) eller 'device' (enheternas område via apparaten).
        None om det inte gick (ingen kontakt eller token utan administratörsrätt): då visas allt utan områden."""
        if not self.connected:
            return None
        res = await self.request({'type': 'config/%s_registry/list' % kind}, timeout=30.0)
        if not res or not res.get('success') or not isinstance(res.get('result'), list):
            return None
        return res['result']


class AuthError(Exception):
    pass


class ProtoError(Exception):
    pass
