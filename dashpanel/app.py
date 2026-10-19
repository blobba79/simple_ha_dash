"""Startpunkt: kopplar ihop skärm, pek, Home Assistant, gränssnitt och (senare) redigeringssidan.

Miljövariabler (för prov och demo; på dash behövs inga):
  DASH_CONFIG  sökväg till konfigurationen   (standard /etc/dash-panel/config.json)
  DASH_FB      framebuffer, eller "none"     (standard /dev/fb0)
  DASH_INPUT   pekenhet, eller "none"        (standard: hittas på namnet, silead_ts)
  DASH_TOUCH_CAL  pekkalibrering             (standard /etc/dash-panel/touch.json)
  DASH_STATE   minne för ljusstyrka, eller "none" (standard /var/lib/dash-panel/state.json)
  DASH_SETTINGS  skärminställningar (ljusstyrka, släcktid), eller "none"  (standard /var/lib/dash-panel/settings.json)
  DASH_BACKLIGHT bakgrundsbelysningens katalog i sysfs, eller "none"       (standard: hittas under /sys/class/backlight)
  DASH_BATTERY batteriets katalog i sysfs, eller "none"                   (standard: hittas under /sys/class/power_supply)
  DASH_GAMES   spelmappen (en fil per spel, se games/SKAPA-SPEL.md), eller "none"  (standard /var/lib/dash-panel/games)
  DASH_GAMEDATA spelens sparfiler (rekord, pågående spel), eller "none"       (standard /var/lib/dash-panel/game-data)
  DASH_GAMES_RUN katalog för resultatfilerna när spel hämtas (knappen Uppdatera spel)   (standard /run)
  DASH_UPDATE_BIN   uppdateraren (knappen Uppdatera), eller "none"       (standard /usr/local/sbin/dash-update)
  DASH_UPDATE_RUN   katalog för uppdateringens resultatfiler           (standard /run)
  DASH_UPDATE_MARKER  minne av en pågående uppdatering, eller "none"    (standard /var/lib/dash-panel/update.json)
Avslutas snabbt på SIGTERM (annars hänger nedstängningen). SIGHUP läser om konfigurationen."""
import asyncio
import os
import signal
import socket
import sys
import time
import traceback

from . import (battery as batterymod, config as cfgmod, console, display as displaymod, gamelib, gamesync, sysinfo,
               updater as updatermod)
from .ha import HASession
from .surface import FbSink, NullSink, Surface
from .touch import Calibration, TouchReader, find_touch_device
from .ui import Panel


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def sd_notify(msg):
    """Talar om för systemd att vi lever (READY, WATCHDOG, STOPPING). Gör ingenting utan systemd."""
    path = os.environ.get('NOTIFY_SOCKET')
    if not path:
        return
    if path[0] == '@':
        path = '\0' + path[1:]
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            s.connect(path)
            s.send(msg.encode())
        finally:
            s.close()
    except OSError:
        pass


