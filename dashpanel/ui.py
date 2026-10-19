"""Panelens gränssnitt: tillstånd -> vyer (flikar, dimvy), pek -> åtgärder, optimistisk uppdatering.

Skärmen ritas bara där något ändrats: varje del (flikrad, klocka, en lampcell ...) har en nyckel; en del ritas om
först när nyckeln ändrats. Surface samlar de ändrade rutorna och skickar dem till framebuffern i ett svep.

Ingen gammal data visas som aktuell: utan kontakt med Home Assistant (efter en kort frist) blir lamporna gråa
("Ingen kontakt") och temperaturerna visar ett streck."""
import json
import os
import time
import traceback

from . import __version__, gamelib, gamesdk, model, theme as T, views as V
from .gfx import H, W, fit, hex_rgb

NAV_MAX_END = 802.0         # flikraden får inte nå klockan (klocka, spelikon och kugghjul sitter till höger)
WIFI_INTERVAL = 5.0         # så ofta läses Wi-Fi-styrkan
BATT_INTERVAL = 10.0        # så ofta läses batteriet (laddnivån ändras långsamt)
BYE_FAIL_SECONDS = 4.0      # så länge "det gick inte" visas innan inställningarna kommer tillbaka
UPDATE_POLL_SECONDS = 1.0   # så ofta läses hur uppdateringen går (en liten fil, inget anrop)
UPDATE_TIMEOUT = 300.0      # längre än så här väntar panelen inte på att en uppdatering ska bli klar
UPDATE_RESULT_SECONDS = 8.0 # så länge resultatet av en uppdatering visas innan inställningarna kommer tillbaka
HIT_SLOP = 16               # så många pixlar får fingret glida från ytan och ändå räknas som tryck
SLOW_DRAW = 0.0 if os.environ.get('DASH_PERF') else 0.12   # logga ritningar som tar längre (sekunder)
STATE_SAVE_DELAY = 8.0        # sparar minnet först när det varit lugnt en stund (sparar SD-kortet)
DRAW_MIN_INTERVAL = 0.03    # tätast ritning vid pågående händelseflöde (reglagedrag, många uppdateringar)
SEND_MIN_INTERVAL = 0.25    # tätast skickade ljusstyrkor under drag (ca 4 per sekund)
GAME_IDLE_SECONDS = 300.0   # spelet lämnas av sig själv efter så här länge utan tryck (spelet och poängen sparas)
GAME_PRESCAN_DELAY = 30.0   # så länge efter start söks spelmappen igenom i förväg (att tolka en spelfil tar ca 0,4 s på dash)

DIM_TOGGLE_HIT = (600, 112, 744, 196)
DIM_SLIDER_HIT = (760, 80, 1016, 562)
DIM_BTN_RECT = (49, 447, 719, 527)


def _inside(r, x, y, slop=0):
    return r[0] - slop <= x < r[2] + slop and r[1] - slop <= y < r[3] + slop


