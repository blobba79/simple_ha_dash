"""Sidan för redigering (HTML, CSS och JavaScript som text). Inget laddas utifrån: allt serveras av panelen."""

INDEX_HTML = r'''<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Panelinställningar</title>
<link rel="stylesheet" href="/app.css">
</head>
<body>
<header><h1>Panelinställningar</h1><span id="conn" class="badge"></span></header>
<main id="app"><p class="muted">Laddar …</p></main>
<div id="bar"><span id="msg"></span><button id="save" class="primary" type="button" disabled>Spara</button></div>
<script src="/app.js"></script>
</body>
</html>
'''

APP_CSS = r'''
:root { --bg:#111; --card:#1c1c1c; --line:#2c2c2c; --text:#e1e1e1; --muted:#9b9b9b; --blue:#03a9f4; --blue-l:#4fc3f7;
        --blue-d:#0b4a6e; --warn:#ffa726; --bad:#ef5350; --ok:#66bb6a; }
* { box-sizing: border-box; }
html { background: var(--bg); }
body { margin: 0; padding: 0 0 84px; background: var(--bg); color: var(--text);
       font: 16px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; padding: 14px 16px; position: sticky; top: 0;
         background: var(--bg); border-bottom: 1px solid var(--line); z-index: 5; }
h1 { margin: 0; font-size: 20px; font-weight: 500; flex: 1; }
h2 { margin: 0 0 10px; font-size: 17px; font-weight: 500; }
h3 { margin: 16px 0 8px; font-size: 15px; font-weight: 500; color: var(--muted); }
main { max-width: 760px; margin: 0 auto; padding: 12px 12px 0; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px; margin: 0 0 14px; }
.muted { color: var(--muted); } .small { font-size: 13px; } .warn { color: var(--warn); } .bad { color: var(--bad); }
.badge { font-size: 13px; padding: 4px 10px; border-radius: 12px; border: 1px solid var(--line); color: var(--muted); }
.badge.ok { color: var(--blue-l); border-color: var(--blue-d); } .badge.bad { color: var(--warn); border-color: #5a3d12; }
button, select, input { font: inherit; color: var(--text); background: #242424; border: 1px solid var(--line); border-radius: 10px;
        min-height: 40px; padding: 6px 12px; }
input[type=text], input[type=search] { width: 100%; }
button { cursor: pointer; }
button:disabled { opacity: .45; cursor: default; }
button.primary { background: var(--blue-d); border-color: var(--blue); }
button.danger { border-color: #6a2b2b; color: #ff8a80; }
button.icon { min-width: 40px; padding: 6px 8px; }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 14px; align-items: center; }
.tab { border-radius: 12px; padding: 8px 14px; color: var(--muted); }
.tab.on { background: #0f2230; border-color: var(--blue); color: var(--text); }
.tab.add { border-style: dashed; }
.adding { display: inline-flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.row { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: end; margin: 0 0 10px; }
.row > label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--muted); flex: 1 1 160px; }
.row > label select, .row > label input { color: var(--text); font-size: 16px; }
.btns { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0 0; }
.item { display: grid; grid-template-columns: auto 1fr auto; gap: 6px 10px; align-items: center; padding: 10px 0;
        border-top: 1px solid var(--line); }
.item .pos { color: var(--muted); font-size: 13px; min-width: 56px; }
.item .meta { grid-column: 2 / 4; display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; color: var(--muted); align-items: center; }
.item .meta code { font-size: 12px; color: #8aa; word-break: break-all; }
.item .ctrl { display: flex; gap: 6px; }
.ph { color: var(--muted); font-style: italic; }
.plist { display: flex; flex-direction: column; margin: 8px 0 0; }
.pitem { display: flex; gap: 12px; align-items: center; padding: 8px 4px; border-top: 1px solid var(--line); cursor: pointer; }
.pitem input { width: 22px; height: 22px; min-height: 0; flex: none; accent-color: var(--blue); }
.pitem .t { flex: 1; min-width: 0; } .pitem .t div { overflow: hidden; text-overflow: ellipsis; }
.opt { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.opt input[type=checkbox] { width: 18px; height: 18px; min-height: 0; accent-color: var(--blue); }
.allopt { margin: 4px 0 12px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; }
.allopt .opt { margin-top: 0; }
.allopt .alltext { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--muted); margin-top: 8px; max-width: 360px; }
.allopt input[type=text]:disabled { opacity: .45; }
.allopt p { margin: 8px 0 0; }
.pitem .id { font-size: 12px; color: var(--muted); } .pitem .st { font-size: 13px; color: var(--muted); white-space: nowrap; }
@media (max-width: 560px) {
  .item { grid-template-columns: 1fr auto; }
  .item .pos { grid-column: 1 / 3; min-width: 0; }
  .item .meta { grid-column: 1 / 3; }
  .card { padding: 12px; }
}
#bar { position: fixed; left: 0; right: 0; bottom: 0; display: flex; gap: 12px; align-items: center; justify-content: flex-end;
       padding: 12px 16px; background: #161616; border-top: 1px solid var(--line); z-index: 6; }
#msg { flex: 1; font-size: 14px; }
#msg.ok { color: var(--ok); } #msg.bad { color: var(--bad); }
'''