def local_ip(peer_host):
    """Egen adress på det nät som når Home Assistant (inget skickas)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((peer_host or '192.0.2.1', 9))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


class App(object):
    def __init__(self, loop, config_path=None, fb=None, input_path=None, cal_path=None, console_ctl=True,
                 now_fn=None, state_path=None, settings_path=None, backlight_path=None, battery_path=None):
        self.loop = loop
        self.config_path = config_path or os.environ.get('DASH_CONFIG', cfgmod.DEFAULT_PATH)
        self.fb = fb or os.environ.get('DASH_FB', '/dev/fb0')
        self.input_path = input_path or os.environ.get('DASH_INPUT') or find_touch_device()
        self.cal_path = cal_path or os.environ.get('DASH_TOUCH_CAL', '/etc/dash-panel/touch.json')
        self.state_path = state_path or os.environ.get('DASH_STATE', '/var/lib/dash-panel/state.json')
        # utan riktig skärm (fb "none", prov och demo) rör vi varken /sys eller /var/lib om inget uttryckligen anges
        headless = self.fb == 'none'
        self.settings_path = settings_path or os.environ.get('DASH_SETTINGS') or ('none' if headless else displaymod.DEFAULT_SETTINGS)
        self.backlight_path = backlight_path or os.environ.get('DASH_BACKLIGHT') or ('none' if headless else None)
        # batteriet: utan riktig skärm visas inget (provens facitbilder ska inte påverkas av datorns eget batteri)
        self.battery_path = battery_path or os.environ.get('DASH_BATTERY') or ('none' if headless else None)
        # spelen: utan riktig skärm (prov och demo) finns ingen spelmapp, inga sparfiler och ingen hämtning från GitHub
        self.games_dir = os.environ.get('DASH_GAMES') or ('none' if headless else gamelib.GAMES_DIR)
        self.gamedata_dir = os.environ.get('DASH_GAMEDATA') or ('none' if headless else gamelib.DATA_DIR)
        self.game_sync = None if self.games_dir == 'none' else gamesync.GameSync(
            games_dir=self.games_dir, run_dir=os.environ.get('DASH_GAMES_RUN') or gamesync.RUN_DIR)
        # uppdateringsknappen: utan riktig skärm (prov och demo) finns ingen uppdaterare och inget rörs i /run eller /var/lib
        ubin = os.environ.get('DASH_UPDATE_BIN') or ('none' if headless else updatermod.UPDATE_BIN)
        self.updater = updatermod.Updater(
            update_bin=None if ubin == 'none' else ubin,
            run_dir=os.environ.get('DASH_UPDATE_RUN') or updatermod.RUN_DIR,
            marker=os.environ.get('DASH_UPDATE_MARKER') or ('none' if headless else updatermod.MARKER))
        self.console_ctl = console_ctl
        self.now_fn = now_fn
        self.stop_event = asyncio.Event()
        self.cfg = None
        self.panel = None
        self.ha = None
        self.surface = None
        self.touch = None
        self.editor = None
        self._console_released = False
        self._tasks = []
        self._cfg_sig = None
        self.log_fn = log
        self.wifi = sysinfo.WifiMeter()
        self.battery = batterymod.BatteryMeter(path=self.battery_path)
        self.display = None

    # ------------------------------------------------------------ start och stopp
    async def start(self):
        cfg, warns = cfgmod.load(self.config_path)
        for w in warns:
            log('konfiguration:', w)
        self.cfg = cfg
        self._cfg_sig = self._sig()
        sink = NullSink() if self.fb == 'none' else FbSink(self.fb)
        self.surface = Surface(sink)
        if self.fb != 'none' and self.console_ctl:
            self._console_released = console.release_console()
            log('konsol bortkopplad:', self._console_released)
        bl = None if self.backlight_path is None else displaymod.Backlight(
            None if self.backlight_path == 'none' else self.backlight_path, log)
        self.display = displaymod.Display(backlight=bl, path=self.settings_path, log=log)
        log('skärm:', self.display.describe())
        self.panel = Panel(self.loop, self.surface, cfg, lambda *a: self.ha.call_service(*a),
                           now_fn=self.now_fn, log=log, state_path=self.state_path,
                           hints={'edit_url': self.edit_url, 'wifi_pct': self.wifi.percent, 'power': self.power,
                                  'display': self.display, 'battery': self.battery.sample,
                                  'games_dir': self.games_dir, 'gamedata_dir': self.gamedata_dir,
                                  'game_sync': self.game_sync,
                                  'updater': self.updater, 'ha': lambda: self.ha})
        self.ha = HASession(self.loop, cfg['ha']['url'], cfg['ha']['token_file'], self.panel.on_ha_status,
                            self.panel.on_ha_full, self.panel.on_ha_update, log=log,
                            hb_interval=cfg['ui']['heartbeat'])
        self.panel.start()
        if self.input_path != 'none' and os.path.exists(self.input_path):
            calib = Calibration.load(self.cal_path)
            if not os.path.exists(self.cal_path):
                log('pekkalibrering saknas (%s), använder standardvärden' % self.cal_path)
            self.touch = TouchReader(self.loop, self.input_path, calib, self._on_touch)
        self.ha.set_entities(cfgmod.entity_ids(cfg))
        self.ha.start()
        await self._start_editor()
        self._tasks.append(self.loop.create_task(self._watch_config()))
        self._tasks.append(self.loop.create_task(self._watchdog()))
        sd_notify('READY=1')
        log('panelen startad')

    async def _start_editor(self):
        try:
            from .editor import EditServer
        except ImportError:
            return
        self.editor = EditServer(self.loop, self)
        try:
            await self.editor.start()
        except OSError as e:
            log('redigeringssidan kunde inte startas:', e)
            self.editor = None

    async def stop(self):
        sd_notify('STOPPING=1')
        for t in self._tasks:
            t.cancel()
        if self.panel:
            self.panel.stop()
        if self.display:
            self.display.restore()          # skärmen tänd och inställningarna sparade (konsolen ska synas efteråt)
        if self.touch:
            self.touch.close()
        if self.editor:
            try:
                await asyncio.wait_for(self.editor.stop(), 1.0)
            except Exception:
                pass
        if self.ha:
            try:
                await asyncio.wait_for(self.ha.stop(), 1.5)
            except Exception:
                pass
        if self.surface:
            self.surface.sink.close()
        if self._console_released:
            log('konsol tillbaka:', console.restore_console())
        log('panelen stoppad')

    async def run(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            self.loop.add_signal_handler(sig, self.stop_event.set)
        self.loop.add_signal_handler(signal.SIGHUP, self.reload_config)
        await self.start()
        await self.stop_event.wait()
        await self.stop()

    # ------------------------------------------------------------ pek, konfiguration, vakt
    def _on_touch(self, kind, x, y):
        try:
            self.panel.on_touch(kind, x, y)
        except Exception:
            log('fel i pekhanteringen:\n' + traceback.format_exc())

    def edit_url(self):
        host = self.cfg['ha']['url'].split('//', 1)[-1].split('/', 1)[0].split(':', 1)[0]
        ip = local_ip(host)
        return 'http://%s:%d' % (ip, self.cfg['ui']['edit_port']) if ip else None

    async def power(self, kind):
        """Starta om, stäng av eller avsluta panelen (reboot, poweroff, quit) via systemd. Anropas från
        inställningssidan efter bekräftelse."""
        return await sysinfo.run_power(kind, log)

    def apply_config(self, cfg):
        """Tar i bruk en ny konfiguration direkt (från redigeringssidan eller en ändrad fil)."""
        old = self.cfg
        self.cfg = cfg
        self.panel.set_config(cfg)
        self.ha.set_entities(cfgmod.entity_ids(cfg))
        if old and (old['ha'] != cfg['ha'] or old['ui']['edit_port'] != cfg['ui']['edit_port']
                    or old['ui']['heartbeat'] != cfg['ui']['heartbeat']):
            log('ändringar av ha, heartbeat eller edit_port kräver omstart av tjänsten (systemctl restart dash-panel)')

    def _sig(self):
        try:
            st = os.stat(self.config_path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def reload_config(self):
        cfg, warns = cfgmod.load(self.config_path)
        for w in warns:
            log('konfiguration:', w)
        self._cfg_sig = self._sig()
        self.apply_config(cfg)
        log('konfigurationen inläst')

    def note_saved(self):
        """Redigeringssidan har själv sparat filen: räkna inte det som en extern ändring."""
        self._cfg_sig = self._sig()

    async def _watch_config(self):
        while True:
            await asyncio.sleep(3.0)
            sig = self._sig()
            if sig != self._cfg_sig and sig is not None:
                await asyncio.sleep(0.3)        # låt en pågående skrivning bli klar
                try:
                    self.reload_config()
                except Exception:
                    log('kunde inte läsa om konfigurationen:\n' + traceback.format_exc())

    async def _watchdog(self):
        usec = os.environ.get('WATCHDOG_USEC')
        interval = max(1.0, int(usec) / 2e6) if (usec and usec.isdigit()) else 10.0
        while True:
            sd_notify('WATCHDOG=1')
            await asyncio.sleep(interval)


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = App(loop)
    try:
        loop.run_until_complete(app.run())
    finally:
        loop.close()


if __name__ == '__main__':
    main()