class Panel(object):
    def __init__(self, loop, surface, cfg, call_service, now_fn=None, hints=None, log=None, state_path=None):
        self.loop = loop
        self.s = surface
        self.call_service = call_service        # async (domain, service, [entity_id], data|None) -> bool
        self._now_override = now_fn
        self.hints = hints or {}
        self.display = self.hints.get('display')        # display.Display: ljusstyrka och tid tills skärmen släcks (eller None)
        self.log = log or (lambda *a: None)
        self.store = model.Store()
        self.pending = {}                       # entity_id -> {state, pct, deadline, seq}
        self.last_pct = {}
        self.last_rgb = {}
        self.drawn = {}
        self.screen = 'tab'                     # tab | dim | settings | confirm | bye | game
        self.confirm_kind = None                # update | reboot | poweroff | quit (visas i confirm och bye)
        self.update_state = None                # dict(kind, title, sub, done) medan uppdateringen visas (screen bye)
        self.updater = self.hints.get('updater')    # updater.Updater eller None (provmiljö utan uppdaterare)
        self._update_timer = None
        self._update_t0 = 0.0
        self.bye_failed = False
        self.screen_off = False                 # bakgrundsbelysningen är släckt: nästa tryck väcker bara skärmen
        self.slider_active = None               # 0 (ljusstyrka) | 1 (släcktid) medan ett reglage dras
        self._swallow = False                   # väckningstrycket ska inte räknas som tryck på något
        self._off_timer = None
        self._last_touch = 0.0
        self._wifi_pct = None
        self._wifi_timer = None
        self._batt = None                       # battery.Batt(pct, state) eller None (inget batteri)
        self._batt_timer = None
        self._bye_timer = None
        self.tab_idx = 0
        self.dim_eid = None
        self.dim_tab = 0
        self.touch = None
        self.pressed = None                     # ('cell', i) | ('btn', 'Minus'|'Plus') | ('gear', 0) | ('game', 0) | ('sbtn'|'cbtn', namn)
        self.drag_pct = None
        self._back_rect = None
        self._nav_end = 0
        self._seq = 0
        self._ever_live = False
        self._stale = True
        self._stale_timer = None
        self._pending_timer = None
        self._refresh_handle = None
        self._clock_timer = None
        self._dim_timer = None
        self._drag_timer = None
        self._last_draw = -1.0
        self._sent_t = -1.0
        self._sent_pct = None
        self._stopped = False
        self._clock = None
        self.game = None                        # spelskärmen som visas (screen == 'game'): väljaren eller ett spel
        self.game_kind = None                   # 'picker' eller spelets id (vilken av dem self.game är)
        self._games = {}                        # kind -> skärmobjekt, skapas första gången de behövs
        self._prescan_timer = None
        self._render_gen = 0                    # räknas upp vid varje hel omritning (spelet ritar om allt då)
        # spelen är filer i spelmappen (gamelib.py); utan hint (prov) finns inga
        self.library = gamelib.Library(self.hints.get('games_dir'), self.hints.get('gamedata_dir'), self.log,
                                       self.hints.get('game_legacy_root') or gamelib.LEGACY_ROOT)
        self.game_sync = self.hints.get('game_sync')          # gamesync.GameSync (knappen Uppdatera spel) eller None
        self.state_path = state_path if state_path not in (None, '', 'none') else None
        self._state_dirty = False
        self._state_timer = None
        self._state_warned = False
        self._load_state()
        self.set_config(cfg, render=False)

    # ------------------------------------------------------------ konfiguration och livscykel
    def set_config(self, cfg, render=True):
        self.cfg = cfg
        ui = cfg['ui']
        self.step = int(ui['dim_step'])
        self.confirm = float(ui['confirm_timeout'])
        self.dim_timeout = float(ui['dim_timeout'])
        self.stale_after = float(ui.get('stale_after', 4.0))
        self.sep = cfg['locale']['decimal_separator']
        self._clock = model.make_clock(cfg['locale']['timezone'])
        if self.tab_idx >= len(cfg['tabs']):
            self.tab_idx = 0
        if self.screen == 'dim' and self._find_item(self.dim_eid) is None:
            self.screen = 'tab'
        keep = {it['entity_id'] for t in cfg['tabs'] for it in t['items'] if it.get('entity_id')}
        for e in list(self.pending):
            if e not in keep:
                del self.pending[e]
        self.touch = None
        self.pressed = None
        self.drag_pct = None
        self.slider_active = None
        if render:
            self.render_all()

    def start(self):
        self._stopped = False
        if self.display is not None:
            self.display.screen_on()            # tar den sparade ljusstyrkan i bruk
        self._last_touch = self.loop.time()
        self._wifi_pct = self._read_wifi()
        self._batt = self._read_batt()
        self._resume_update()
        self.render_all()
        self._arm_clock()
        self._wifi_timer = self.loop.call_later(WIFI_INTERVAL, self._wifi_tick)
        self._batt_timer = self.loop.call_later(BATT_INTERVAL, self._batt_tick)
        if self.library.games_dir:
            self._prescan_timer = self.loop.call_later(GAME_PRESCAN_DELAY, self._prescan_games)
        self._arm_off_timer()

    def stop(self):
        self._stopped = True
        for name in ('_stale_timer', '_pending_timer', '_refresh_handle', '_clock_timer', '_dim_timer', '_drag_timer',
                     '_state_timer', '_wifi_timer', '_batt_timer', '_bye_timer', '_off_timer', '_update_timer', '_prescan_timer'):
            h = getattr(self, name)
            if h is not None:
                h.cancel()
                setattr(self, name, None)
        self._save_state()
        for kind, scr in list(self._games.items()):
            try:
                scr.stop()
            except Exception as e:
                self.log('kunde inte spara spelet (%s):' % kind, repr(e))

    def _prescan_games(self):
        """Läser in spelfilerna en gång en stund efter start, så att den första öppningen av väljaren inte väntar på att de
        tolkas (biblioteket minns dem på ändringstid och storlek)."""
        self._prescan_timer = None
        if self._stopped:
            return
        try:
            self.library.scan()
        except Exception as e:
            self.log('kunde inte läsa in spelen i förväg:', repr(e))

    def now(self):
        return (self._now_override or self._clock)()

    # ------------------------------------------------------------ data från Home Assistant
    def on_ha_status(self, status, reason):
        st = self.store
        st.status, st.reason = status, reason
        if status != 'connected':
            st.have_full = False
            self.pending.clear()
        self._live_changed()
        self.request_refresh()

    def on_ha_full(self, states):
        self.store.states = dict(states)
        self.store.have_full = True
        for eid, s in states.items():
            self._remember(eid, s)
        self.pending.clear()
        self._live_changed()
        self.request_refresh()

    def on_ha_update(self, eid, st):
        if st is None:
            self.store.states.pop(eid, None)
        else:
            self.store.states[eid] = st
            self._remember(eid, st)
        p = self.pending.get(eid)
        if p is not None and self._matches(p, st):
            del self.pending[eid]
            self._arm_pending_timer()
        self.request_refresh()

    def _remember(self, eid, st):
        attrs = st.get('attributes') or {}
        if st.get('state') == 'on':
            pct = model.brightness_pct(attrs)
            if pct:
                self._set_pct(eid, pct)
            rgb = attrs.get('rgb_color')
            if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
                self.last_rgb[eid] = tuple(int(v) for v in rgb)

    @staticmethod
    def _matches(p, st):
        if st is None:
            return False
        s = st.get('state')
        if p['state'] == 'off':
            return s == 'off'
        if s != 'on':
            return False
        if p['pct'] is None:
            return True
        cur = model.brightness_pct(st.get('attributes') or {})
        return cur is None or abs(cur - p['pct']) <= 3

    @property
    def stale(self):
        return self._stale

    def _live_changed(self):
        if self.store.live:
            self._ever_live = True
            if self._stale_timer is not None:
                self._stale_timer.cancel()
                self._stale_timer = None
            self._stale = False
        elif not self._ever_live:
            self._stale = True
        elif not self._stale and self._stale_timer is None:
            if self.stale_after <= 0:
                self._go_stale()
            else:
                self._stale_timer = self.loop.call_later(self.stale_after, self._go_stale)

    def _go_stale(self):
        self._stale_timer = None
        if not self.store.live:
            self._stale = True
            self.pending.clear()
            self.request_refresh()

    # ------------------------------------------------------------ minne för ljusstyrka
    def _load_state(self):
        if not self.state_path:
            return
        try:
            with open(self.state_path, encoding='utf-8') as f:
                d = json.load(f)
            for eid, v in (d.get('last_pct') or {}).items():
                v = int(v)
                if 1 <= v <= 100:
                    self.last_pct[eid] = v
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def _set_pct(self, eid, pct):
        """Kom ihåg senaste ljusstyrka (när lampan var tänd) så att den kommer tillbaka på samma nivå."""
        if self.last_pct.get(eid) == pct:
            return
        self.last_pct[eid] = pct
        if self.state_path:
            self._state_dirty = True
            if self._state_timer is None and not self._stopped:
                self._state_timer = self.loop.call_later(STATE_SAVE_DELAY, self._state_tick)

    def _state_tick(self):
        self._state_timer = None
        self._save_state()

    def _save_state(self):
        if not self.state_path or not self._state_dirty:
            return
        self._state_dirty = False
        try:
            d = os.path.dirname(self.state_path)
            if d:
                os.makedirs(d, exist_ok=True)
            tmp = self.state_path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump({'last_pct': dict(sorted(self.last_pct.items())[:300])}, f, ensure_ascii=False, indent=1)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.state_path)
        except OSError as e:
            if not self._state_warned:
                self._state_warned = True
                self.log('kunde inte spara ljusstyrkeminnet (%s): %s' % (self.state_path, e))

    def _is_dimmable(self, eid):
        found = self._find_item(eid)
        return bool(found and self.lamp_info(found[1])['dimmable'])

    # ------------------------------------------------------------ vymodeller
    def _find_item(self, eid):
        if not eid:
            return None
        order = [self.dim_tab] + [i for i in range(len(self.cfg['tabs'])) if i != self.dim_tab]
        for i in order:
            if i >= len(self.cfg['tabs']):
                continue
            t = self.cfg['tabs'][i]
            if t['type'] != 'lights':
                continue
            for it in t['items']:
                if it.get('entity_id') == eid:
                    return t, it
        return None

    def lamp_info(self, item):
        eid = item['entity_id']
        dom = eid.split('.', 1)[0]
        known = self.store.states.get(eid)
        attrs = (known or {}).get('attributes') or {}
        name = item.get('name') or attrs.get('friendly_name') or eid
        if isinstance(item.get('dimmable'), bool):
            dimmable = item['dimmable'] and dom == 'light'
        else:
            dimmable = model.dimmable_from_attrs(dom, attrs)
        rgb = attrs.get('rgb_color')
        if not (isinstance(rgb, (list, tuple)) and len(rgb) == 3):
            rgb = self.last_rgb.get(eid)
        if rgb is None and item.get('color'):
            rgb = hex_rgb(item['color'])
        pal = T.lamp_palette(rgb)
        pct = None
        if self.stale:
            state = 'stale'
        else:
            raw = known.get('state') if known else None
            state = raw if raw in ('on', 'off') else 'na'
            if state == 'on':
                pct = model.brightness_pct(attrs)
            p = self.pending.get(eid)
            if p is not None and state in ('on', 'off'):
                state = p['state']
                pct = p['pct'] if p['pct'] is not None else (pct if state == 'on' else None)
            if state == 'on' and pct is None:
                pct = self.last_pct.get(eid)
        if state == 'on':
            status = ('På · %d %%' % pct) if (dimmable and pct is not None) else 'På'
        elif state == 'off':
            status = 'Av'
        elif state == 'na':
            status = 'Ej tillgänglig'
        else:
            status = self._stale_text()
        return {'eid': eid, 'name': name, 'state': state, 'status': status, 'pal': pal, 'dimmable': dimmable,
                'pct': pct}

    def _stale_text(self):
        return 'Ansluter …' if (self.store.status == 'connecting' and not self._ever_live) else 'Ingen kontakt'

    def _all_vm(self, tab, infos):
        n_on = sum(1 for i in infos if i['state'] == 'on')
        n_avail = sum(1 for i in infos if i['state'] in ('on', 'off'))
        if self.stale:
            state, status = 'stale', self._stale_text()
        elif n_avail == 0:
            state, status = 'na', 'Ej tillgänglig'
        else:
            state = 'on' if n_on else 'off'
            status = '%d av %d tända' % (n_on, len(infos))
        return V.LampVM('all', tab.get('all_label') or 'Alla lampor', state, status)

    def sensor_info(self, item):
        eid = item['entity_id']
        known = self.store.states.get(eid)
        attrs = (known or {}).get('attributes') or {}
        label = item.get('name') or attrs.get('friendly_name') or eid
        unit = item.get('unit') or attrs.get('unit_of_measurement') or ''
        value = None
        if known is not None and not self.stale:
            raw = known.get('state')
            num = model.format_number(raw, item.get('decimals', 1), self.sep)
            if num is not None:
                value = num
            elif raw not in (None, '', 'unavailable', 'unknown'):
                value, unit = str(raw), ''
        return label, value, unit

    def _nav_tabs(self):
        tabs = []
        counts = []
        for t in self.cfg['tabs']:
            d = {'title': t['title'], 'icon': t['icon']}
            n = 0
            if t['type'] == 'lights' and not self.stale:
                n = sum(1 for it in t['items'] if self.lamp_info(it)['state'] == 'on')
                if n:
                    d['badge'] = model.count_text(n)
            tabs.append(d)
            counts.append(n)
        geo = V.tab_geometry(tabs)
        if geo and geo[-1]['x'] + geo[-1]['w'] > NAV_MAX_END:
            # får flikarna inte plats: märkena blir bara siffran ("5" i stället för "5 tända") ...
            for d, n in zip(tabs, counts):
                if n:
                    d['badge'] = str(n)
            geo = V.tab_geometry(tabs)
            if geo[-1]['x'] + geo[-1]['w'] > NAV_MAX_END:
                # ... därefter med mindre luft runt siffran, och först sist kortas något namn
                for d in tabs:
                    if d.get('badge'):
                        d['tight'] = True
        for _ in range(40):
            geo = V.tab_geometry(tabs)
            if geo[-1]['x'] + geo[-1]['w'] <= NAV_MAX_END:
                break
            k = max(range(len(tabs)), key=lambda i: geo[i]['tw'])
            tabs[k]['title'] = fit(tabs[k]['title'], 500, 21, max(24.0, geo[k]['tw'] - 14))
        return tabs

    def _status_line(self):
        st = self.store
        if st.live:
            return 'ok', 'Ansluten till Home Assistant'
        if st.status == 'connecting':
            return 'wait', 'Ansluter till Home Assistant …'
        if st.status == 'connected':
            return 'wait', 'Hämtar status från Home Assistant …'
        if st.reason == 'no_token':
            return 'bad', 'Token saknas (/etc/dash-panel/token)'
        if st.reason == 'auth':
            return 'bad', 'Home Assistant godtar inte token'
        return 'bad', 'Ingen kontakt med Home Assistant'

    def _edit_hint(self):
        url = self.hints.get('edit_url')
        url = url() if callable(url) else url
        return ('Välj på redigeringssidan: %s' % url) if url else 'Välj på redigeringssidan (port %d)' % self.cfg['ui']['edit_port']

    # ------------------------------------------------------------ ritning
    def _put(self, wid, key, rect, fn):
        if self.drawn.get(wid) == key:
            return
        self.drawn[wid] = key
        fn()
        self.s.mark(rect)

    def render_all(self):
        t0 = time.monotonic()
        V.clear(self.s.img, 0, 0, W, H)
        self.drawn = {}
        self._render_gen += 1
        self._nav_end = 0
        self._draw_screen()
        self.s.mark_all()
        self.s.flush()
        self._last_draw = self.loop.time()
        self._note_draw('hela skärmen', t0)

    def refresh(self):
        if self._stopped:
            return
        t0 = time.monotonic()
        self._draw_screen()
        n = self.s.flush()
        self._last_draw = self.loop.time()
        if n:
            self._note_draw('%d ruta/rutor' % n, t0)

    def _note_draw(self, what, t0):
        dt = time.monotonic() - t0
        if dt >= SLOW_DRAW:
            self.log('ritning (%s) tog %d ms' % (what, dt * 1000))

    def request_refresh(self, urgent=False):
        if self._stopped:
            return
        if urgent:
            if self._refresh_handle is not None:
                self._refresh_handle.cancel()
                self._refresh_handle = None
            self.refresh()
            return
        if self._refresh_handle is None:
            wait = max(0.01, self._last_draw + DRAW_MIN_INTERVAL - self.loop.time())
            self._refresh_handle = self.loop.call_later(wait, self._refresh_cb)

    def _refresh_cb(self):
        self._refresh_handle = None
        self.refresh()

    def _draw_screen(self):
        if self.screen == 'dim':
            self._draw_dim()
        elif self.screen == 'settings':
            self._draw_settings()
        elif self.screen == 'confirm':
            self._draw_confirm()
        elif self.screen == 'bye':
            self._draw_bye()
        elif self.screen == 'game':
            self._draw_game()
        else:
            self._draw_tab()

    def _draw_footer(self, now):
        img = self.s.img
        ds = model.date_text(now)
        self._put('fdate', ds, (16, 566, 500, 594), lambda: V.draw_footer_date(img, ds))
        lvl, msg = self._status_line()
        pct = self._wifi_pct
        batt = self._batt
        self._put('fstat', (lvl, msg, pct, batt), (500, 566, W, 594),
                  lambda: V.draw_footer_status(img, lvl, msg, pct, batt))

    def _draw_tab(self):
        img = self.s.img
        now = self.now()
        tabs = self._nav_tabs()
        idx = self.tab_idx
        key = (tuple((t['title'], t['icon'], t.get('badge'), t.get('tight')) for t in tabs), idx)
        geo = V.tab_geometry(tabs)
        end = min(V.NAV_RECT[2], int(geo[-1]['x'] + geo[-1]['w']) + 16)
        self._put('nav', key, (0, V.NAV_RECT[1], max(end, self._nav_end), V.NAV_RECT[3]), lambda: V.draw_nav(img, tabs, idx))
        self._nav_end = end
        hh = model.hhmm(now)
        self._put('clock', hh, V.CLOCK_RECT, lambda: V.draw_clock(img, hh))
        self._draw_gear(False)
        self._draw_game_btn()
        tab = self.cfg['tabs'][idx]
        if tab['type'] == 'lights':
            self._draw_lights(tab)
        else:
            self._draw_sensors(tab)
        self._draw_footer(now)

    def _draw_empty(self, line1):
        img = self.s.img
        line2 = self._edit_hint()
        self._put('empty', (line1, line2), (16, 86, 1008, 556), lambda: V.draw_empty(img, line1, line2))

    def _draw_lights(self, tab):
        img = self.s.img
        items = tab['items']
        if not items:
            self._draw_empty('Inga lampor valda')
            return
        infos = [self.lamp_info(it) for it in items]
        for i, inf in enumerate(infos):
            vm = V.LampVM('lamp', inf['name'], inf['state'], inf['status'], inf['pal'], inf['dimmable'],
                          self.pressed == ('cell', i))
            self._put(('cell', i), vm.key(), V.cell_rect(i), lambda i=i, vm=vm: V.draw_lamp_cell(img, i, vm))
        if not tab.get('show_all', True):
            return
        n = len(items)
        avm = self._all_vm(tab, infos)
        avm.pressed = self.pressed == ('cell', n)
        self._put(('cell', n), avm.key(), V.cell_rect(n), lambda: V.draw_lamp_cell(img, n, avm))

    def _draw_sensors(self, tab):
        img = self.s.img
        items = tab['items']
        if not items:
            self._draw_empty('Inga sensorer valda')
            return
        for k in range(2):
            if k >= len(items) or items[k].get('placeholder'):
                continue
            label, value, unit = self.sensor_info(items[k])
            self._put(('big', k), ('big', label, value, unit), V.BIG_CARDS[k],
                      lambda k=k, label=label, value=value, unit=unit:
                      V.draw_temp_big(img, k, label, value or '', unit, value is None))
        variant = 0
        for k in range(9):
            j = 2 + k
            if j >= len(items):
                break
            it = items[j]
            if it.get('placeholder'):
                self._put(('small', k), ('sk', variant), V.small_rect(k),
                          lambda k=k, v=variant: V.draw_temp_skeleton(img, k, v))
                variant += 1
                continue
            label, value, unit = self.sensor_info(it)
            self._put(('small', k), ('sm', label, value, unit), V.small_rect(k),
                      lambda k=k, label=label, value=value, unit=unit:
                      V.draw_temp_small(img, k, label, value or '', unit, value is None))

    def _draw_dim(self):
        img = self.s.img
        found = self._find_item(self.dim_eid)
        if found is None:
            self.screen = 'tab'
            self.render_all()
            return
        tab, item = found
        inf = self.lamp_info(item)
        now = self.now()
        eid = inf['eid']
        state, pal = inf['state'], inf['pal']
        palkey = tuple(sorted(pal.items()))

        def head():
            rect, xr = V.draw_back(img, tab['title'])
            self._back_rect = rect
            V.draw_dim_title(img, inf['name'], xr)
        self._put('head', (tab['title'], inf['name']), (0, 10, V.NAV_RECT[2], 82), head)
        hh = model.hhmm(now)
        self._put('clock', hh, V.CLOCK_RECT, lambda: V.draw_clock(img, hh))
        self._draw_gear(False)
        self._draw_game_btn()
        self._put('card', 1, V.CARD_RECT, lambda: V.draw_dim_card(img))

        pct = self.drag_pct if self.drag_pct is not None else inf['pct']
        if state == 'on':
            shown = pct if pct is not None else self.last_pct.get(eid)
            value_text = str(shown) if shown is not None else '–'
            dimv, spct = False, (shown or 0)
        else:
            lp = self.last_pct.get(eid)
            value_text = str(lp) if (lp is not None and state == 'off') else '–'
            dimv, spct = True, 0
        top_status = 'På' if state == 'on' else ('Av' if state == 'off' else inf['status'])
        self._put('top', (state, top_status, palkey), V.TOP_ROW_RECT,
                  lambda: V.draw_dim_top(img, state, top_status, pal))
        self._put('value', (value_text, dimv), V.VALUE_RECT, lambda: V.draw_dim_value(img, value_text, dimv))
        pressed = self.pressed[1] if (self.pressed and self.pressed[0] == 'btn') else None
        enabled = state in ('on', 'off')
        self._put('btn', (pressed, enabled), DIM_BTN_RECT, lambda: V.draw_dim_buttons(img, pressed, enabled))
        self._put('slider', (spct, state, palkey), V.SLIDER_RECT, lambda: V.draw_slider(img, spct, state, pal))
        self._draw_footer(now)

    # ------------------------------------------------------------ klocka
    def _arm_clock(self):
        if self._clock_timer is not None:
            self._clock_timer.cancel()
        t = time.time()
        delay = min(15.0, 60.0 - (t % 60.0) + 0.05)
        self._clock_timer = self.loop.call_later(delay, self._clock_tick)

    def _clock_tick(self):
        self._clock_timer = None
        if self._stopped:
            return
        self.refresh()
        self._arm_clock()

    # ------------------------------------------------------------ pek
    def on_touch(self, kind, x, y):
        self._last_touch = self.loop.time()
        if self._swallow:
            if kind != 'down':
                if kind == 'up':
                    self._swallow = False
                return
            self._swallow = False               # nytt tryck utan att det förra släpptes: det förra gick förlorat
        if self.screen_off:
            if kind == 'down':                  # första trycket tänder bara skärmen
                self._swallow = True
                self._wake()
            return
        if self._off_timer is None:
            self._arm_off_timer()
        if self.screen in ('dim', 'settings', 'confirm', 'game'):
            self._arm_dim_timer()
        if self.screen == 'game':
            self._game_touch(kind, x, y)
            return
        if kind == 'down':
            self._down(x, y)
        elif kind == 'move':
            self._move(x, y)
        else:
            self._up(x, y)

    def _hit(self, x, y):
        if self.screen == 'bye':
            if self.update_state and self.update_state.get('done'):
                return ('byeok', None, (0, 0, W, H))        # resultatet av en uppdatering: tryck var som helst
            return None
        if _inside(V.GEAR_HIT, x, y):
            return ('gear', None, V.GEAR_HIT)
        if _inside(V.GAME_HIT, x, y):
            return ('game', None, V.GAME_HIT)
        if self.screen == 'dim':
            return self._hit_dim(x, y)
        if self.screen == 'settings':
            return self._hit_settings(x, y)
        if self.screen == 'confirm':
            return self._hit_confirm(x, y)
        return self._hit_tab(x, y)

    def _hit_tab(self, x, y):
        if 10 <= y < 82:
            for i, g in enumerate(V.tab_geometry(self._nav_tabs())):
                x0, _, x1, _ = g['rect']
                r = (x0 - 6, 10, x1 + 6, 82)
                if _inside(r, x, y):
                    return ('tab', i, r)
            return None
        tab = self.cfg['tabs'][self.tab_idx]
        if tab['type'] != 'lights' or not tab['items']:
            return None
        infos = [self.lamp_info(it) for it in tab['items']]
        for i, inf in enumerate(infos):
            if inf['state'] not in ('on', 'off'):
                continue
            z = V.lamp_zones(i, inf['dimmable'])
            for r in z['toggle']:
                if _inside(r, x, y):
                    return ('toggle', i, r)
            for r in z['dim']:
                if _inside(r, x, y):
                    return ('dim', i, r)
        if not tab.get('show_all', True):
            return None
        n = len(infos)
        r = V.cell_rect(n)
        if _inside(r, x, y) and self._all_vm(tab, infos).state in ('on', 'off'):
            return ('all', n, r)
        return None

    def _hit_dim(self, x, y):
        if self._back_rect and _inside(self._back_rect, x, y, 8):
            return ('back', None, self._back_rect)
        found = self._find_item(self.dim_eid)
        if found is None:
            return None
        inf = self.lamp_info(found[1])
        if inf['state'] not in ('on', 'off'):
            return None
        if _inside(DIM_TOGGLE_HIT, x, y):
            return ('dtoggle', None, DIM_TOGGLE_HIT)
        if _inside(V.BTN_MINUS, x, y):
            return ('btn', 'Minus', V.BTN_MINUS)
        if _inside(V.BTN_PLUS, x, y):
            return ('btn', 'Plus', V.BTN_PLUS)
        if _inside(DIM_SLIDER_HIT, x, y):
            return ('slider', None, DIM_SLIDER_HIT)
        return None

    def _hit_settings(self, x, y):
        if self._back_rect and _inside(self._back_rect, x, y, 8):
            return ('back', None, self._back_rect)
        for name in V.SBTN_ORDER:
            if _inside(V.SBTN[name], x, y):
                return ('sbtn', name, V.SBTN[name])
        if self._sliders_on():
            for row in (0, 1):
                if _inside(V.SLIDER_HIT[row], x, y):
                    return ('sset', row, V.SLIDER_HIT[row])
        return None

    def _hit_confirm(self, x, y):
        if self._back_rect and _inside(self._back_rect, x, y, 8):
            return ('back', None, self._back_rect)
        for name in ('cancel', 'ok'):
            if _inside(V.CBTN[name], x, y):
                return ('cbtn', name, V.CBTN[name])
        return None

    def _press_of(self, t):
        if t[0] in ('toggle', 'dim', 'all'):
            return ('cell', t[1])
        if t[0] == 'btn':
            return ('btn', t[1])
        if t[0] == 'gear':
            return ('gear', 0)
        if t[0] == 'game':
            return ('game', 0)
        if t[0] in ('sbtn', 'cbtn'):
            return (t[0], t[1])
        return None

    def _down(self, x, y):
        self.touch = None
        t = self._hit(x, y)
        if t is None:
            return
        self.touch = {'t': t, 'inside': True}
        if t[0] == 'slider':
            self._sent_t, self._sent_pct = -1.0, None
            self._slider_move(y)
            return
        if t[0] == 'sset':
            self._sset_move(t[1], x)
            return
        p = self._press_of(t)
        if p is not None:
            self.pressed = p
            self.request_refresh(urgent=True)

    def _move(self, x, y):
        tc = self.touch
        if tc is None:
            return
        t = tc['t']
        if t[0] == 'slider':
            self._slider_move(y)
            return
        if t[0] == 'sset':
            self._sset_move(t[1], x)
            return
        inside = _inside(t[2], x, y, HIT_SLOP)
        if inside != tc['inside']:
            tc['inside'] = inside
            p = self._press_of(t)
            if p is not None:
                self.pressed = p if inside else None
                self.request_refresh(urgent=True)

    def _up(self, x, y):
        tc, self.touch = self.touch, None
        if tc is None:
            return
        t = tc['t']
        if t[0] == 'slider':
            self._slider_up()
            return
        if t[0] == 'sset':
            self._sset_up(t[1])
            return
        was = self.pressed is not None
        self.pressed = None
        if tc['inside'] and _inside(t[2], x, y, HIT_SLOP):
            self._activate(t)
        elif was:
            self.request_refresh(urgent=True)

    def _activate(self, t):
        kind = t[0]
        if kind == 'tab':
            if t[1] != self.tab_idx:
                self.tab_idx = t[1]
                self.render_all()
            else:
                self.request_refresh(urgent=True)
            return
        if kind in ('toggle', 'dim'):
            item = self.cfg['tabs'][self.tab_idx]['items'][t[1]]
            if kind == 'toggle':
                self._toggle(item)
            else:
                self._open_dim(item)
            return
        if kind == 'all':
            self._toggle_all(self.cfg['tabs'][self.tab_idx])
            return
        if kind == 'gear':
            if self.screen in ('settings', 'confirm'):
                self._close_settings()
            else:
                self._open_settings()
            return
        if kind == 'game':
            self._open_game()
            return
        if kind == 'byeok':
            self._update_close()
            return
        if kind == 'sbtn':
            self._open_confirm(t[1])
            return
        if kind == 'cbtn':
            if t[1] == 'cancel':
                self._back_to_settings()
            elif self.confirm_kind == 'update':
                self._do_update()
            else:
                self._do_power(self.confirm_kind)
            return
        if kind == 'back':
            if self.screen == 'confirm':
                self._back_to_settings()
            elif self.screen == 'settings':
                self._close_settings()
            else:
                self._close_dim()
            return
        found = self._find_item(self.dim_eid)
        if found is None:
            return
        item = found[1]
        if kind == 'dtoggle':
            self._toggle(item)
        elif kind == 'btn':
            self._step(item, 1 if t[1] == 'Plus' else -1)

    # ------------------------------------------------------------ kugghjulet: inställningar, omstart, avstängning
    def _draw_gear(self, active):
        img = self.s.img
        pressed = self.pressed == ('gear', 0)
        self._put('gear', (active, pressed), V.GEAR_SLOT, lambda: V.draw_gear(img, active, pressed))

    def _draw_game_btn(self):
        img = self.s.img
        pressed = self.pressed == ('game', 0)
        self._put('gamebtn', pressed, V.GAME_SLOT, lambda: V.draw_game_btn(img, pressed))

    def _net_info(self):
        """(adress till redigeringssidan, IP, port) eller (None, None, None) om dash inte vet sin adress."""
        url = self.hints.get('edit_url')
        url = url() if callable(url) else url
        if not url:
            return None, None, None
        host = url.split('//', 1)[-1]
        ip, _, port = host.rpartition(':')
        return url, (ip or host), port

    def _header(self, title, back_label):
        img = self.s.img

        def head():
            rect, xr = V.draw_back(img, back_label)
            self._back_rect = rect
            V.draw_dim_title(img, title, xr)
        self._put('head', (title, back_label), (0, 10, V.NAV_RECT[2], 82), head)
        hh = model.hhmm(self.now())
        self._put('clock', hh, V.CLOCK_RECT, lambda: V.draw_clock(img, hh))
        self._draw_gear(True)
        self._draw_game_btn()

    def _draw_settings(self):
        img = self.s.img
        self._header('Inställningar', 'Tillbaka')
        url, ip, port = self._net_info()
        self._put('scard', (url, ip, port), V.SET_LEFT, lambda: V.draw_settings_left(img, url, ip, port))
        version = self._version_text()
        for name in V.SBTN_ORDER:
            pr = self.pressed == ('sbtn', name)
            hint = version if name == 'update' else None
            self._put(('sbtn', name), (pr, hint), V.SBTN[name],
                      lambda name=name, pr=pr, hint=hint: V.draw_settings_button(img, name, pr, hint))
        avail = self._sliders_on()
        self._put('sliders', avail, V.SET_SLIDERS, lambda: V.draw_sliders_card(img, avail))
        if avail:
            for row in (0, 1):
                idx, act = self._sset_idx(row), self.slider_active == row
                self._put(('srow', row), (idx, act), V.SLIDER_ROW_RECT[row],
                          lambda row=row, idx=idx, act=act: V.draw_slider_row(img, row, idx, act))
        self._draw_footer(self.now())

    def _draw_confirm(self):
        img = self.s.img
        kind = self.confirm_kind
        self._header('Inställningar', 'Tillbaka')
        pr = self.pressed[1] if (self.pressed and self.pressed[0] == 'cbtn') else None
        ip = self._net_info()[1]
        self._put('confirm', (kind, ip), (0, 84, W, 564), lambda: V.draw_confirm_card(img, kind, ip))
        self._put('cbtns', (kind, pr), V.CBTN_AREA, lambda: V.draw_confirm_buttons(img, kind, pr))
        self._draw_footer(self.now())

    def _draw_bye(self):
        img = self.s.img
        kind, failed = self.confirm_kind, self.bye_failed
        ip = self._net_info()[1]
        self._put('head', ('bye',), (0, 10, W, 82), lambda: V.clear(img, 0, 10, W, 82))
        st = self.update_state
        if kind == 'update':
            st = st or {'kind': 'busy', 'title': 'Söker efter ny version …', 'sub': '', 'done': False}
            key = (kind, st['kind'], st['title'], st['sub'], bool(st.get('done')))
            self._put('bye', key, (0, 84, W, 564), lambda: V.draw_update_status(img, st))
        else:
            self._put('bye', (kind, failed, ip), (0, 84, W, 564), lambda: V.draw_bye(img, kind, failed, ip))
        self._draw_footer(self.now())

    def _open_settings(self):
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        self.screen = 'settings'
        self.touch = None
        self.pressed = None
        self.drag_pct = None
        self.render_all()
        self._arm_dim_timer()

    def _close_settings(self):
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        if self.screen not in ('settings', 'confirm'):
            return
        self.screen = 'tab'
        self.touch = None
        self.pressed = None
        self.render_all()

    def _open_confirm(self, kind):
        self.confirm_kind = kind
        self.screen = 'confirm'
        self.touch = None
        self.pressed = None
        self.render_all()
        self._arm_dim_timer()

    def _back_to_settings(self):
        self.screen = 'settings'
        self.touch = None
        self.pressed = None
        self.render_all()
        self._arm_dim_timer()

    def _do_power(self, kind):
        """Bekräftad omstart/avstängning: visa det på skärmen och be systemet göra det (ren nedstängning)."""
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        self.confirm_kind = kind
        self.screen = 'bye'
        self.bye_failed = False
        self.touch = None
        self.pressed = None
        self.log('%s från skärmen' % {'reboot': 'omstart begärd', 'poweroff': 'avstängning begärd',
                                       'quit': 'avslut av panelen begärt'}.get(kind, kind))
        self.render_all()
        self.loop.create_task(self._run_power(kind))

    async def _run_power(self, kind):
        fn = self.hints.get('power')
        ok = False
        if fn is not None:
            try:
                ok = await fn(kind)
            except Exception as e:
                self.log('fel vid %s: %r' % (kind, e))
        if ok or self._stopped or self.screen != 'bye':
            return          # systemd stänger nu ned systemet och stoppar panelen
        self.bye_failed = True
        self.render_all()
        self._bye_timer = self.loop.call_later(BYE_FAIL_SECONDS, self._bye_back)

    def _bye_back(self):
        self._bye_timer = None
        if self.screen == 'bye' and not self._stopped:
            self.bye_failed = False
            self.update_state = None
            self._back_to_settings()

    # ------------------------------------------------------------ uppdatera (knappen på inställningssidan)
    def _version_text(self):
        u = self.updater
        if u is None:
            return 'Version %s' % __version__
        try:
            return u.version_text()
        except Exception as e:      # ska aldrig fälla panelen
            self.log('kunde inte läsa versionen:', repr(e))
            return 'Version %s' % __version__

    def _do_update(self):
        """Bekräftad uppdatering: visa det på skärmen och starta uppdateraren (dash-update apply) som egen tjänst. Finns
        en ny version startar uppdateraren om panelen; den nya panelen visar sedan resultatet (_resume_update)."""
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        self.confirm_kind = 'update'
        self.screen = 'bye'
        self.bye_failed = False
        self.update_state = {'kind': 'busy', 'title': 'Söker efter ny version …',
                             'sub': 'Finns en ny version installeras den och panelen startar om av sig själv.',
                             'done': False}
        self.touch = None
        self.pressed = None
        self.log('uppdatering begärd från skärmen')
        self.render_all()
        self.loop.create_task(self._start_update())

    async def _start_update(self):
        u = self.updater
        res = ('missing', 'Uppdateringen är inte tillgänglig här.')
        if u is not None:
            try:
                res = await u.start()
            except Exception as e:      # ska aldrig fälla panelen
                self.log('fel vid start av uppdateringen: %r' % (e,))
                res = ('error', 'Kunde inte starta uppdateringen.')
        if self._stopped or self.screen != 'bye' or self.update_state is None or self.update_state.get('done'):
            return
        if res[0] in ('started', 'busy'):
            self._update_t0 = self.loop.time()
            self._arm_update_poll()
        else:
            self._update_result({'kind': 'failed', 'title': 'Det gick inte att uppdatera', 'sub': res[1]})

    def _arm_update_poll(self):
        if self._update_timer is not None:
            self._update_timer.cancel()
        self._update_timer = self.loop.call_later(UPDATE_POLL_SECONDS, self._update_tick)

    def _update_tick(self):
        self._update_timer = None
        st = self.update_state
        if self._stopped or self.screen != 'bye' or not st or st.get('done') or self.updater is None:
            return
        u = self.updater
        try:
            rc = u.finished()
            if rc is not None:
                self._update_result(u.outcome(rc))
                return
            prog = u.progress()
        except Exception as e:      # ska aldrig fälla panelen
            self.log('fel när uppdateringen lästes av: %r' % (e,))
            prog = None
        if prog and (prog['title'], prog['sub']) != (st['title'], st['sub']):
            st['title'], st['sub'] = prog['title'], prog['sub']
            self.request_refresh()
        if self.loop.time() - self._update_t0 > UPDATE_TIMEOUT:
            self._update_result(u.timeout_outcome())
            return
        self._arm_update_poll()

    def _update_result(self, res):
        """Visar hur uppdateringen gick (tills man trycker, eller UPDATE_RESULT_SECONDS) och glömmer att den pågick."""
        if self._update_timer is not None:
            self._update_timer.cancel()
            self._update_timer = None
        self.confirm_kind = 'update'
        self.screen = 'bye'
        self.update_state = {'kind': res['kind'], 'title': res['title'], 'sub': res['sub'], 'done': True}
        self.touch = None
        self.pressed = None
        if self.updater is not None:
            try:
                self.updater.clear()
            except Exception as e:
                self.log('kunde inte städa efter uppdateringen: %r' % (e,))
        self.log('uppdatering: %s (%s)' % (res['kind'], res['sub']))
        self.render_all()
        if self._bye_timer is not None:
            self._bye_timer.cancel()
        self._bye_timer = self.loop.call_later(UPDATE_RESULT_SECONDS, self._bye_back)

    def _update_close(self):
        if self._bye_timer is not None:
            self._bye_timer.cancel()
            self._bye_timer = None
        self._bye_back()

    def _resume_update(self):
        """Vid start: har den här panelen själv startat en uppdatering som ännu inte visats (uppdateraren startar om
        panelen mitt i uppdateringen) visas hur det går, eller hur det gick, i stället för flikarna."""
        u = self.updater
        if u is None:
            return
        try:
            pend = u.pending()
            if not pend:
                return
            rc = u.finished()
            if rc is not None:
                res = u.outcome(rc)
            else:
                prog = u.progress()
                res = {'kind': 'busy', 'title': prog['title'], 'sub': prog['sub']}
        except Exception as e:      # ska aldrig fälla panelen
            self.log('kunde inte ta upp en pågående uppdatering: %r' % (e,))
            return
        self.confirm_kind = 'update'
        self.screen = 'bye'
        self.bye_failed = False
        if res['kind'] == 'busy':
            self.update_state = {'kind': 'busy', 'title': res['title'], 'sub': res['sub'], 'done': False}
            self._update_t0 = self.loop.time()
            self._arm_update_poll()
        else:
            self._update_result(res)

    # ------------------------------------------------------------ spelen (väljaren och spelfilerna)
    # Spelikonen öppnar spelväljaren (gamepick.py), som visar de spel som finns som filer i spelmappen (gamelib.py);
    # ett tryck på ett spel öppnar det. Väljaren och spelen är "spelskärmar" som får draw(gen) och on_touch(kind, x, y)
    # medan de visas (screen == 'game', self.game är den som visas); allt annat i panelen går vidare i bakgrunden
    # (Home Assistant, klockan, skärmsläck). Tillbaka i ett spel går till väljaren, Tillbaka i väljaren till flikarna.
    def _open_game(self):
        """Spelikonen bredvid kugghjulet (från flikarna, dimvyn och inställningarna): öppnar spelväljaren."""
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        if not self._switch_game('picker'):
            self._arm_dim_timer()               # kvar på sidan där ikonen trycktes
            self.request_refresh(urgent=True)

    def _make_game(self, kind):
        hooks = {'refresh': lambda urgent=False: self.request_refresh(urgent),
                 'clock': lambda: model.hhmm(self.now()),
                 'log': self.log,
                 'fail': self._game_failed}
        if kind == 'picker':
            from .gamepick import GamePicker
            hooks.update({'exit': self._close_game, 'pick': self._pick_game})
            ctx = gamesdk.GameContext(self.loop, self.s, {'api': gamesdk.API, 'id': 'picker', 'name': 'Spel'},
                                      hooks=hooks)
            return GamePicker(ctx, self.library, self.game_sync)
        info = self.library.get(kind)
        if info is None:
            raise ValueError('okänt spel: %r' % (kind,))
        hooks['exit'] = self._game_to_picker
        return self.library.make_game(info, self.s, self.loop, hooks)

    def _drop_game(self, kind):
        """Glömmer den skapade skärmen för kind (efter att den sparat sig)."""
        scr = self._games.pop(kind, None)
        if scr is not None:
            try:
                scr.stop()
            except Exception as e:
                self.log('kunde inte spara spelet (%s):' % kind, repr(e))

    def _fresh_game(self, kind):
        """Skärmen för kind, ny om spelfilen ändrats eller tagits bort sedan den skapades (en hämtning av spel)."""
        scr = self._games.get(kind)
        if scr is not None and kind != 'picker':
            info = self.library.get(kind)
            if info is None or getattr(scr, '_lib_key', None) != info.key:
                self._drop_game(kind)
                scr = None
        if scr is None:
            scr = self._make_game(kind)
            self._games[kind] = scr
        return scr

    def _switch_game(self, kind):
        """Visar spelskärmen kind ('picker' eller ett spels id) och stänger den som visades (den sparar sig själv).
        Ger False, och lämnar allt som det var, om den inte gick att öppna."""
        prev = self.game
        try:
            scr = self._fresh_game(kind)
            if prev is not None and prev is not scr:
                try:
                    prev.save_now()             # väljaren läser sparfilerna när den öppnas: spara det som visas först
                except Exception:
                    self.log('kunde inte spara spelet (%s):\n%s' % (self.game_kind, traceback.format_exc()))
            scr.open()
        except Exception:
            self.log('kunde inte öppna spelet (%s):\n%s' % (kind, traceback.format_exc()))
            self._games.pop(kind, None)
            return False
        if prev is not None and prev is not scr:
            try:
                prev.close()
            except Exception:
                self.log('fel när spelet stängdes:\n' + traceback.format_exc())
        self.game, self.game_kind = scr, kind
        self.screen = 'game'
        self.touch = None
        self.pressed = None
        self.drag_pct = None
        self.slider_active = None
        if kind == 'picker':                    # väljaren har just sökt igenom mappen: släpp spel som försvunnit
            for k in list(self._games):
                if k != 'picker' and self.library.get(k) is None:
                    self._drop_game(k)
        self.render_all()
        self._arm_dim_timer()
        return True

    def _pick_game(self, kind):
        """Ett spel valdes i väljaren."""
        if not self._switch_game(kind):
            self.request_refresh(urgent=True)   # kvar i väljaren (felet är loggat)

    def _game_to_picker(self):
        """Tillbaka i ett spel: till spelväljaren (och till flikarna om den inte går att öppna)."""
        if not self._switch_game('picker'):
            self._close_game()

    def _close_game(self):
        """Lämnar spelen (väljaren eller ett spel) och visar flikarna."""
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        if self.screen != 'game':
            return
        try:
            self.game.close()
        except Exception:
            self.log('fel när spelet stängdes:\n' + traceback.format_exc())
        self.screen = 'tab'
        self.touch = None
        self.pressed = None
        self.render_all()

    def _game_failed(self):
        """Något gick fel i spelet: tillbaka till flikarna, spelet nollställs (panelen ska aldrig falla för ett spel)."""
        self.log('fel i spelet, tillbaka till flikarna:\n' + traceback.format_exc())
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        g, kind = self.game, self.game_kind
        self.game, self.game_kind = None, None
        self._games.pop(kind, None)
        if g is not None:
            try:
                g.quarantine()
            except Exception:
                pass
        self.screen = 'tab'
        self.touch = None
        self.pressed = None
        self.loop.call_soon(self.render_all)

    def _draw_game(self):
        try:
            self.game.draw(self._render_gen)
        except Exception:
            self._game_failed()

    def _game_touch(self, kind, x, y):
        try:
            self.game.on_touch(kind, x, y)
        except Exception:
            self._game_failed()

    # ------------------------------------------------------------ Wi-Fi-styrka
    def _read_wifi(self):
        fn = self.hints.get('wifi_pct')
        if fn is None:
            return None
        try:
            return fn()
        except Exception as e:      # ska aldrig fälla panelen
            self.log('kunde inte läsa Wi-Fi-styrkan:', repr(e))
            return None

    def _wifi_tick(self):
        if self._wifi_timer is not None:
            self._wifi_timer.cancel()
        self._wifi_timer = None
        if self._stopped:
            return
        pct = self._read_wifi()
        if pct != self._wifi_pct:
            self._wifi_pct = pct
            self.request_refresh()
        self._wifi_timer = self.loop.call_later(WIFI_INTERVAL, self._wifi_tick)

    # ------------------------------------------------------------ batteri
    def _read_batt(self):
        fn = self.hints.get('battery')
        if fn is None:
            return None
        try:
            return fn()
        except Exception as e:      # ska aldrig fälla panelen
            self.log('kunde inte läsa batteriet:', repr(e))
            return None

    def _batt_tick(self):
        if self._batt_timer is not None:
            self._batt_timer.cancel()
        self._batt_timer = None
        if self._stopped:
            return
        b = self._read_batt()
        if b != self._batt:
            self._batt = b
            self.request_refresh()
        self._batt_timer = self.loop.call_later(BATT_INTERVAL, self._batt_tick)

    # ------------------------------------------------------------ skärmen: ljusstyrka, släcka och väcka
    def _sliders_on(self):
        """Reglagen visas bara om bakgrundsbelysningen går att styra."""
        return self.display is not None and self.display.can_blank

    def _sset_idx(self, row):
        d = self.display
        if d is None:
            return 0
        return V.slider_idx_of(row, d.brightness if row == 0 else d.off_after)

    def _sset_move(self, row, x):
        """Fingret ligger på ett av reglagen på inställningssidan: ljusstyrkan syns direkt, släcktiden gäller när
        fingret lyfts."""
        d = self.display
        if d is None:
            return
        idx = V.slider_idx_at(row, x)
        changed = idx != self._sset_idx(row)
        if changed:
            v = V.slider_value(row, idx)
            if row == 0:
                d.set_brightness(v)
            else:
                d.set_off_after(v)
        if changed or self.slider_active != row:
            self.slider_active = row
            self.request_refresh()

    def _sset_up(self, row):
        self.slider_active = None
        d = self.display
        if d is not None:
            d.save()
            self._arm_off_timer()               # en ny släcktid gäller från nu
        self.request_refresh(urgent=True)

    def _arm_off_timer(self):
        """Släcker skärmen när off_after sekunder gått sedan senaste trycket (kollar i klockan när tiden är ute,
        så trycken i sig inte behöver röra timern)."""
        if self._off_timer is not None:
            self._off_timer.cancel()
            self._off_timer = None
        d = self.display
        if d is None or not d.can_blank or self.screen_off or self._stopped:
            return
        delay = max(0.05, self._last_touch + d.off_after - self.loop.time())
        self._off_timer = self.loop.call_later(delay, self._off_tick)

    def _off_tick(self):
        self._off_timer = None
        d = self.display
        if self._stopped or d is None or self.screen_off:
            return
        if (self.loop.time() - self._last_touch + 0.02 < d.off_after or self.slider_active is not None
                or self.screen == 'bye'):
            self._arm_off_timer()               # trycktes nyss, ett reglage dras eller enheten stängs ned: vänta
            return
        self._go_dark()

    def _go_dark(self):
        """Släcker skärmen. Först tillbaka till flikarna, så att nästa tryck möter en lugn skärm och inte en fråga
        om omstart eller ett reglage."""
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        if self.screen not in ('tab', 'game'):          # spelet står kvar (ofarligt att trycka i, sparas om det lämnas)
            self.screen = 'tab'
            self.touch = None
            self.pressed = None
            self.drag_pct = None
            self.slider_active = None
            self.render_all()
        self.screen_off = True
        self.display.screen_off()

    def _wake(self):
        self.screen_off = False
        if self.display is not None:
            self.display.screen_on()
        self._arm_off_timer()

    # ------------------------------------------------------------ åtgärder
    def _toggle(self, item):
        inf = self.lamp_info(item)
        if inf['state'] not in ('on', 'off'):
            self.request_refresh(urgent=True)
            return
        self._command([inf['eid']], inf['state'] != 'on')

    def _toggle_all(self, tab):
        infos = [self.lamp_info(it) for it in tab['items']]
        avail = [i for i in infos if i['state'] in ('on', 'off')]
        if not avail:
            self.request_refresh(urgent=True)
            return
        any_on = any(i['state'] == 'on' for i in avail)
        self._command([i['eid'] for i in avail], not any_on)

    def _open_dim(self, item):
        self.dim_eid = item['entity_id']
        self.dim_tab = self.tab_idx
        self.screen = 'dim'
        self.drag_pct = None
        self.render_all()
        self._arm_dim_timer()

    def _close_dim(self):
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        if self.screen != 'dim':
            return
        self.screen = 'tab'
        self.touch = None
        self.pressed = None
        self.drag_pct = None
        self.render_all()

    def _arm_dim_timer(self):
        """Tomgångstimer för dimvyn och inställningarna: efter dim_timeout sekunder utan tryck tillbaka till flikarna."""
        if self._dim_timer is not None:
            self._dim_timer.cancel()
            self._dim_timer = None
        if self.screen in ('dim', 'settings', 'confirm') and self.dim_timeout > 0:
            self._dim_timer = self.loop.call_later(self.dim_timeout, self._idle_back)
        elif self.screen == 'game':
            self._dim_timer = self.loop.call_later(GAME_IDLE_SECONDS, self._idle_back)

    def _idle_back(self):
        self._dim_timer = None
        if self.screen == 'dim':
            self._close_dim()
        elif self.screen in ('settings', 'confirm'):
            self._close_settings()
        elif self.screen == 'game':
            self._close_game()

    def _step(self, item, sign):
        inf = self.lamp_info(item)
        if inf['state'] == 'off':
            if sign < 0:
                return
            pct = self.last_pct.get(inf['eid'])
        else:
            base = self.drag_pct or inf['pct'] or self.last_pct.get(inf['eid']) or 50
            pct = max(1, min(100, base + sign * self.step))
        self._command([inf['eid']], True, pct)

    # reglaget
    @staticmethod
    def _slider_pct(y):
        x0, y0, x1, y1 = V.SLIDER_RECT
        inner = (y1 - 1) - (y0 + 1)
        pct = int(round(((y1 - 1) - y) * 100.0 / inner))
        return max(1, min(100, pct))

    def _slider_move(self, y):
        pct = self._slider_pct(y)
        if pct == self.drag_pct:
            return
        self.drag_pct = pct
        self._maybe_send_drag()
        self.request_refresh()

    def _maybe_send_drag(self):
        pct = self.drag_pct
        found = self._find_item(self.dim_eid)
        if pct is None or found is None or pct == self._sent_pct:
            return
        now = self.loop.time()
        if now - self._sent_t >= SEND_MIN_INTERVAL:
            self._sent_t, self._sent_pct = now, pct
            self._command([found[1]['entity_id']], True, pct, urgent=False)
        elif self._drag_timer is None:
            self._drag_timer = self.loop.call_later(SEND_MIN_INTERVAL - (now - self._sent_t), self._drag_tick)

    def _drag_tick(self):
        self._drag_timer = None
        if self.touch is not None and self.touch['t'][0] == 'slider':
            self._maybe_send_drag()

    def _slider_up(self):
        if self._drag_timer is not None:
            self._drag_timer.cancel()
            self._drag_timer = None
        pct = self.drag_pct
        found = self._find_item(self.dim_eid)
        if pct is not None and found is not None and pct != self._sent_pct:
            self._command([found[1]['entity_id']], True, pct, urgent=False)
        self.drag_pct = None
        self._sent_pct = None
        self.request_refresh(urgent=True)

    # ------------------------------------------------------------ kommandon till Home Assistant
    def _command(self, eids, on, pct=None, urgent=True):
        """Ändrar skärmen direkt (väntande läge) och ber Home Assistant utföra det. Återställs vid fel eller om
        Home Assistant inte bekräftat inom confirm_timeout. Vid tändning utan angiven ljusstyrka skickas den
        senast kända ljusstyrkan för varje dimbar lampa (annars tänder många lampor på 100 %)."""
        if not eids:
            return
        self._seq += 1
        seq = self._seq
        deadline = self.loop.time() + self.confirm
        groups = {}
        for e in eids:
            dom = e.split('.', 1)[0]
            p = None
            if on and dom == 'light':
                if pct is not None:
                    p = pct
                elif self._is_dimmable(e):
                    p = self.last_pct.get(e)
            if p is not None:
                self._set_pct(e, p)
            self.pending[e] = {'state': 'on' if on else 'off', 'pct': p, 'deadline': deadline, 'seq': seq}
            groups.setdefault((dom, p), []).append(e)
        self._arm_pending_timer()
        self.request_refresh(urgent=urgent)
        for (dom, p), ids in groups.items():
            data = {'brightness_pct': p} if p is not None else None
            self.loop.create_task(self._send(dom, 'turn_on' if on else 'turn_off', ids, data, seq))

    async def _send(self, domain, service, ids, data, seq):
        try:
            ok = await self.call_service(domain, service, ids, data)
        except Exception as e:      # ska aldrig fälla panelen
            self.log('fel vid anrop till Home Assistant:', repr(e))
            ok = False
        if not ok:
            changed = False
            for e in ids:
                p = self.pending.get(e)
                if p is not None and p['seq'] == seq:
                    del self.pending[e]
                    changed = True
            if changed:
                self._arm_pending_timer()
                self.request_refresh(urgent=True)

    def _arm_pending_timer(self):
        if self._pending_timer is not None:
            self._pending_timer.cancel()
            self._pending_timer = None
        if not self.pending or self._stopped:
            return
        nxt = min(p['deadline'] for p in self.pending.values())
        self._pending_timer = self.loop.call_later(max(0.0, nxt - self.loop.time()) + 0.01, self._pending_tick)

    def _pending_tick(self):
        self._pending_timer = None
        now = self.loop.time()
        expired = [e for e, p in self.pending.items() if p['deadline'] <= now]
        for e in expired:
            del self.pending[e]
        self._arm_pending_timer()
        if expired:
            self.log('ingen bekräftelse från Home Assistant, återställer:', ', '.join(sorted(expired)))
            self.request_refresh(urgent=True)