APP_JS = r'''
'use strict';
(function () {
  var S = null, cfg = null, sel = 0, dirty = false, search = '', sensorMode = 'temp', showHidden = false, adding = false, confirmDel = false;
  var $app = document.getElementById('app'), $msg = document.getElementById('msg'), $save = document.getElementById('save'),
      $conn = document.getElementById('conn');
  var ICON_NAMES = { Lightbulb: 'Lampa', LightbulbMultiple: 'Flera lampor', Thermometer: 'Termometer' };

  function add(e, kid) {
    if (kid == null || kid === false) return;
    if (Array.isArray(kid)) { kid.forEach(function (k) { add(e, k); }); return; }
    e.appendChild(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  function h(tag, props) {
    var e = document.createElement(tag);
    props = props || {};
    Object.keys(props).forEach(function (k) {
      var v = props[k];
      if (v === false || v == null) return;
      if (k === 'class') e.className = v;
      else if (k.slice(0, 2) === 'on') e.addEventListener(k.slice(2), v);
      else if (k === 'value') e.value = v;
      else if (k === 'checked') e.checked = !!v;
      else if (k === 'disabled') e.disabled = !!v;
      else e.setAttribute(k, v === true ? '' : v);
    });
    for (var i = 2; i < arguments.length; i++) add(e, arguments[i]);
    return e;
  }
  function select(options, value, onchange) {
    var s = h('select', { onchange: function () { onchange(this.value); } });
    options.forEach(function (o) { s.appendChild(h('option', { value: o[0] }, o[1])); });
    s.value = String(value);
    return s;
  }
  function setDirty(v) {
    dirty = v;
    $save.disabled = !v;
    $msg.textContent = v ? 'Osparade ändringar' : '';
    $msg.className = v ? 'warn' : '';
  }
  function say(text, cls) { $msg.textContent = text; $msg.className = cls || ''; }
  function entMap() { var m = {}; ((S && S.entities) || []).forEach(function (e) { m[e.id] = e; }); return m; }
  function copy(o) { return JSON.parse(JSON.stringify(o)); }
  function limit(tab) {
    if (tab.type !== 'lights') return S.config.limits.sensors;
    return tab.show_all === false ? S.config.limits.lamps_no_all : S.config.limits.lamps;
  }

  // ---------------------------------------------------------------- ladda och spara
  function load() {
    return fetch('/api/state', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (s) {
      S = s; cfg = copy(s.config); if (sel >= cfg.tabs.length) sel = 0; setDirty(false); render();
    }).catch(function () { say('Kunde inte hämta inställningarna från panelen.', 'bad'); });
  }
  function reloadEntities() {
    return fetch('/api/state', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (s) {
      S.entities = s.entities; S.connected = s.connected; S.error = s.error; render();
    });
  }
  function save() {
    cfg.tabs.forEach(function (t) { t.items.forEach(function (it) { if (it.name === '') delete it.name; }); });
    $save.disabled = true; say('Sparar …');
    fetch('/api/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tabs: cfg.tabs, locale: cfg.locale, ui: cfg.ui }) })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (!res.ok) { say(res.error || 'Kunde inte spara.', 'bad'); $save.disabled = false; return; }
        S.config = res.config; cfg = copy(res.config); if (sel >= cfg.tabs.length) sel = 0; dirty = false; render();
        say('Sparat. Panelen har uppdaterats.' + (res.warnings && res.warnings.length ? ' Obs: ' + res.warnings.join('; ') : ''), 'ok');
        $save.disabled = true;
      })
      .catch(function () { say('Ingen kontakt med panelen.', 'bad'); $save.disabled = false; });
  }
  $save.addEventListener('click', save);
  window.addEventListener('beforeunload', function (e) { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

  // ---------------------------------------------------------------- flikar
  function renderTabs() {
    var row = h('div', { class: 'tabs' });
    cfg.tabs.forEach(function (t, i) {
      row.appendChild(h('button', { type: 'button', class: 'tab' + (i === sel ? ' on' : ''),
        onclick: function () { sel = i; adding = false; confirmDel = false; render(); } }, t.title || '(namnlös)'));
    });
    if (adding) {
      row.appendChild(h('span', { class: 'adding' }, 'Ny flik för:',
        h('button', { type: 'button', onclick: function () { newTab('lights'); } }, 'Lampor'),
        h('button', { type: 'button', onclick: function () { newTab('sensors'); } }, 'Temperaturer'),
        h('button', { type: 'button', onclick: function () { adding = false; render(); } }, 'Avbryt')));
    } else if (cfg.tabs.length < S.config.limits.tabs) {
      row.appendChild(h('button', { type: 'button', class: 'tab add', onclick: function () { adding = true; render(); } }, '+ Ny flik'));
    }
    return row;
  }
  function newTab(type) {
    var t = { id: 'flik' + (cfg.tabs.length + 1), title: type === 'lights' ? 'Lampor' : 'Temperaturer', type: type,
              icon: type === 'lights' ? 'Lightbulb' : 'Thermometer', items: [] };
    if (type === 'lights') { t.all_label = 'Alla lampor'; t.show_all = true; }
    cfg.tabs.push(t); sel = cfg.tabs.length - 1; adding = false; setDirty(true); render();
  }
  function moveTab(d) {
    var j = sel + d;
    if (j < 0 || j >= cfg.tabs.length) return;
    var t = cfg.tabs[sel]; cfg.tabs[sel] = cfg.tabs[j]; cfg.tabs[j] = t; sel = j; setDirty(true); render();
  }

  // Knappen "Alla lampor" sist på lampfliken: bockrutan väljer om den ska visas, fältet vad det står på den
  function renderAllOption(tab) {
    var on = tab.show_all !== false;
    var tooMany = !on && tab.items.length > S.config.limits.lamps;     // åtta lampor ryms bara utan knappen
    var cb = h('input', { type: 'checkbox', checked: on, disabled: tooMany, onchange: function () {
      tab.show_all = this.checked; setDirty(true); render(); } });
    var label = h('input', { type: 'text', value: tab.all_label || 'Alla lampor', maxlength: '24', disabled: !on,
      oninput: function () { tab.all_label = this.value; setDirty(true); } });
    return h('div', { class: 'allopt' },
      h('label', { class: 'opt' }, cb, 'Visa knappen som slår om alla lampor på fliken'),
      h('label', { class: 'alltext' }, 'Text på knappen', label),
      tooMany ? h('p', { class: 'warn small' }, 'Fliken har ' + tab.items.length + ' lampor. Ta bort en lampa först om knappen ska visas igen (högst '
        + S.config.limits.lamps + ' då).') : null);
  }

  function renderTabEditor(tab) {
    var card = h('section', { class: 'card' });
    card.appendChild(h('h2', null, tab.type === 'lights' ? 'Flik med lampor och strömbrytare' : 'Flik med temperaturer'));
    var title = h('input', { type: 'text', value: tab.title, maxlength: '24', oninput: function () {
      tab.title = this.value; var on = $app.querySelector('.tab.on'); if (on) on.textContent = tab.title || '(namnlös)'; setDirty(true); } });
    var row = h('div', { class: 'row' }, h('label', null, 'Rubrik', title),
      h('label', null, 'Ikon', select(S.config.icons.map(function (n) { return [n, ICON_NAMES[n] || n]; }), tab.icon,
        function (v) { tab.icon = v; setDirty(true); })));
    card.appendChild(row);
    if (tab.type === 'lights') card.appendChild(renderAllOption(tab));
    var del = h('button', { type: 'button', class: 'danger', disabled: cfg.tabs.length < 2, onclick: function () {
      if (!confirmDel) { confirmDel = true; render(); return; }
      cfg.tabs.splice(sel, 1); sel = Math.max(0, sel - 1); confirmDel = false; setDirty(true); render(); } },
      confirmDel ? 'Säker? Tryck igen för att ta bort fliken' : 'Ta bort fliken');
    card.appendChild(h('div', { class: 'btns' },
      h('button', { type: 'button', disabled: sel === 0, onclick: function () { moveTab(-1); } }, '← Flytta åt vänster'),
      h('button', { type: 'button', disabled: sel === cfg.tabs.length - 1, onclick: function () { moveTab(1); } }, 'Flytta åt höger →'),
      del));
    card.appendChild(renderItems(tab));
    return card;
  }

  // ---------------------------------------------------------------- valda enheter på fliken
  function isTemp(e) { return e.dc === 'temperature' || ['°C', '°F', 'K'].indexOf(e.unit) >= 0; }
  function stateText(e) {
    if (!e) return '';
    var names = { on: 'på', off: 'av', unavailable: 'ej tillgänglig', unknown: 'okänt' };
    var s = names[e.state] || e.state;
    return s + (e.unit ? ' ' + e.unit : '');
  }
  function moveItem(tab, i, d) {
    var j = i + d;
    if (j < 0 || j >= tab.items.length) return;
    var t = tab.items[i]; tab.items[i] = tab.items[j]; tab.items[j] = t; setDirty(true); render();
  }
  function renderItems(tab) {
    var em = entMap(), wrap = h('div');
    wrap.appendChild(h('h3', null, 'Visas på fliken (' + tab.items.length + ' av ' + limit(tab) + ')'));
    if (tab.type === 'sensors') wrap.appendChild(h('p', { class: 'muted small' }, 'De två första blir stora kort, de följande nio små (3 × 3). Tomma rutor visas som grå platshållare.'));
    if (tab.type === 'lights') wrap.appendChild(h('p', { class: 'muted small' }, 'Tryck på symbolen eller växeln på panelen för av/på, tryck på namnet (med ›) för dimning. '
      + (tab.show_all === false ? 'Knappen för alla lampor visas inte, så fliken rymmer ' + S.config.limits.lamps_no_all + ' lampor.'
                                : 'Knappen för alla lampor läggs sist.')));
    if (!tab.items.length) wrap.appendChild(h('p', { class: 'muted' }, 'Inget valt än. Kryssa i enheter längre ned.'));
    tab.items.forEach(function (it, i) {
      var pos = (tab.type === 'sensors') ? (i < 2 ? 'Stor ' + (i + 1) : 'Liten ' + (i - 1)) : String(i + 1);
      var ctrl = h('div', { class: 'ctrl' },
        h('button', { type: 'button', class: 'icon', disabled: i === 0, title: 'Flytta upp', onclick: function () { moveItem(tab, i, -1); } }, '↑'),
        h('button', { type: 'button', class: 'icon', disabled: i === tab.items.length - 1, title: 'Flytta ned', onclick: function () { moveItem(tab, i, 1); } }, '↓'),
        h('button', { type: 'button', class: 'icon danger', title: 'Ta bort', onclick: function () { tab.items.splice(i, 1); setDirty(true); render(); } }, '✕'));
      if (it.placeholder) {
        wrap.appendChild(h('div', { class: 'item' }, h('div', { class: 'pos' }, pos), h('div', { class: 'ph' }, 'Tom ruta (platshållare)'), ctrl));
        return;
      }
      var e = em[it.entity_id];
      var name = h('input', { type: 'text', value: it.name || '', maxlength: '40', placeholder: e ? e.name : it.entity_id,
        oninput: function () { it.name = this.value; setDirty(true); } });
      var meta = h('div', { class: 'meta' }, h('code', null, it.entity_id), e ? h('span', null, 'nu: ' + stateText(e)) : (S.entities ? h('span', { class: 'warn' }, 'finns inte i Home Assistant') : null));
      if (tab.type === 'sensors') {
        meta.appendChild(h('span', null, 'Decimaler ', select([['0', '0'], ['1', '1'], ['2', '2'], ['3', '3']], it.decimals == null ? 1 : it.decimals,
          function (v) { it.decimals = parseInt(v, 10); setDirty(true); })));
      } else if (it.entity_id.indexOf('light.') === 0) {
        var cur = typeof it.dimmable === 'boolean' ? (it.dimmable ? 'yes' : 'no') : 'auto';
        meta.appendChild(h('span', null, 'Dimbar ', select([['auto', 'Automatiskt'], ['yes', 'Ja'], ['no', 'Nej']], cur, function (v) {
          if (v === 'auto') delete it.dimmable; else it.dimmable = (v === 'yes'); setDirty(true); })));
      }
      wrap.appendChild(h('div', { class: 'item' }, h('div', { class: 'pos' }, pos), name, ctrl, meta));
    });
    if (tab.type === 'sensors') {
      wrap.appendChild(h('div', { class: 'btns' }, h('button', { type: 'button', disabled: tab.items.length >= limit(tab),
        onclick: function () { tab.items.push({ placeholder: true }); setDirty(true); render(); } }, '+ Tom ruta')));
    }
    return wrap;
  }

  // ---------------------------------------------------------------- lista över enheter i Home Assistant
  function renderPicker(tab) {
    var box = h('section', { class: 'card' }, h('h2', null, tab.type === 'lights' ? 'Lampor och strömbrytare i Home Assistant' : 'Sensorer i Home Assistant'));
    if (!S.entities) {
      box.appendChild(h('p', { class: 'bad' }, S.error || 'Inga enheter att visa.'));
      box.appendChild(h('div', { class: 'btns' }, h('button', { type: 'button', onclick: reloadEntities }, 'Försök igen')));
      return box;
    }
    var doms = tab.type === 'lights' ? ['light', 'switch'] : ['sensor'];
    var list = h('div', { class: 'plist' });
    var info = h('p', { class: 'muted small' });
    function fill() {
      list.textContent = '';
      var q = search.trim().toLowerCase(), shown = 0, total = 0, inTab = {};
      tab.items.forEach(function (it) { if (it.entity_id) inTab[it.entity_id] = true; });
      S.entities.forEach(function (e) {
        if (doms.indexOf(e.id.split('.')[0]) < 0) return;
        if (e.hid && !showHidden && !inTab[e.id]) return;
        if (tab.type === 'sensors' && !inTab[e.id]) {
          if (sensorMode === 'temp' && !isTemp(e)) return;
          if (sensorMode === 'num' && !e.num) return;
        }
        if (q && e.name.toLowerCase().indexOf(q) < 0 && e.id.toLowerCase().indexOf(q) < 0) return;
        total++;
        if (shown >= 300) return;
        shown++;
        var cb = h('input', { type: 'checkbox', checked: !!inTab[e.id], onchange: function () { toggle(tab, e, this); } });
        list.appendChild(h('label', { class: 'pitem' }, cb,
          h('div', { class: 't' }, h('div', null, e.name), h('div', { class: 'id' }, e.id + (e.hid ? '  (dold eller teknisk)' : ''))),
          h('div', { class: 'st' }, stateText(e))));
      });
      info.textContent = total + ' enheter' + (total > shown ? ' (visar ' + shown + ', sök för att begränsa)' : '');
    }
    var s = h('input', { type: 'search', placeholder: 'Sök på namn eller id …', value: search, oninput: function () { search = this.value; fill(); } });
    box.appendChild(s);
    if (tab.type === 'sensors') {
      box.appendChild(h('label', { class: 'opt small muted' }, 'Visa',
        select([['temp', 'Temperaturer'], ['num', 'Sensorer med siffervärde'], ['all', 'Alla sensorer']], sensorMode,
          function (v) { sensorMode = v; fill(); })));
    }
    if (S.hidden_known) {
      box.appendChild(h('label', { class: 'opt small muted' },
        h('input', { type: 'checkbox', checked: showHidden, onchange: function () { showHidden = this.checked; fill(); } }),
        'Visa dolda och tekniska enheter'));
    }
    box.appendChild(info); box.appendChild(list);
    box.appendChild(h('div', { class: 'btns' }, h('button', { type: 'button', onclick: reloadEntities }, 'Uppdatera listan')));
    fill();
    return box;
  }
  function toggle(tab, e, cb) {
    var idx = -1;
    tab.items.forEach(function (it, i) { if (it.entity_id === e.id) idx = i; });
    if (cb.checked && idx < 0) {
      if (tab.items.length >= limit(tab)) { cb.checked = false; say('Fliken är full (' + limit(tab) + ' platser).', 'bad'); return; }
      var it = { entity_id: e.id, name: e.name };
      if (tab.type === 'sensors') it.decimals = 1;
      var firstFree = -1;
      if (tab.type === 'sensors') tab.items.forEach(function (x, i) { if (x.placeholder && firstFree < 0 && i >= 2) firstFree = i; });
      if (firstFree >= 0) tab.items[firstFree] = it; else tab.items.push(it);
    } else if (!cb.checked && idx >= 0) {
      tab.items.splice(idx, 1);
    }
    setDirty(true); render();
  }

  // ---------------------------------------------------------------- allmänna inställningar
  function renderSettings() {
    var card = h('section', { class: 'card' }, h('h2', null, 'Allmänt'));
    card.appendChild(h('div', { class: 'row' },
      h('label', null, 'Decimaltecken för temperaturer', select([[',', 'Komma (21,5)'], ['.', 'Punkt (21.5)']], cfg.locale.decimal_separator,
        function (v) { cfg.locale.decimal_separator = v; setDirty(true); })),
      h('label', null, 'Steg för plus och minus i dimvyn', select([['5', '5 %'], ['10', '10 %'], ['20', '20 %'], ['25', '25 %']], cfg.ui.dim_step,
        function (v) { cfg.ui.dim_step = parseInt(v, 10); setDirty(true); })),
      h('label', null, 'Dimvyn stängs efter tomgång', select([['30', '30 sekunder'], ['60', '1 minut'], ['90', '90 sekunder'], ['180', '3 minuter'], ['0', 'Aldrig']],
        cfg.ui.dim_timeout, function (v) { cfg.ui.dim_timeout = parseInt(v, 10); setDirty(true); }))));
    return card;
  }

  function render() {
    var y = window.scrollY;
    $app.textContent = '';
    $conn.textContent = S.connected ? 'Ansluten till Home Assistant' : 'Ingen kontakt med Home Assistant';
    $conn.className = 'badge ' + (S.connected ? 'ok' : 'bad');
    $app.appendChild(renderTabs());
    var tab = cfg.tabs[sel];
    if (tab) { $app.appendChild(renderTabEditor(tab)); $app.appendChild(renderPicker(tab)); }
    $app.appendChild(renderSettings());
    window.scrollTo(0, y);
  }

  load();
})();
'''
