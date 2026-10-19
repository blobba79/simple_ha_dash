"""Sidan för redigering (HTML, CSS och JavaScript som text). Inget laddas utifrån: allt serveras av panelen
(typsnittet Roboto ur assets/fonts, ikonerna är Material Design Icons-banor, Apache 2.0).
Källan byggs av ett verktyg utanför repot; ändra gärna här direkt."""

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
<div id="shell">
  <aside id="side" aria-label="Flikar och inställningar">
    <div class="brand"><span class="brand-name">Panelen</span><span id="conn" class="conn"></span></div>
    <nav id="nav"></nav>
  </aside>
  <div id="scrim" hidden></div>
  <div id="main">
    <header id="top">
      <button id="menu" class="iconbtn" type="button" aria-label="Visa flikarna"></button>
      <h1 id="title">Panelinställningar</h1>
      <span id="topact"></span>
    </header>
    <main id="app"><p class="muted pad">Laddar …</p></main>
  </div>
</div>
<div id="bar" hidden><span id="msg"></span><button id="undo" type="button">Ångra ändringar</button><button id="save" class="primary" type="button">Spara</button></div>
<div id="toast" role="status" hidden></div>
<div id="dlg" hidden></div>
<script src="/app.js"></script>
</body>
</html>
'''

APP_CSS = r'''@font-face { font-family: Roboto; font-weight: 300; src: url(/fonts/300.ttf) format("truetype"); font-display: swap; }
@font-face { font-family: Roboto; font-weight: 400; src: url(/fonts/400.ttf) format("truetype"); font-display: swap; }
@font-face { font-family: Roboto; font-weight: 500; src: url(/fonts/500.ttf) format("truetype"); font-display: swap; }
:root {
  --bg: #111111; --surface: #1c1c1c; --surface-2: #242424; --surface-3: #2a2a2a; --line: #2c2c2c; --line-2: #3a3a3a;
  --text: #e1e1e1; --muted: #9b9b9b; --faint: #6b6b6b;
  --primary: #03a9f4; --primary-l: #4fc3f7; --primary-d: #0b4a6e; --primary-bg: #0f2230;
  --amber: #ffc107; --amber-bg: #2e2812; --amber-line: #4a3f12; --off-icon: #4b79a8; --off-circle: #242c36;
  --warn: #ffa726; --bad: #ef5350; --ok: #66bb6a;
  --side-w: 256px; --top-h: 56px;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html { background: var(--bg); }
body { margin: 0; background: var(--bg); color: var(--text); font: 400 15px/1.45 Roboto, system-ui, -apple-system, "Segoe UI", sans-serif;
       -webkit-font-smoothing: antialiased; }
button, select, input { font: inherit; color: inherit; }
svg.i { width: 24px; height: 24px; fill: currentColor; flex: none; display: block; }
svg.i.s18 { width: 18px; height: 18px; } svg.i.s20 { width: 20px; height: 20px; }
svg.i.inl { display: inline-block; vertical-align: -4px; }
.muted { color: var(--muted); } .small { font-size: 13px; } .warn { color: var(--warn); } .bad { color: var(--bad); }
.pad { padding: 16px; }
:focus-visible { outline: 2px solid var(--primary-l); outline-offset: 2px; }

/* ---------------------------------------------------------------- skal: sidomeny + innehåll */
#shell { display: flex; min-height: 100vh; }
#side { width: var(--side-w); flex: none; background: var(--surface); border-right: 1px solid var(--line); position: sticky; top: 0;
        height: 100vh; overflow-y: auto; display: flex; flex-direction: column; }
.brand { height: var(--top-h); display: flex; align-items: center; gap: 10px; padding: 0 16px; border-bottom: 1px solid var(--line); }
.brand-name { font-size: 20px; font-weight: 400; flex: 1; }
.conn { width: 10px; height: 10px; border-radius: 50%; background: var(--faint); }
.conn.ok { background: var(--ok); } .conn.bad { background: var(--warn); }
#nav { padding: 8px 0; display: flex; flex-direction: column; }
.navhead { padding: 14px 16px 6px; font-size: 13px; color: var(--muted); }
.navitem { display: flex; align-items: center; gap: 16px; min-height: 48px; margin: 0 8px; padding: 0 12px; border: 0; border-radius: 10px;
           background: none; text-align: left; cursor: pointer; color: var(--text); }
.navitem svg { color: var(--muted); }
.navitem:hover { background: var(--surface-2); }
.navitem.on { background: var(--primary-bg); color: var(--primary-l); }
.navitem.on svg { color: var(--primary-l); }
.navitem .lbl { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.navitem .cnt { font-size: 12px; color: var(--muted); }
.navitem.add { color: var(--muted); }
.navsep { height: 1px; background: var(--line); margin: 8px 16px; }
#main { flex: 1; min-width: 0; }
#top { height: var(--top-h); display: flex; align-items: center; gap: 8px; padding: 0 16px; position: sticky; top: 0; z-index: 5;
       background: var(--bg); border-bottom: 1px solid var(--line); }
#top h1 { margin: 0; font-size: 20px; font-weight: 400; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#menu { display: none; }
#app { max-width: 1040px; margin: 0 auto; padding: 16px 16px 120px; }
#scrim { position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 19; }

/* ---------------------------------------------------------------- knappar och fält */
.iconbtn { width: 40px; height: 40px; min-width: 40px; border-radius: 50%; border: 0; background: none; display: inline-flex;
           align-items: center; justify-content: center; cursor: pointer; color: var(--text); padding: 0; }
.iconbtn:hover { background: var(--surface-2); }
.iconbtn:disabled { opacity: .35; cursor: default; background: none; }
.btn { min-height: 40px; padding: 0 16px; border-radius: 20px; border: 1px solid var(--line-2); background: none; cursor: pointer;
       display: inline-flex; align-items: center; gap: 8px; font-weight: 500; color: var(--primary-l); }
.btn:hover { background: var(--surface-2); }
.btn:disabled { opacity: .4; cursor: default; background: none; }
.btn.fill, button.primary { background: var(--primary); border-color: var(--primary); color: #fff; }
.btn.fill:hover, button.primary:hover { background: #0398dc; }
.btn.danger { color: #ff8a80; border-color: #5a2b2b; }
.btn.text { border-color: transparent; padding: 0 10px; }
.field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.field > span { font-size: 12px; color: var(--muted); padding-left: 2px; }
.field input, .field select, input.big { width: 100%; min-height: 44px; padding: 8px 12px; border-radius: 10px; border: 1px solid var(--line-2);
       background: var(--surface-2); color: var(--text); }
.field input:focus, .field select:focus, input.big:focus { border-color: var(--primary); outline: none; }
.field input:disabled { opacity: .45; }
.check { display: flex; gap: 12px; align-items: center; cursor: pointer; min-height: 40px; }
.check input { width: 20px; height: 20px; accent-color: var(--primary); margin: 0; flex: none; }
.check input.switch, .switch { position: relative; width: 36px; height: 20px; flex: none; appearance: none; -webkit-appearance: none; margin: 0; cursor: pointer;
          border-radius: 10px; background: #5a5a5a; transition: background .15s; }
.switch::after { content: ""; position: absolute; left: 2px; top: 2px; width: 16px; height: 16px; border-radius: 50%; background: #e1e1e1;
                 transition: transform .15s; }
.switch:checked { background: var(--primary-d); } .switch:checked::after { transform: translateX(16px); background: var(--primary-l); }
.switch:disabled { opacity: .4; cursor: default; }

/* ---------------------------------------------------------------- kort */
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; margin: 0 0 16px; }
.card > .hd { display: flex; align-items: center; gap: 12px; padding: 14px 16px 6px; min-height: 52px; }
.card > .hd h2 { margin: 0; font-size: 18px; font-weight: 400; flex: 1; }
.card > .hd .sub { font-size: 13px; color: var(--muted); }
.card > .bd { padding: 8px 16px 16px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px 16px; }
.hint { font-size: 13px; color: var(--muted); margin: 6px 0 0; }

/* fliken: rubrik och ikon */
.tabhead { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: center; padding: 16px; }
.iconpick { width: 56px; height: 56px; border-radius: 50%; border: 1px solid var(--line-2); background: var(--off-circle); color: var(--primary-l);
            display: inline-flex; align-items: center; justify-content: center; cursor: pointer; }
.iconpick svg { width: 28px; height: 28px; }
input.big { font-size: 20px; min-height: 52px; }
.tabkind { font-size: 13px; color: var(--muted); margin-top: 4px; padding-left: 2px; }
.icons { display: grid; grid-template-columns: repeat(auto-fill, 52px); gap: 8px; padding: 0 16px 16px; }
.icons button { width: 52px; height: 52px; border-radius: 12px; border: 1px solid var(--line-2); background: var(--surface-2); color: var(--muted);
                display: flex; align-items: center; justify-content: center; cursor: pointer; }
.icons button.on { border-color: var(--primary); color: var(--primary-l); background: var(--primary-bg); }
.allrow { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; padding: 12px 16px; border-top: 1px solid var(--line); }
.allrow .check { flex: 1 1 260px; }
.allrow .field { flex: 0 1 240px; }

/* ---------------------------------------------------------------- förhandsvisning av fliken (som på panelen) */
.screen { background: #0b0b0b; border: 1px solid var(--line); border-radius: 14px; padding: 10px; }
.slots { display: grid; gap: 8px; }
.slots.btn8 { grid-template-columns: 1fr 1fr; grid-auto-rows: 64px; }
.slots.val { grid-template-columns: 1.6fr 1fr 1fr 1fr; grid-template-rows: repeat(6, 44px); }
.slots.val .slot:nth-child(1) { grid-column: 1; grid-row: 1 / 4; }
.slots.val .slot:nth-child(2) { grid-column: 1; grid-row: 4 / 7; }
.slots.val .slot:nth-child(n+3) { grid-row: span 2; }
.slot { position: relative; border-radius: 12px; border: 1px solid var(--line); background: var(--surface); display: flex; align-items: center;
        gap: 10px; padding: 0 8px 0 10px; min-width: 0; cursor: pointer; text-align: left; color: var(--text); user-select: none;
        -webkit-user-select: none; }
.slot:hover { border-color: var(--line-2); }
.slot.empty { border-style: dashed; border-color: var(--line-2); background: none; color: var(--faint); justify-content: center; }
.slot.ph { border-style: dashed; background: none; color: var(--muted); }
.slot .ic { width: 38px; height: 38px; border-radius: 50%; background: var(--off-circle); color: var(--off-icon); display: flex;
            align-items: center; justify-content: center; flex: none; }
.slot.on .ic { background: #43390f; color: var(--amber); }
.slot.on { background: var(--amber-bg); border-color: var(--amber-line); }
.slot.on.blue { background: var(--primary-bg); border-color: var(--primary-d); }
.slot.on.blue .ic { background: var(--primary-d); color: var(--primary-l); }
.slot.na .ic { color: #3e4e60; background: #1f2226; }
.slot .tx { flex: 1; min-width: 0; }
.slot .nm { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.slot .st { font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.slot.on .st { color: var(--amber); } .slot.on.blue .st { color: var(--primary-l); }
.slot.miss .st { color: var(--warn); }
.slot.all { border-width: 2px; }
.slot .grip { width: 32px; height: 40px; border: 0; background: none; color: var(--muted); display: flex; align-items: center; justify-content: center;
              cursor: grab; touch-action: none; border-radius: 8px; flex: none; padding: 0; }
.slot .grip:hover { color: var(--text); background: var(--surface-3); }
.slots.val .slot { flex-direction: column; align-items: flex-start; justify-content: space-between; padding: 8px 10px; gap: 2px; }
.slots.val .slot .row1 { display: flex; align-items: center; gap: 6px; width: 100%; color: var(--muted); font-size: 12px; }
.slots.val .slot .row1 .nm { flex: 1; font-weight: 400; color: var(--muted); }
.slots.val .slot .val { font-size: 22px; font-weight: 500; line-height: 1.1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }
.slots.val .slot:nth-child(-n+2) .val { font-size: 34px; font-weight: 300; }
.slots.val .slot .val small { font-size: 13px; color: var(--muted); font-weight: 400; margin-left: 3px; }
.slots.val .slot .grip { position: absolute; right: 2px; top: 2px; height: 32px; width: 28px; }
.slots.val .slot .row1 { padding-right: 24px; }
.slots.val .slot.empty, .slots.val .slot.ph { align-items: center; justify-content: center; }
.slot.dragging { opacity: .35; }
.slot.target { outline: 2px solid var(--primary); outline-offset: 1px; }
.ghost { position: fixed; z-index: 40; pointer-events: none; opacity: .92; box-shadow: 0 8px 28px rgba(0,0,0,.6); }
.prevfoot { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 10px 2px 0; }
.prevfoot .hint { margin: 0; flex: 1 1 240px; }

/* ---------------------------------------------------------------- lägg till: sök, filter, lista */
.search { display: flex; align-items: center; gap: 8px; background: var(--surface-2); border: 1px solid var(--line-2); border-radius: 24px;
          padding: 0 6px 0 14px; min-height: 48px; }
.search:focus-within { border-color: var(--primary); }
.search input { flex: 1; min-width: 0; border: 0; background: none; outline: none; min-height: 44px; font-size: 16px; color: var(--text); }
.search svg { color: var(--muted); }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 0; align-items: center; }
.chip { min-height: 34px; border-radius: 17px; border: 1px solid var(--line-2); background: none; padding: 0 12px 0 8px; display: inline-flex;
        align-items: center; gap: 6px; cursor: pointer; color: var(--text); font-size: 14px; }
.chip svg { width: 18px; height: 18px; color: var(--muted); }
.chip .n { color: var(--muted); font-size: 12px; }
.chip.on { background: var(--primary-bg); border-color: var(--primary); color: var(--primary-l); }
.chip.on svg { color: var(--primary-l); }
.chip:disabled { opacity: .4; cursor: default; }
.tools { display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 12px 0 4px; align-items: flex-end; }
.tools .field { flex: 1 1 180px; max-width: 280px; }
.tools .check { font-size: 14px; color: var(--muted); }
.count { font-size: 13px; color: var(--muted); margin: 10px 2px 0; }
.group { border-top: 1px solid var(--line); }
.ghd { display: flex; align-items: center; gap: 10px; min-height: 48px; padding: 0 4px 0 0; }
.ghd .tog { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; border: 0; background: none; cursor: pointer; min-height: 48px;
            padding: 0 4px; text-align: left; color: var(--text); }
.ghd .tog .gn { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ghd .tog .gc { color: var(--muted); font-size: 13px; }
.ghd .tog svg.chev { color: var(--muted); transition: transform .15s; }
.group.closed .ghd .tog svg.chev { transform: rotate(-90deg); }
.group.closed .rows { display: none; }
.ghd .btn { min-height: 32px; font-size: 13px; padding: 0 12px; }
.erow { display: grid; grid-template-columns: auto auto 1fr auto; gap: 12px; align-items: center; padding: 6px 4px; min-height: 56px; cursor: pointer;
        border-radius: 10px; }
.erow:hover { background: var(--surface-2); }
.erow input { width: 20px; height: 20px; accent-color: var(--primary); margin: 0 4px; }
.erow .ic { width: 40px; height: 40px; border-radius: 50%; background: var(--off-circle); color: var(--off-icon); display: flex;
            align-items: center; justify-content: center; }
.erow.on .ic { background: #43390f; color: var(--amber); }
.erow.on.blue .ic { background: var(--primary-d); color: var(--primary-l); }
.erow .t { min-width: 0; }
.erow .t div { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.erow .t .id { font-size: 12px; color: var(--muted); }
.erow .s { font-size: 13px; color: var(--muted); white-space: nowrap; max-width: 140px; overflow: hidden; text-overflow: ellipsis; }
.erow.full { opacity: .5; cursor: default; }
.empty-note { padding: 18px 4px; color: var(--muted); }

/* ---------------------------------------------------------------- dialog */
#dlg { position: fixed; inset: 0; z-index: 30; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,.6); padding: 16px; }
.dbox { background: var(--surface); border: 1px solid var(--line-2); border-radius: 16px; width: 100%; max-width: 520px; max-height: calc(100vh - 32px);
        overflow-y: auto; }
.dbox .dh { display: flex; align-items: center; gap: 12px; padding: 16px 12px 8px 20px; }
.dbox .dh h3 { margin: 0; font-size: 20px; font-weight: 400; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dbox .db { padding: 8px 20px 12px; display: flex; flex-direction: column; gap: 14px; }
.dbox .df { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; padding: 8px 16px 16px; }
.dbox .df .spacer { flex: 1; }
.kv { display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; font-size: 13px; }
.kv dt { color: var(--muted); } .kv dd { margin: 0; overflow-wrap: anywhere; }
.seg { align-self: flex-start; display: inline-flex; border: 1px solid var(--line-2); border-radius: 20px; overflow: hidden; }
.seg button { border: 0; background: none; padding: 0 14px; min-height: 36px; cursor: pointer; color: var(--muted); white-space: nowrap; }
.seg button.on { background: var(--primary-bg); color: var(--primary-l); }
.seg button + button { border-left: 1px solid var(--line-2); }
.kindpick { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.kindpick button { border: 1px solid var(--line-2); border-radius: 12px; background: var(--surface-2); padding: 12px; text-align: left; cursor: pointer;
                   display: flex; flex-direction: column; gap: 6px; color: var(--text); }
.kindpick button.on { border-color: var(--primary); background: var(--primary-bg); }
.kindpick button .k { font-weight: 500; display: flex; align-items: center; gap: 8px; }
.kindpick button .d { font-size: 12px; color: var(--muted); }

/* ---------------------------------------------------------------- spara-raden och meddelanden */
#bar { position: fixed; left: var(--side-w); right: 0; bottom: 0; display: flex; gap: 8px; align-items: center; justify-content: flex-end;
       padding: 12px 16px; background: #181818; border-top: 1px solid var(--line-2); z-index: 10; }
#msg { flex: 1; font-size: 14px; color: var(--warn); min-width: 0; }
#bar button { min-height: 40px; padding: 0 18px; border-radius: 20px; border: 1px solid var(--line-2); background: none; cursor: pointer; font-weight: 500;
              color: var(--primary-l); }
#bar button.primary { color: #fff; background: var(--primary); border-color: var(--primary); }
#bar button:disabled { opacity: .5; cursor: default; }
#toast { position: fixed; left: 50%; transform: translateX(-50%); bottom: 84px; z-index: 50; background: #323232; color: #fff; border-radius: 8px;
         padding: 12px 18px; max-width: calc(100vw - 32px); box-shadow: 0 6px 20px rgba(0,0,0,.5); font-size: 14px; }
#toast.bad { background: #5a1f1f; }

@media (max-width: 860px) {
  #side { position: fixed; left: 0; top: 0; bottom: 0; z-index: 20; transform: translateX(-100%); transition: transform .2s; height: 100%; }
  body.drawer #side { transform: none; }
  #menu { display: inline-flex; }
  #bar { left: 0; }
}
@media (max-width: 560px) {
  #app { padding: 12px 10px 120px; }
  .card > .hd, .card > .bd { padding-left: 12px; padding-right: 12px; }
  .tabhead { padding: 12px; gap: 10px; grid-template-columns: auto 1fr; }
  .tabhead > div:last-child { grid-column: 1 / -1; justify-self: end; margin-top: -6px; }
  .iconpick { width: 48px; height: 48px; }
  .slots.btn8 { grid-auto-rows: 58px; gap: 6px; }
  .slot { gap: 6px; padding: 0 2px 0 6px; }
  .slot .ic { width: 32px; height: 32px; } .slot .ic svg { width: 20px; height: 20px; }
  .slot .nm { font-size: 13px; } .slot .st { font-size: 11px; }
  .slot .grip { width: 26px; }
  .slots.val { grid-template-columns: repeat(6, 1fr); grid-template-rows: none; grid-auto-rows: 70px; }
  .slots.val .slot:nth-child(1) { grid-column: 1 / 4; grid-row: 1 / 3; }
  .slots.val .slot:nth-child(2) { grid-column: 4 / 7; grid-row: 1 / 3; }
  .slots.val .slot:nth-child(n+3) { grid-row: span 1; grid-column: span 2; }
  .slots.val .slot:nth-child(-n+2) .val { font-size: 28px; }
  .slots.val .slot .val { font-size: 18px; }
  .screen { padding: 6px; }
  .erow { grid-template-columns: auto auto 1fr; }
  .erow .s { grid-column: 3; max-width: none; margin-top: -8px; }
  .kindpick { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }

/* ---------------------------------------------------------------- tillägg 2026-10-19 kväll: enheter, graf, säkerhetskopia */
a.btn, label.btn { text-decoration: none; }
.filein { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.countrow { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; justify-content: space-between; margin: 10px 0 0; }
.countrow .count { margin: 0; }
.foldall { display: flex; gap: 4px; }
.foldall .btn { min-height: 32px; font-size: 13px; }
.ghd .tog .gsel { font-size: 12px; color: var(--primary-l); background: var(--primary-bg); border-radius: 10px; padding: 1px 8px; white-space: nowrap; }
.group.lv1 { border-top: 0; margin: 2px 0 2px 34px; border-left: 2px solid var(--line); padding-left: 6px; }
.group.lv1 .ghd { min-height: 42px; }
.group.lv1 .ghd .tog { min-height: 42px; }
.group.lv1 .ghd .tog .gn { font-weight: 400; }
.group.lv0 > .rows > .erow, .group.lv0 > .rows > .rows > .erow { margin-left: 0; }
.slots.gl { grid-template-columns: 1fr; grid-auto-rows: 56px; }
.slot.gs { cursor: pointer; }
.sw { width: 14px; height: 14px; border-radius: 4px; flex: none; display: inline-block; background: var(--primary-l); }
.sw[data-c="1"] { background: #ffb74d; } .sw[data-c="2"] { background: #81c784; }
.gchart { margin: 14px 0 0; background: #151515; border: 1px solid var(--line); border-radius: 12px; padding: 10px 10px 4px; }
.gchart .empty-note { margin: 0; }
svg.chart { width: 100%; height: auto; display: block; }
svg.chart .grid { stroke: #2c2c2c; stroke-width: 1; }
svg.chart .ax { fill: var(--muted); font-size: 11px; }
svg.chart .mm { font-size: 12px; font-weight: 500; }
.glegend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 0 0 8px; font-size: 13px; }
.gl-item { display: inline-flex; align-items: center; gap: 6px; }
.gl-item .mx { color: #ef9a9a; font-weight: 500; } .gl-item .mn { color: #90caf9; font-weight: 500; }
.card.welcome h2 { font-size: 22px; font-weight: 400; margin: 6px 0 10px; }
.card.welcome p { max-width: 640px; }
'''

APP_JS = r''''use strict';
(function () {
  // Material Design Icons (Apache 2.0), samma ikoner som Home Assistant och panelen använder
  var ICONS = {"Account":"M12,4A4,4 0 0,1 16,8A4,4 0 0,1 12,12A4,4 0 0,1 8,8A4,4 0 0,1 12,4M12,14C16.42,14 20,15.79 20,18V20H4V18C4,15.79 7.58,14 12,14Z","AirHumidifier":"M11 9C8.79 9 7 10.79 7 13S8.79 17 11 17 15 15.21 15 13 13.21 9 11 9M11 15C9.9 15 9 14.11 9 13S9.9 11 11 11 13 11.9 13 13 12.11 15 11 15M7 4H14C16.21 4 18 5.79 18 8V9H16V8C16 6.9 15.11 6 14 6H7C5.9 6 5 6.9 5 8V20H16V18H18V22H3V8C3 5.79 4.79 4 7 4M19 10.5C19 10.5 21 12.67 21 14C21 15.1 20.1 16 19 16S17 15.1 17 14C17 12.67 19 10.5 19 10.5","AirHumidifierOff":"M22.1 21.5L2.4 1.7L1.1 3L3.8 5.7C3.3 6.3 3 7.1 3 8V22H18V19.9L20.8 22.7L22.1 21.5M9.6 11.5L12.4 14.3C12.1 14.7 11.6 15 11 15C9.9 15 9 14.1 9 13C9 12.4 9.3 11.9 9.6 11.5M16 17.9V20H5V8C5 7.7 5.1 7.4 5.2 7.1L8.2 10.1C7.5 10.8 7 11.9 7 13C7 15.2 8.8 17 11 17C12.1 17 13.2 16.5 13.9 15.8L16 17.9M17 13.8C17.1 12.5 19 10.5 19 10.5S21 12.7 21 14C21 15 20.2 15.9 19.2 16L17 13.8M9.2 6L7.2 4H14C16.2 4 18 5.8 18 8V9H16V8C16 6.9 15.1 6 14 6H9.2Z","ArrowDown":"M11,4H13V16L18.5,10.5L19.92,11.92L12,19.84L4.08,11.92L5.5,10.5L11,16V4Z","ArrowLeft":"M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z","ArrowRight":"M4,11V13H16L10.5,18.5L11.92,19.92L19.84,12L11.92,4.08L10.5,5.5L16,11H4Z","ArrowUp":"M13,20H11V8L5.5,13.5L4.08,12.08L12,4.16L19.92,12.08L18.5,13.5L13,8V20Z","Battery":"M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.67C6,21.4 6.6,22 7.33,22H16.67A1.33,1.33 0 0,0 18,20.67V5.33C18,4.6 17.4,4 16.67,4Z","Brightness5":"M12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6A6,6 0 0,1 18,12A6,6 0 0,1 12,18M20,15.31L23.31,12L20,8.69V4H15.31L12,0.69L8.69,4H4V8.69L0.69,12L4,15.31V20H8.69L12,23.31L15.31,20H20V15.31Z","Brightness6":"M12,18V6A6,6 0 0,1 18,12A6,6 0 0,1 12,18M20,15.31L23.31,12L20,8.69V4H15.31L12,0.69L8.69,4H4V8.69L0.69,12L4,15.31V20H8.69L12,23.31L15.31,20H20V15.31Z","CalendarClock":"M15,13H16.5V15.82L18.94,17.23L18.19,18.53L15,16.69V13M19,8H5V19H9.67C9.24,18.09 9,17.07 9,16A7,7 0 0,1 16,9C17.07,9 18.09,9.24 19,9.67V8M5,21C3.89,21 3,20.1 3,19V5C3,3.89 3.89,3 5,3H6V1H8V3H16V1H18V3H19A2,2 0 0,1 21,5V11.1C22.24,12.36 23,14.09 23,16A7,7 0 0,1 16,23C14.09,23 12.36,22.24 11.1,21H5M16,11.15A4.85,4.85 0 0,0 11.15,16C11.15,18.68 13.32,20.85 16,20.85A4.85,4.85 0 0,0 20.85,16C20.85,13.32 18.68,11.15 16,11.15Z","ChartLine":"M16,11.78L20.24,4.45L21.97,5.45L16.74,14.5L10.23,10.75L5.46,19H22V21H2V3H4V17.54L9.5,8L16,11.78Z","Check":"M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z","ChevronDown":"M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z","ChevronLeft":"M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z","ChevronRight":"M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z","Close":"M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z","CloudDownload":"M6.5 20Q4.22 20 2.61 18.43 1 16.85 1 14.58 1 12.63 2.17 11.1 3.35 9.57 5.25 9.15 5.83 7.13 7.39 5.75 8.95 4.38 11 4.08V12.15L9.4 10.6L8 12L12 16L16 12L14.6 10.6L13 12.15V4.08Q15.58 4.43 17.29 6.39 19 8.35 19 11 20.73 11.2 21.86 12.5 23 13.78 23 15.5 23 17.38 21.69 18.69 20.38 20 18.5 20Z","Cog":"M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z","Counter":"M4,4H20A2,2 0 0,1 22,6V18A2,2 0 0,1 20,20H4A2,2 0 0,1 2,18V6A2,2 0 0,1 4,4M4,6V18H11V6H4M20,18V6H18.76C19,6.54 18.95,7.07 18.95,7.13C18.88,7.8 18.41,8.5 18.24,8.75L15.91,11.3L19.23,11.28L19.24,12.5L14.04,12.47L14,11.47C14,11.47 17.05,8.24 17.2,7.95C17.34,7.67 17.91,6 16.5,6C15.27,6.05 15.41,7.3 15.41,7.3L13.87,7.31C13.87,7.31 13.88,6.65 14.25,6H13V18H15.58L15.57,17.14L16.54,17.13C16.54,17.13 17.45,16.97 17.46,16.08C17.5,15.08 16.65,15.08 16.5,15.08C16.37,15.08 15.43,15.13 15.43,15.95H13.91C13.91,15.95 13.95,13.89 16.5,13.89C19.1,13.89 18.96,15.91 18.96,15.91C18.96,15.91 19,17.16 17.85,17.63L18.37,18H20M8.92,16H7.42V10.2L5.62,10.76V9.53L8.76,8.41H8.92V16Z","Delete":"M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z","Devices":"M3 6H21V4H3C1.9 4 1 4.9 1 6V18C1 19.1 1.9 20 3 20H7V18H3V6M13 12H9V13.78C8.39 14.33 8 15.11 8 16C8 16.89 8.39 17.67 9 18.22V20H13V18.22C13.61 17.67 14 16.88 14 16S13.61 14.33 13 13.78V12M11 17.5C10.17 17.5 9.5 16.83 9.5 16S10.17 14.5 11 14.5 12.5 15.17 12.5 16 11.83 17.5 11 17.5M22 8H16C15.5 8 15 8.5 15 9V19C15 19.5 15.5 20 16 20H22C22.5 20 23 19.5 23 19V9C23 8.5 22.5 8 22 8M21 18H17V10H21V18Z","DoorOpen":"M12,3C10.89,3 10,3.89 10,5H3V19H2V21H22V19H21V5C21,3.89 20.11,3 19,3H12M12,5H19V19H12V5M5,11H7V13H5V11Z","Download":"M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z","DragVertical":"M9,3H11V5H9V3M13,3H15V5H13V3M9,7H11V9H9V7M13,7H15V9H13V7M9,11H11V13H9V11M13,11H15V13H13V11M9,15H11V17H9V15M13,15H15V17H13V15M9,19H11V21H9V19M13,19H15V21H13V19Z","ExitToApp":"M19,3H5C3.89,3 3,3.89 3,5V9H5V5H19V19H5V15H3V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5C21,3.89 20.1,3 19,3M10.08,15.58L11.5,17L16.5,12L11.5,7L10.08,8.41L12.67,11H3V13H12.67L10.08,15.58Z","Eye":"M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17M12,4.5C7,4.5 2.73,7.61 1,12C2.73,16.39 7,19.5 12,19.5C17,19.5 21.27,16.39 23,12C21.27,7.61 17,4.5 12,4.5Z","Fan":"M12,11A1,1 0 0,0 11,12A1,1 0 0,0 12,13A1,1 0 0,0 13,12A1,1 0 0,0 12,11M12.5,2C17,2 17.11,5.57 14.75,6.75C13.76,7.24 13.32,8.29 13.13,9.22C13.61,9.42 14.03,9.73 14.35,10.13C18.05,8.13 22.03,8.92 22.03,12.5C22.03,17 18.46,17.1 17.28,14.73C16.78,13.74 15.72,13.3 14.79,13.11C14.59,13.59 14.28,14 13.88,14.34C15.87,18.03 15.08,22 11.5,22C7,22 6.91,18.42 9.27,17.24C10.25,16.75 10.69,15.71 10.89,14.79C10.4,14.59 9.97,14.27 9.65,13.87C5.96,15.85 2,15.07 2,11.5C2,7 5.56,6.89 6.74,9.26C7.24,10.25 8.29,10.68 9.22,10.87C9.41,10.39 9.73,9.97 10.14,9.65C8.15,5.96 8.94,2 12.5,2Z","FanOff":"M12.5,2C9.64,2 8.57,4.55 9.29,7.47L15,13.16C15.87,13.37 16.81,13.81 17.28,14.73C18.46,17.1 22.03,17 22.03,12.5C22.03,8.92 18.05,8.13 14.35,10.13C14.03,9.73 13.61,9.42 13.13,9.22C13.32,8.29 13.76,7.24 14.75,6.75C17.11,5.57 17,2 12.5,2M3.28,4L2,5.27L4.47,7.73C3.22,7.74 2,8.87 2,11.5C2,15.07 5.96,15.85 9.65,13.87C9.97,14.27 10.4,14.59 10.89,14.79C10.69,15.71 10.25,16.75 9.27,17.24C6.91,18.42 7,22 11.5,22C13.8,22 14.94,20.36 14.94,18.21L18.73,22L20,20.72L3.28,4Z","Flash":"M7,2V13H10V22L17,10H13L17,2H7Z","Flower":"M3,13A9,9 0 0,0 12,22C12,17 7.97,13 3,13M12,5.5A2.5,2.5 0 0,1 14.5,8A2.5,2.5 0 0,1 12,10.5A2.5,2.5 0 0,1 9.5,8A2.5,2.5 0 0,1 12,5.5M5.6,10.25A2.5,2.5 0 0,0 8.1,12.75C8.63,12.75 9.12,12.58 9.5,12.31C9.5,12.37 9.5,12.43 9.5,12.5A2.5,2.5 0 0,0 12,15A2.5,2.5 0 0,0 14.5,12.5C14.5,12.43 14.5,12.37 14.5,12.31C14.88,12.58 15.37,12.75 15.9,12.75C17.28,12.75 18.4,11.63 18.4,10.25C18.4,9.25 17.81,8.4 16.97,8C17.81,7.6 18.4,6.74 18.4,5.75C18.4,4.37 17.28,3.25 15.9,3.25C15.37,3.25 14.88,3.41 14.5,3.69C14.5,3.63 14.5,3.56 14.5,3.5A2.5,2.5 0 0,0 12,1A2.5,2.5 0 0,0 9.5,3.5C9.5,3.56 9.5,3.63 9.5,3.69C9.12,3.41 8.63,3.25 8.1,3.25A2.5,2.5 0 0,0 5.6,5.75C5.6,6.74 6.19,7.6 7.03,8C6.19,8.4 5.6,9.25 5.6,10.25M12,22A9,9 0 0,0 21,13C16,13 12,17 12,22Z","FormTextbox":"M17,7H22V17H17V19A1,1 0 0,0 18,20H20V22H17.5C16.95,22 16,21.55 16,21C16,21.55 15.05,22 14.5,22H12V20H14A1,1 0 0,0 15,19V5A1,1 0 0,0 14,4H12V2H14.5C15.05,2 16,2.45 16,3C16,2.45 16.95,2 17.5,2H20V4H18A1,1 0 0,0 17,5V7M2,7H13V9H4V15H13V17H2V7M20,15V9H17V15H20Z","FormatListBulleted":"M7,5H21V7H7V5M7,13V11H21V13H7M4,4.5A1.5,1.5 0 0,1 5.5,6A1.5,1.5 0 0,1 4,7.5A1.5,1.5 0 0,1 2.5,6A1.5,1.5 0 0,1 4,4.5M4,10.5A1.5,1.5 0 0,1 5.5,12A1.5,1.5 0 0,1 4,13.5A1.5,1.5 0 0,1 2.5,12A1.5,1.5 0 0,1 4,10.5M7,19V17H21V19H7M4,16.5A1.5,1.5 0 0,1 5.5,18A1.5,1.5 0 0,1 4,19.5A1.5,1.5 0 0,1 2.5,18A1.5,1.5 0 0,1 4,16.5Z","GamepadVariant":"M7,6H17A6,6 0 0,1 23,12A6,6 0 0,1 17,18C15.22,18 13.63,17.23 12.53,16H11.47C10.37,17.23 8.78,18 7,18A6,6 0 0,1 1,12A6,6 0 0,1 7,6M6,9V11H4V13H6V15H8V13H10V11H8V9H6M15.5,12A1.5,1.5 0 0,0 14,13.5A1.5,1.5 0 0,0 15.5,15A1.5,1.5 0 0,0 17,13.5A1.5,1.5 0 0,0 15.5,12M18.5,9A1.5,1.5 0 0,0 17,10.5A1.5,1.5 0 0,0 18.5,12A1.5,1.5 0 0,0 20,10.5A1.5,1.5 0 0,0 18.5,9Z","Gauge":"M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12C20,14.4 19,16.5 17.3,18C15.9,16.7 14,16 12,16C10,16 8.2,16.7 6.7,18C5,16.5 4,14.4 4,12A8,8 0 0,1 12,4M14,5.89C13.62,5.9 13.26,6.15 13.1,6.54L11.81,9.77L11.71,10C11,10.13 10.41,10.6 10.14,11.26C9.73,12.29 10.23,13.45 11.26,13.86C12.29,14.27 13.45,13.77 13.86,12.74C14.12,12.08 14,11.32 13.57,10.76L13.67,10.5L14.96,7.29L14.97,7.26C15.17,6.75 14.92,6.17 14.41,5.96C14.28,5.91 14.15,5.89 14,5.89M10,6A1,1 0 0,0 9,7A1,1 0 0,0 10,8A1,1 0 0,0 11,7A1,1 0 0,0 10,6M7,9A1,1 0 0,0 6,10A1,1 0 0,0 7,11A1,1 0 0,0 8,10A1,1 0 0,0 7,9M17,9A1,1 0 0,0 16,10A1,1 0 0,0 17,11A1,1 0 0,0 18,10A1,1 0 0,0 17,9Z","GestureTapButton":"M13 5C15.21 5 17 6.79 17 9C17 10.5 16.2 11.77 15 12.46V11.24C15.61 10.69 16 9.89 16 9C16 7.34 14.66 6 13 6S10 7.34 10 9C10 9.89 10.39 10.69 11 11.24V12.46C9.8 11.77 9 10.5 9 9C9 6.79 10.79 5 13 5M20 20.5C19.97 21.32 19.32 21.97 18.5 22H13C12.62 22 12.26 21.85 12 21.57L8 17.37L8.74 16.6C8.93 16.39 9.2 16.28 9.5 16.28H9.7L12 18V9C12 8.45 12.45 8 13 8S14 8.45 14 9V13.47L15.21 13.6L19.15 15.79C19.68 16.03 20 16.56 20 17.14V20.5M20 2H4C2.9 2 2 2.9 2 4V12C2 13.11 2.9 14 4 14H8V12L4 12L4 4H20L20 12H18V14H20V13.96L20.04 14C21.13 14 22 13.09 22 12V4C22 2.9 21.11 2 20 2Z","Home":"M10,20V14H14V20H19V12H22L12,3L2,12H5V20H10Z","Lightbulb":"M12,2A7,7 0 0,0 5,9C5,11.38 6.19,13.47 8,14.74V17A1,1 0 0,0 9,18H15A1,1 0 0,0 16,17V14.74C17.81,13.47 19,11.38 19,9A7,7 0 0,0 12,2M9,21A1,1 0 0,0 10,22H14A1,1 0 0,0 15,21V20H9V21Z","LightbulbMultiple":"M17 16V18C17 18.55 16.53 19 16 19H12C11.42 19 11 18.55 11 18V16C8.77 14.34 8.32 11.21 10 9S14.77 6.34 17 8 19.63 12.79 18 15C17.69 15.38 17.35 15.72 17 16M16 20H12V21C12 21.55 12.42 22 13 22H15C15.53 22 16 21.55 16 21M7.66 15H7V16C7 16.55 7.42 17 8 17H9V16.88C8.44 16.33 8 15.7 7.66 15M13.58 5C12.46 2.47 9.5 1.33 7 2.45S3.31 6.5 4.43 9.04C4.77 9.81 5.3 10.5 6 11V13C6 13.55 6.42 14 7 14H7.28C7.07 13.35 6.97 12.68 7 12C6.97 8.29 9.87 5.21 13.58 5Z","LightbulbOff":"M12,2C9.76,2 7.78,3.05 6.5,4.68L16.31,14.5C17.94,13.21 19,11.24 19,9A7,7 0 0,0 12,2M3.28,4L2,5.27L5.04,8.3C5,8.53 5,8.76 5,9C5,11.38 6.19,13.47 8,14.74V17A1,1 0 0,0 9,18H14.73L18.73,22L20,20.72L3.28,4M9,20V21A1,1 0 0,0 10,22H14A1,1 0 0,0 15,21V20H9Z","Lock":"M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z","Magnify":"M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z","Menu":"M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z","Minus":"M19,13H5V11H19V13Z","MoleculeCo2":"M5,7A2,2 0 0,0 3,9V15A2,2 0 0,0 5,17H8V15H5V9H8V7H5M11,7A2,2 0 0,0 9,9V15A2,2 0 0,0 11,17H13A2,2 0 0,0 15,15V9A2,2 0 0,0 13,7H11M11,9H13V15H11V9M16,10.5V12H19V13.5H17.5A1.5,1.5 0 0,0 16,15V18H20.5V16.5H17.5V15H19A1.5,1.5 0 0,0 20.5,13.5V12A1.5,1.5 0 0,0 19,10.5H16Z","MonitorOff":"M14,18V20H16V22H8V20H10V18H3A2,2 0 0,1 1,16V4L0,3L1.41,1.58L22.16,22.34L20.75,23.75L15,18H14M3,16H13L3,6V16M21,2A2,2 0 0,1 23,4V16A2,2 0 0,1 21,18H20.66L18.66,16H21V4H6.66L4.66,2H21Z","MotionSensor":"M10,0.2C9,0.2 8.2,1 8.2,2C8.2,3 9,3.8 10,3.8C11,3.8 11.8,3 11.8,2C11.8,1 11,0.2 10,0.2M15.67,1A7.33,7.33 0 0,0 23,8.33V7A6,6 0 0,1 17,1H15.67M18.33,1C18.33,3.58 20.42,5.67 23,5.67V4.33C21.16,4.33 19.67,2.84 19.67,1H18.33M21,1A2,2 0 0,0 23,3V1H21M7.92,4.03C7.75,4.03 7.58,4.06 7.42,4.11L2,5.8V11H3.8V7.33L5.91,6.67L2,22H3.8L6.67,13.89L9,17V22H10.8V15.59L8.31,11.05L9.04,8.18L10.12,10H15V8.2H11.38L9.38,4.87C9.08,4.37 8.54,4.03 7.92,4.03Z","PackageUp":"M20.54,5.23C20.83,5.57 21,6 21,6.5V19A2,2 0 0,1 19,21H5A2,2 0 0,1 3,19V6.5C3,6 3.17,5.57 3.46,5.23L4.84,3.55C5.12,3.21 5.53,3 6,3H18C18.47,3 18.88,3.21 19.15,3.55L20.54,5.23M5.12,5H18.87L17.93,4H5.93L5.12,5M12,9.5L6.5,15H10V17H14V15H17.5L12,9.5Z","Palette":"M17.5,12A1.5,1.5 0 0,1 16,10.5A1.5,1.5 0 0,1 17.5,9A1.5,1.5 0 0,1 19,10.5A1.5,1.5 0 0,1 17.5,12M14.5,8A1.5,1.5 0 0,1 13,6.5A1.5,1.5 0 0,1 14.5,5A1.5,1.5 0 0,1 16,6.5A1.5,1.5 0 0,1 14.5,8M9.5,8A1.5,1.5 0 0,1 8,6.5A1.5,1.5 0 0,1 9.5,5A1.5,1.5 0 0,1 11,6.5A1.5,1.5 0 0,1 9.5,8M6.5,12A1.5,1.5 0 0,1 5,10.5A1.5,1.5 0 0,1 6.5,9A1.5,1.5 0 0,1 8,10.5A1.5,1.5 0 0,1 6.5,12M12,3A9,9 0 0,0 3,12A9,9 0 0,0 12,21A1.5,1.5 0 0,0 13.5,19.5C13.5,19.11 13.35,18.76 13.11,18.5C12.88,18.23 12.73,17.88 12.73,17.5A1.5,1.5 0 0,1 14.23,16H16A5,5 0 0,0 21,11C21,6.58 16.97,3 12,3Z","Paw":"M8.35,3C9.53,2.83 10.78,4.12 11.14,5.9C11.5,7.67 10.85,9.25 9.67,9.43C8.5,9.61 7.24,8.32 6.87,6.54C6.5,4.77 7.17,3.19 8.35,3M15.5,3C16.69,3.19 17.35,4.77 17,6.54C16.62,8.32 15.37,9.61 14.19,9.43C13,9.25 12.35,7.67 12.72,5.9C13.08,4.12 14.33,2.83 15.5,3M3,7.6C4.14,7.11 5.69,8 6.5,9.55C7.26,11.13 7,12.79 5.87,13.28C4.74,13.77 3.2,12.89 2.41,11.32C1.62,9.75 1.9,8.08 3,7.6M21,7.6C22.1,8.08 22.38,9.75 21.59,11.32C20.8,12.89 19.26,13.77 18.13,13.28C17,12.79 16.74,11.13 17.5,9.55C18.31,8 19.86,7.11 21,7.6M19.33,18.38C19.37,19.32 18.65,20.36 17.79,20.75C16,21.57 13.88,19.87 11.89,19.87C9.9,19.87 7.76,21.64 6,20.75C5,20.26 4.31,18.96 4.44,17.88C4.62,16.39 6.41,15.59 7.47,14.5C8.88,13.09 9.88,10.44 11.89,10.44C13.89,10.44 14.95,13.05 16.3,14.5C17.41,15.72 19.26,16.75 19.33,18.38Z","Play":"M8,5.14V19.14L19,12.14L8,5.14Z","Plus":"M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z","Power":"M16.56,5.44L15.11,6.89C16.84,7.94 18,9.83 18,12A6,6 0 0,1 12,18A6,6 0 0,1 6,12C6,9.83 7.16,7.94 8.88,6.88L7.44,5.44C5.36,6.88 4,9.28 4,12A8,8 0 0,0 12,20A8,8 0 0,0 20,12C20,9.28 18.64,6.88 16.56,5.44M13,3H11V13H13","PowerPlug":"M16,7V3H14V7H10V3H8V7H8C7,7 6,8 6,9V14.5L9.5,18V21H14.5V18L18,14.5V9C18,8 17,7 16,7Z","RadioboxMarked":"M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,7A5,5 0 0,0 7,12A5,5 0 0,0 12,17A5,5 0 0,0 17,12A5,5 0 0,0 12,7Z","RayVertex":"M2,11H9.17C9.58,9.83 10.69,9 12,9C13.31,9 14.42,9.83 14.83,11H22V13H14.83C14.42,14.17 13.31,15 12,15C10.69,15 9.58,14.17 9.17,13H2V11Z","Restart":"M12,4C14.1,4 16.1,4.8 17.6,6.3C20.7,9.4 20.7,14.5 17.6,17.6C15.8,19.5 13.3,20.2 10.9,19.9L11.4,17.9C13.1,18.1 14.9,17.5 16.2,16.2C18.5,13.9 18.5,10.1 16.2,7.7C15.1,6.6 13.5,6 12,6V10.6L7,5.6L12,0.6V4M6.3,17.6C3.7,15 3.3,11 5.1,7.9L6.6,9.4C5.5,11.6 5.9,14.4 7.8,16.2C8.3,16.7 8.9,17.1 9.6,17.4L9,19.4C8,19 7.1,18.4 6.3,17.6Z","Robot":"M12,2A2,2 0 0,1 14,4C14,4.74 13.6,5.39 13,5.73V7H14A7,7 0 0,1 21,14H22A1,1 0 0,1 23,15V18A1,1 0 0,1 22,19H21V20A2,2 0 0,1 19,22H5A2,2 0 0,1 3,20V19H2A1,1 0 0,1 1,18V15A1,1 0 0,1 2,14H3A7,7 0 0,1 10,7H11V5.73C10.4,5.39 10,4.74 10,4A2,2 0 0,1 12,2M7.5,13A2.5,2.5 0 0,0 5,15.5A2.5,2.5 0 0,0 7.5,18A2.5,2.5 0 0,0 10,15.5A2.5,2.5 0 0,0 7.5,13M16.5,13A2.5,2.5 0 0,0 14,15.5A2.5,2.5 0 0,0 16.5,18A2.5,2.5 0 0,0 19,15.5A2.5,2.5 0 0,0 16.5,13Z","RobotOff":"M23 15V18C23 18.5 22.64 18.88 22.17 18.97L18.97 15.77C19 15.68 19 15.59 19 15.5C19 14.12 17.88 13 16.5 13C16.41 13 16.32 13 16.23 13.03L10.2 7H11V5.73C10.4 5.39 10 4.74 10 4C10 2.9 10.9 2 12 2S14 2.9 14 4C14 4.74 13.6 5.39 13 5.73V7H14C17.87 7 21 10.13 21 14H22C22.55 14 23 14.45 23 15M22.11 21.46L20.84 22.73L19.89 21.78C19.62 21.92 19.32 22 19 22H5C3.9 22 3 21.11 3 20V19H2C1.45 19 1 18.55 1 18V15C1 14.45 1.45 14 2 14H3C3 11.53 4.29 9.36 6.22 8.11L1.11 3L2.39 1.73L22.11 21.46M10 15.5C10 14.12 8.88 13 7.5 13S5 14.12 5 15.5 6.12 18 7.5 18 10 16.88 10 15.5M16.07 17.96L14.04 15.93C14.23 16.97 15.04 17.77 16.07 17.96Z","ScriptText":"M17.8,20C17.4,21.2 16.3,22 15,22H5C3.3,22 2,20.7 2,19V18H5L14.2,18C14.6,19.2 15.7,20 17,20H17.8M19,2C20.7,2 22,3.3 22,5V6H20V5C20,4.4 19.6,4 19,4C18.4,4 18,4.4 18,5V18H17C16.4,18 16,17.6 16,17V16H5V5C5,3.3 6.3,2 8,2H19M8,6V8H15V6H8M8,10V12H14V10H8Z","ScriptTextPlay":"M13.8 22H5C3.3 22 2 20.7 2 19V18H13.1C13 18.3 13 18.7 13 19C13 20.1 13.3 21.1 13.8 22M13.8 16H5V5C5 3.3 6.3 2 8 2H19C20.7 2 22 3.3 22 5V6H20V5C20 4.4 19.6 4 19 4S18 4.4 18 5V13.1C16.2 13.4 14.7 14.5 13.8 16M8 8H15V6H8V8M8 12H14V10H8V12M17 16V22L22 19L17 16Z","Shape":"M11,13.5V21.5H3V13.5H11M12,2L17.5,11H6.5L12,2M17.5,13C20,13 22,15 22,17.5C22,20 20,22 17.5,22C15,22 13,20 13,17.5C13,15 15,13 17.5,13Z","Sofa":"M12.5 7C12.5 5.89 13.39 5 14.5 5H18C19.1 5 20 5.9 20 7V9.16C18.84 9.57 18 10.67 18 11.97V14H12.5V7M6 11.96V14H11.5V7C11.5 5.89 10.61 5 9.5 5H6C4.9 5 4 5.9 4 7V9.15C5.16 9.56 6 10.67 6 11.96M20.66 10.03C19.68 10.19 19 11.12 19 12.12V15H5V12C5 10.9 4.11 10 3 10S1 10.9 1 12V17C1 18.1 1.9 19 3 19V21H5V19H19V21H21V19C22.1 19 23 18.1 23 17V12C23 10.79 21.91 9.82 20.66 10.03Z","Speaker":"M12,12A3,3 0 0,0 9,15A3,3 0 0,0 12,18A3,3 0 0,0 15,15A3,3 0 0,0 12,12M12,20A5,5 0 0,1 7,15A5,5 0 0,1 12,10A5,5 0 0,1 17,15A5,5 0 0,1 12,20M12,4A2,2 0 0,1 14,6A2,2 0 0,1 12,8C10.89,8 10,7.1 10,6C10,4.89 10.89,4 12,4M17,2H7C5.89,2 5,2.89 5,4V20A2,2 0 0,0 7,22H17A2,2 0 0,0 19,20V4C19,2.89 18.1,2 17,2Z","SpeakerOff":"M2,5.27L3.28,4L21,21.72L19.73,23L18.27,21.54C17.93,21.83 17.5,22 17,22H7C5.89,22 5,21.1 5,20V8.27L2,5.27M12,18A3,3 0 0,1 9,15C9,14.24 9.28,13.54 9.75,13L8.33,11.6C7.5,12.5 7,13.69 7,15A5,5 0 0,0 12,20C13.31,20 14.5,19.5 15.4,18.67L14,17.25C13.45,17.72 12.76,18 12,18M17,15A5,5 0 0,0 12,10H11.82L5.12,3.3C5.41,2.54 6.14,2 7,2H17A2,2 0 0,1 19,4V17.18L17,15.17V15M12,4C10.89,4 10,4.89 10,6A2,2 0 0,0 12,8A2,2 0 0,0 14,6C14,4.89 13.1,4 12,4Z","TextureBox":"M20 2H4C2.9 2 2 2.9 2 4V20C2 21.11 2.9 22 4 22H20C21.11 22 22 21.11 22 20V4C22 2.9 21.11 2 20 2M4 6L6 4H10.9L4 10.9V6M4 13.7L13.7 4H18.6L4 18.6V13.7M20 18L18 20H13.1L20 13.1V18M20 10.3L10.3 20H5.4L20 5.4V10.3Z","Thermometer":"M15 13V5A3 3 0 0 0 9 5V13A5 5 0 1 0 15 13M12 4A1 1 0 0 1 13 5V8H11V5A1 1 0 0 1 12 4Z","Thermostat":"M16.95,16.95L14.83,14.83C15.55,14.1 16,13.1 16,12C16,11.26 15.79,10.57 15.43,10L17.6,7.81C18.5,9 19,10.43 19,12C19,13.93 18.22,15.68 16.95,16.95M12,5C13.57,5 15,5.5 16.19,6.4L14,8.56C13.43,8.21 12.74,8 12,8A4,4 0 0,0 8,12C8,13.1 8.45,14.1 9.17,14.83L7.05,16.95C5.78,15.68 5,13.93 5,12A7,7 0 0,1 12,5M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12C22,6.47 17.5,2 12,2Z","TimerOutline":"M12,20A7,7 0 0,1 5,13A7,7 0 0,1 12,6A7,7 0 0,1 19,13A7,7 0 0,1 12,20M19.03,7.39L20.45,5.97C20,5.46 19.55,5 19.04,4.56L17.62,6C16.07,4.74 14.12,4 12,4A9,9 0 0,0 3,13A9,9 0 0,0 12,22C17,22 21,17.97 21,13C21,10.88 20.26,8.93 19.03,7.39M11,14H13V8H11M15,1H9V3H15V1Z","ToggleSwitch":"M17,7H7A5,5 0 0,0 2,12A5,5 0 0,0 7,17H17A5,5 0 0,0 22,12A5,5 0 0,0 17,7M17,15A3,3 0 0,1 14,12A3,3 0 0,1 17,9A3,3 0 0,1 20,12A3,3 0 0,1 17,15Z","ToggleSwitchOff":"M17,7H7A5,5 0 0,0 2,12A5,5 0 0,0 7,17H17A5,5 0 0,0 22,12A5,5 0 0,0 17,7M7,15A3,3 0 0,1 4,12A3,3 0 0,1 7,9A3,3 0 0,1 10,12A3,3 0 0,1 7,15Z","UnfoldLessHorizontal":"M16.59,5.41L15.17,4L12,7.17L8.83,4L7.41,5.41L12,10M7.41,18.59L8.83,20L12,16.83L15.17,20L16.58,18.59L12,14L7.41,18.59Z","UnfoldMoreHorizontal":"M12,18.17L8.83,15L7.42,16.41L12,21L16.59,16.41L15.17,15M12,5.83L15.17,9L16.58,7.59L12,3L7.41,7.59L8.83,9L12,5.83Z","Upload":"M9,16V10H5L12,3L19,10H15V16H9M5,20V18H19V20H5Z","WaterBoiler":"M8 2C6.89 2 6 2.89 6 4V16C6 17.11 6.89 18 8 18H9V20H6V22H9C10.11 22 11 21.11 11 20V18H13V20C13 21.11 13.89 22 15 22H18V20H15V18H16C17.11 18 18 17.11 18 16V4C18 2.89 17.11 2 16 2H8M12 4.97A2 2 0 0 1 14 6.97A2 2 0 0 1 12 8.97A2 2 0 0 1 10 6.97A2 2 0 0 1 12 4.97M10 14.5H14V16H10V14.5Z","WaterPercent":"M12,3.25C12,3.25 6,10 6,14C6,17.32 8.69,20 12,20A6,6 0 0,0 18,14C18,10 12,3.25 12,3.25M14.47,9.97L15.53,11.03L9.53,17.03L8.47,15.97M9.75,10A1.25,1.25 0 0,1 11,11.25A1.25,1.25 0 0,1 9.75,12.5A1.25,1.25 0 0,1 8.5,11.25A1.25,1.25 0 0,1 9.75,10M14.25,14.5A1.25,1.25 0 0,1 15.5,15.75A1.25,1.25 0 0,1 14.25,17A1.25,1.25 0 0,1 13,15.75A1.25,1.25 0 0,1 14.25,14.5Z","WeatherPartlyCloudy":"M12.74,5.47C15.1,6.5 16.35,9.03 15.92,11.46C17.19,12.56 18,14.19 18,16V16.17C18.31,16.06 18.65,16 19,16A3,3 0 0,1 22,19A3,3 0 0,1 19,22H6A4,4 0 0,1 2,18A4,4 0 0,1 6,14H6.27C5,12.45 4.6,10.24 5.5,8.26C6.72,5.5 9.97,4.24 12.74,5.47M11.93,7.3C10.16,6.5 8.09,7.31 7.31,9.07C6.85,10.09 6.93,11.22 7.41,12.13C8.5,10.83 10.16,10 12,10C12.7,10 13.38,10.12 14,10.34C13.94,9.06 13.18,7.86 11.93,7.3M13.55,3.64C13,3.4 12.45,3.23 11.88,3.12L14.37,1.82L15.27,4.71C14.76,4.29 14.19,3.93 13.55,3.64M6.09,4.44C5.6,4.79 5.17,5.19 4.8,5.63L4.91,2.82L7.87,3.5C7.25,3.71 6.65,4.03 6.09,4.44M18,9.71C17.91,9.12 17.78,8.55 17.59,8L19.97,9.5L17.92,11.73C18.03,11.08 18.05,10.4 18,9.71M3.04,11.3C3.11,11.9 3.24,12.47 3.43,13L1.06,11.5L3.1,9.28C3,9.93 2.97,10.61 3.04,11.3M19,18H16V16A4,4 0 0,0 12,12A4,4 0 0,0 8,16H6A2,2 0 0,0 4,18A2,2 0 0,0 6,20H19A1,1 0 0,0 20,19A1,1 0 0,0 19,18Z","WhiteBalanceSunny":"M3.55 19.09L4.96 20.5L6.76 18.71L5.34 17.29M12 6C8.69 6 6 8.69 6 12S8.69 18 12 18 18 15.31 18 12C18 8.68 15.31 6 12 6M20 13H23V11H20M17.24 18.71L19.04 20.5L20.45 19.09L18.66 17.29M20.45 5L19.04 3.6L17.24 5.39L18.66 6.81M13 1H11V4H13M6.76 5.39L4.96 3.6L3.55 5L5.34 6.81L6.76 5.39M1 13H4V11H1M13 20H11V23H13","Wifi":"M12,21L15.6,16.2C14.6,15.45 13.35,15 12,15C10.65,15 9.4,15.45 8.4,16.2L12,21M12,3C7.95,3 4.21,4.34 1.2,6.6L3,9C5.5,7.12 8.62,6 12,6C15.38,6 18.5,7.12 21,9L22.8,6.6C19.79,4.34 16.05,3 12,3M12,9C9.3,9 6.81,9.89 4.8,11.4L6.6,13.8C8.1,12.67 9.97,12 12,12C14.03,12 15.9,12.67 17.4,13.8L19.2,11.4C17.19,9.89 14.7,9 12,9Z","WindowShutter":"M3 4H21V8H19V20H17V8H7V20H5V8H3V4M8 9H16V11H8V9M8 12H16V14H8V12M8 15H16V17H8V15M8 18H16V20H8V18Z"};

  var S = null, cfg = null, dirty = false;
  var page = 'tab', sel = 0, search = '', iconsOpen = false, confirmDel = false, focusGrip = null;
  var prefs = { group: 'area', area: '', hidden: false, chips: { lights: [], sensors: [], graph: [] }, fold: {} };
  try { var saved = JSON.parse(localStorage.getItem('dash-editor-prefs') || 'null'); if (saved && typeof saved === 'object') {
    Object.keys(prefs).forEach(function (k) { if (saved[k] !== undefined && typeof saved[k] === typeof prefs[k]) prefs[k] = saved[k]; }); } } catch (e) { /* inget sparat */ }
  ['lights', 'sensors', 'graph'].forEach(function (k) { if (!Array.isArray(prefs.chips[k])) prefs.chips[k] = []; });
  function savePrefs() { try { localStorage.setItem('dash-editor-prefs', JSON.stringify(prefs)); } catch (e) { /* privat läge */ } }

  var $app = document.getElementById('app'), $nav = document.getElementById('nav'), $title = document.getElementById('title'),
      $conn = document.getElementById('conn'), $bar = document.getElementById('bar'), $msg = document.getElementById('msg'),
      $save = document.getElementById('save'), $undo = document.getElementById('undo'), $dlg = document.getElementById('dlg'),
      $toast = document.getElementById('toast'), $menu = document.getElementById('menu'), $scrim = document.getElementById('scrim'),
      $topact = document.getElementById('topact');

  // ---------------------------------------------------------------- små hjälpfunktioner
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
  function icon(name, cls) {
    var NS = 'http://www.w3.org/2000/svg';
    var s = document.createElementNS(NS, 'svg');
    s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('class', 'i' + (cls ? ' ' + cls : '')); s.setAttribute('aria-hidden', 'true');
    var p = document.createElementNS(NS, 'path'); p.setAttribute('d', ICONS[name] || ICONS.Shape); s.appendChild(p);
    return s;
  }
  function select(options, value, onchange, label) {
    var s = h('select', { onchange: function () { onchange(this.value); }, 'aria-label': label || null });
    options.forEach(function (o) { s.appendChild(h('option', { value: o[0] }, o[1])); });
    s.value = String(value);
    return s;
  }
  function copy(o) { return JSON.parse(JSON.stringify(o)); }
  function dom(id) { return String(id || '').split('.')[0]; }
  function toast(text, bad) {
    $toast.textContent = text; $toast.className = bad ? 'bad' : ''; $toast.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(function () { $toast.hidden = true; }, bad ? 6000 : 3500);
  }
  function setDirty(v) {
    dirty = v; $bar.hidden = !v; $save.disabled = false; $msg.textContent = v ? 'Osparade ändringar' : '';
  }
  function entMap() { var m = {}; ((S && S.entities) || []).forEach(function (e) { m[e.id] = e; }); return m; }
  function areaMap() { var m = {}; ((S && S.areas) || []).forEach(function (a) { m[a.id] = a; }); return m; }
  function pascal(mdi) { return String(mdi || '').split('-').map(function (w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join(''); }

  // ---------------------------------------------------------------- vad en entitet är
  var LAMPS = ['light', 'switch'], ACTIONS = ['scene', 'script', 'button', 'input_button'];
  var DOM_NAME = { light: 'Lampa', switch: 'Strömbrytare', fan: 'Fläkt', input_boolean: 'Hjälpare (av/på)', automation: 'Automation',
    scene: 'Scen', script: 'Skript', button: 'Knapp', input_button: 'Hjälpare (knapp)', sensor: 'Sensor', binary_sensor: 'Binär sensor',
    input_number: 'Hjälpare (tal)', counter: 'Hjälpare (räknare)', input_select: 'Hjälpare (val)', input_text: 'Hjälpare (text)',
    input_datetime: 'Hjälpare (datum och tid)', number: 'Inställning (tal)', select: 'Inställning (val)', climate: 'Klimat',
    cover: 'Jalusi eller port', lock: 'Lås', media_player: 'Mediaspelare', person: 'Person', device_tracker: 'Spårare',
    weather: 'Väder', sun: 'Sol', update: 'Uppdatering', timer: 'Timer', humidifier: 'Luftfuktare', water_heater: 'Varmvatten' };
  var ENERGY_DC = ['power', 'energy', 'voltage', 'current', 'power_factor', 'apparent_power', 'reactive_power', 'frequency', 'gas', 'water'];
  var ENERGY_UNIT = ['W', 'kW', 'kWh', 'Wh', 'MWh', 'V', 'A', 'mA', 'VA', 'var', 'Hz'];
  var TYPES = {
    lights: [
      { k: 'light', label: 'Lampor', icon: 'Lightbulb', doms: ['light'] },
      { k: 'switch', label: 'Strömbrytare', icon: 'PowerPlug', doms: ['switch'] },
      { k: 'scene', label: 'Scener', icon: 'Palette', doms: ['scene'] },
      { k: 'automation', label: 'Automationer', icon: 'Robot', doms: ['automation'] },
      { k: 'script', label: 'Skript', icon: 'ScriptText', doms: ['script'] },
      { k: 'helper', label: 'Hjälpare', icon: 'ToggleSwitch', doms: ['input_boolean', 'input_button'] },
      { k: 'media', label: 'Media', icon: 'Speaker', doms: ['media_player'] },
      { k: 'climate', label: 'Klimat och fläktar', icon: 'Thermostat', doms: ['climate', 'humidifier', 'fan'] },
      { k: 'button', label: 'Knappar', icon: 'GestureTapButton', doms: ['button'] }],
    sensors: [
      { k: 'temp', label: 'Temperatur', icon: 'Thermometer', doms: ['sensor'], cat: 'temp' },
      { k: 'humidity', label: 'Luftfuktighet', icon: 'WaterPercent', doms: ['sensor'], cat: 'humidity' },
      { k: 'energy', label: 'El och energi', icon: 'Flash', doms: ['sensor'], cat: 'energy' },
      { k: 'battery', label: 'Batteri', icon: 'Battery', doms: ['sensor'], cat: 'battery' },
      { k: 'sensor', label: 'Övriga sensorer', icon: 'Gauge', doms: ['sensor'], cat: 'other' },
      { k: 'binary', label: 'Binära sensorer', icon: 'RadioboxMarked', doms: ['binary_sensor'] },
      { k: 'helper', label: 'Hjälpare', icon: 'RayVertex', doms: ['input_number', 'counter', 'input_select', 'input_text', 'input_datetime'] },
      { k: 'other', label: 'Annat', icon: 'Shape', doms: ['number', 'select', 'climate', 'cover', 'lock', 'media_player', 'person', 'device_tracker',
                                                        'weather', 'sun', 'update', 'timer', 'fan', 'humidifier', 'water_heater'] }],
    graph: [
      { k: 'temp', label: 'Temperatur', icon: 'Thermometer', doms: ['sensor'], cat: 'temp' },
      { k: 'humidity', label: 'Luftfuktighet', icon: 'WaterPercent', doms: ['sensor'], cat: 'humidity' },
      { k: 'energy', label: 'El och energi', icon: 'Flash', doms: ['sensor'], cat: 'energy' },
      { k: 'battery', label: 'Batteri', icon: 'Battery', doms: ['sensor'], cat: 'battery' },
      { k: 'sensor', label: 'Övriga sensorer', icon: 'Gauge', doms: ['sensor'], cat: 'other' },
      { k: 'helper', label: 'Hjälpare och inställningar', icon: 'RayVertex', doms: ['input_number', 'counter', 'number'] }]
  };
  var TYPE_DESC = {
    lights: 'Knappar: lampor, strömbrytare, scener, automationer, skript, hjälpare och media',
    sensors: 'Värden: sensorer, binära sensorer, hjälpare, väder, personer och annat',
    graph: 'Graf: hur värden har ändrats över tid, med max och min'
  };
  function isTemp(e) { return e.dc === 'temperature' || ['°C', '°F', 'K'].indexOf(e.unit) >= 0; }
  function sensorCat(e) {
    if (isTemp(e)) return 'temp';
    if (e.dc === 'humidity' || e.dc === 'moisture') return 'humidity';
    if (ENERGY_DC.indexOf(e.dc) >= 0 || ENERGY_UNIT.indexOf(e.unit) >= 0) return 'energy';
    if (e.dc === 'battery') return 'battery';
    return 'other';
  }
  function typeOf(e, tabType) {
    var d = dom(e.id), list = TYPES[tabType];
    if (tabType === 'graph' && !(e.num || e.unit)) return null;       // grafen behöver tal
    for (var i = 0; i < list.length; i++) {
      var t = list[i];
      if (t.doms.indexOf(d) < 0) continue;
      if (t.cat === undefined || t.cat === sensorCat(e)) return t.k;
    }
    return null;
  }
  function entIcon(e, id) {
    var d = dom(e ? e.id : id);
    if (e && e.icon && ICONS[pascal(e.icon)]) return pascal(e.icon);
    var on = e && e.state === 'on';
    switch (d) {
      case 'light': return on ? 'Lightbulb' : 'LightbulbOff';
      case 'switch': return 'PowerPlug';
      case 'fan': return 'Fan';
      case 'input_boolean': return on ? 'ToggleSwitch' : 'ToggleSwitchOff';
      case 'automation': return on ? 'Robot' : 'RobotOff';
      case 'scene': return 'Palette';
      case 'script': return 'ScriptText';
      case 'button': case 'input_button': return 'GestureTapButton';
      case 'binary_sensor':
        if (e && ['door', 'garage_door', 'window', 'opening'].indexOf(e.dc) >= 0) return 'DoorOpen';
        if (e && ['motion', 'occupancy', 'presence'].indexOf(e.dc) >= 0) return 'MotionSensor';
        return 'RadioboxMarked';
      case 'input_number': case 'number': return 'RayVertex';
      case 'counter': return 'Counter';
      case 'input_select': case 'select': return 'FormatListBulleted';
      case 'input_text': return 'FormTextbox';
      case 'input_datetime': return 'CalendarClock';
      case 'climate': return 'Thermostat';
      case 'humidifier': return 'AirHumidifier';
      case 'cover': return 'WindowShutter';
      case 'lock': return 'Lock';
      case 'media_player': return e && (e.state === 'off' || e.state === 'standby') ? 'SpeakerOff' : 'Speaker';
      case 'person': case 'device_tracker': return 'Account';
      case 'weather': return 'WeatherPartlyCloudy';
      case 'sun': return 'WhiteBalanceSunny';
      case 'update': return 'PackageUp';
      case 'timer': return 'TimerOutline';
      case 'water_heater': return 'WaterBoiler';
      case 'sensor':
        if (!e) return 'Gauge';
        var c = sensorCat(e);
        if (c === 'temp') return 'Thermometer';
        if (c === 'humidity') return 'WaterPercent';
        if (c === 'energy') return 'Flash';
        if (c === 'battery') return 'Battery';
        if (e.dc === 'signal_strength') return 'Wifi';
        if (e.dc === 'illuminance' || e.unit === 'lx') return 'Brightness5';
        if (e.dc === 'carbon_dioxide') return 'MoleculeCo2';
        return 'Gauge';
    }
    return 'Shape';
  }
  // ikonen som panelen själv ritar i rutan (lampor och strömbrytare: glödlampa)
  function panelIcon(e, id) {
    if (amber(id)) return e && e.state === 'on' ? 'Lightbulb' : 'LightbulbOff';
    var d = dom(id);
    if (d === 'script') return e && e.state === 'on' ? 'ScriptTextPlay' : 'ScriptText';
    if (d === 'fan') return e && e.state === 'on' ? 'Fan' : 'FanOff';
    if (d === 'humidifier') return e && e.state === 'on' ? 'AirHumidifier' : 'AirHumidifierOff';
    return entIcon(e ? { id: e.id, state: e.state, dc: e.dc, unit: e.unit } : null, id);
  }
  var BIN = { door: ['Öppen', 'Stängd'], garage_door: ['Öppen', 'Stängd'], window: ['Öppet', 'Stängt'], opening: ['Öppen', 'Stängd'],
    motion: ['Rörelse', 'Ingen rörelse'], occupancy: ['Upptaget', 'Ledigt'], presence: ['Hemma', 'Borta'], moisture: ['Fukt', 'Torrt'],
    battery: ['Låg', 'Normal'], connectivity: ['Ansluten', 'Frånkopplad'], problem: ['Problem', 'OK'], lock: ['Olåst', 'Låst'],
    smoke: ['Rök', 'Ingen rök'], gas: ['Gas', 'Ingen gas'], light: ['Ljust', 'Mörkt'], running: ['Igång', 'Stannad'], plug: ['Inkopplad', 'Urkopplad'] };
  var STATE_TXT = {
    cover: { open: 'Öppen', closed: 'Stängd', opening: 'Öppnas', closing: 'Stängs' },
    lock: { locked: 'Låst', unlocked: 'Olåst', locking: 'Låser', unlocking: 'Låser upp', jammed: 'Fastnat' },
    media_player: { off: 'Av', on: 'På', playing: 'Spelar', paused: 'Pausad', idle: 'Inaktiv', standby: 'Vila', buffering: 'Buffrar' },
    person: { home: 'Hemma', not_home: 'Borta' }, device_tracker: { home: 'Hemma', not_home: 'Borta' },
    sun: { above_horizon: 'Uppe', below_horizon: 'Nere' }, update: { on: 'Uppdatering finns', off: 'Senaste' },
    timer: { idle: 'Inaktiv', active: 'Igång', paused: 'Pausad' },
    climate: { off: 'Av', heat: 'Värme', cool: 'Kyla', auto: 'Auto', heat_cool: 'Värme och kyla', dry: 'Avfuktning', fan_only: 'Fläkt' },
    weather: { sunny: 'Soligt', 'clear-night': 'Klart', cloudy: 'Molnigt', partlycloudy: 'Halvklart', rainy: 'Regn', pouring: 'Skyfall',
      snowy: 'Snö', 'snowy-rainy': 'Snöblandat regn', fog: 'Dimma', hail: 'Hagel', lightning: 'Åska', 'lightning-rainy': 'Åska och regn',
      windy: 'Blåsigt', 'windy-variant': 'Blåsigt', exceptional: 'Extremt väder' }
  };
  function num(v, dec) {
    var n = Number(v);
    if (v === '' || v == null || !isFinite(n)) return null;
    return n.toFixed(dec == null ? 1 : dec).replace('-', '−').replace('.', cfg.locale.decimal_separator);
  }
  // läget som text, som på panelen
  function stateText(e, item) {
    if (!e) return 'Finns inte i Home Assistant';
    var d = dom(e.id), s = e.state;
    if (s === 'unavailable') return 'Ej tillgänglig';
    if (d === 'scene') return 'Scen';
    if (d === 'button' || d === 'input_button') return 'Knapp';
    if (d === 'script') return s === 'on' ? 'Körs' : 'Skript';
    if (s === 'unknown' || s == null) return 'Okänt';
    if (d === 'binary_sensor') { var b = BIN[e.dc] || ['På', 'Av']; return s === 'on' ? b[0] : (s === 'off' ? b[1] : s); }
    if (STATE_TXT[d] && STATE_TXT[d][s]) return STATE_TXT[d][s];
    if (s === 'on') return 'På';
    if (s === 'off') return 'Av';
    if (['sensor', 'input_number', 'counter', 'number'].indexOf(d) >= 0) {
      var v = num(s, item && item.decimals != null ? item.decimals : (d === 'counter' ? 0 : 1));
      if (v != null) return v + (e.unit ? ' ' + e.unit : '');
    }
    if (d === 'input_datetime' && /:\d\d:00$/.test(s)) return s.slice(0, -3);
    return String(s);
  }
  function lit(e) {
    if (!e) return false;
    var d = dom(e.id);
    if (d === 'script') return e.state === 'on';
    if (ACTIONS.indexOf(d) >= 0) return false;
    if (d === 'media_player') return ['off', 'standby', 'unavailable', 'unknown'].indexOf(e.state) < 0;
    if (d === 'climate') return ['off', 'unavailable', 'unknown'].indexOf(e.state) < 0;
    return e.state === 'on';
  }
  function amber(id) { return LAMPS.indexOf(dom(id)) >= 0; }

  // ---------------------------------------------------------------- flikarnas regler (samma som panelen)
  function hasLamp(tab) { return tab.items.some(function (it) { return it.entity_id && amber(it.entity_id); }); }
  function showsAll(tab) { return tab.type === 'lights' && tab.show_all !== false && hasLamp(tab); }
  function limit(tab) {
    if (tab.type === 'graph') return S.config.limits.graph;
    if (tab.type !== 'lights') return S.config.limits.sensors;
    return showsAll(tab) ? S.config.limits.lamps : S.config.limits.lamps_no_all;
  }
  function inTab(tab) { var m = {}; tab.items.forEach(function (it) { if (it.entity_id) m[it.entity_id] = true; }); return m; }
  function newItem(tab, e) {
    var it = { entity_id: e.id };
    if (tab.type !== 'lights') it.decimals = (dom(e.id) === 'counter' || e.dc === 'battery' || e.dc === 'humidity') ? 0 : 1;
    return it;
  }
  function addEntity(tab, e) {
    if (tab.items.length >= limit(tab)) return false;
    if (tab.type === 'lights' && tab.show_all !== false && !hasLamp(tab) && amber(e.id) && tab.items.length >= S.config.limits.lamps) {
      tab.show_all = false;      // en lampa på en flik med sju andra saker: knappen "Alla lampor" får inte plats
    }
    var it = newItem(tab, e), at = -1;
    if (tab.type === 'sensors') tab.items.forEach(function (x, i) { if (x.placeholder && at < 0 && i >= 2) at = i; });
    if (at >= 0) tab.items[at] = it; else tab.items.push(it);
    return true;
  }

  // ---------------------------------------------------------------- ladda och spara
  function load() {
    return fetch('/api/state', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (s) {
      S = s; cfg = copy(s.config); if (sel >= cfg.tabs.length) sel = 0; setDirty(false); render();
    }).catch(function () { $app.textContent = ''; $app.appendChild(h('p', { class: 'bad pad' }, 'Kunde inte hämta inställningarna från panelen. Ladda om sidan.')); });
  }
  function reloadEntities() {
    return fetch('/api/state', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (s) {
      S.entities = s.entities; S.areas = s.areas; S.connected = s.connected; S.error = s.error; S.hidden_known = s.hidden_known; render();
      toast(s.entities ? 'Listan är uppdaterad.' : (s.error || 'Ingen kontakt med Home Assistant.'), !s.entities);
    }).catch(function () { toast('Ingen kontakt med panelen.', true); });
  }
  function save() {
    cfg.tabs.forEach(function (t) { t.items.forEach(function (it) { if (it.name === '') delete it.name; }); });
    $save.disabled = true; $msg.textContent = 'Sparar …';
    fetch('/api/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tabs: cfg.tabs, locale: cfg.locale, ui: cfg.ui }) })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (!res.ok) { $msg.textContent = res.error || 'Kunde inte spara.'; $save.disabled = false; return; }
        S.config = res.config; cfg = copy(res.config); if (sel >= cfg.tabs.length) sel = 0; setDirty(false); render();
        toast('Sparat. Panelen visar ändringarna nu.' + (res.warnings && res.warnings.length ? ' Obs: ' + res.warnings.join('; ') : ''));
      })
      .catch(function () { $msg.textContent = 'Ingen kontakt med panelen. Försök igen.'; $save.disabled = false; });
  }
  $save.addEventListener('click', save);
  $undo.addEventListener('click', function () { cfg = copy(S.config); if (sel >= cfg.tabs.length) sel = 0; setDirty(false); closeDlg(); render(); });
  window.addEventListener('beforeunload', function (e) { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
  $menu.appendChild(icon('Menu'));
  $menu.addEventListener('click', function () { document.body.classList.add('drawer'); $scrim.hidden = false; });
  $scrim.addEventListener('click', closeDrawer);
  function closeDrawer() { document.body.classList.remove('drawer'); $scrim.hidden = true; }

  // ---------------------------------------------------------------- sidomenyn
  function renderNav() {
    $nav.textContent = '';
    $nav.appendChild(h('div', { class: 'navhead' }, 'Flikar på panelen'));
    cfg.tabs.forEach(function (t, i) {
      $nav.appendChild(h('button', { type: 'button', class: 'navitem' + (page === 'tab' && i === sel ? ' on' : ''), 'aria-current': page === 'tab' && i === sel ? 'page' : null,
        onclick: function () { page = 'tab'; sel = i; iconsOpen = false; confirmDel = false; closeDrawer(); render(); window.scrollTo(0, 0); } },
        icon(t.icon), h('span', { class: 'lbl' }, t.title || '(namnlös)'), h('span', { class: 'cnt' }, t.items.length + '/' + limit(t))));
    });
    $nav.appendChild(h('button', { type: 'button', class: 'navitem add', disabled: cfg.tabs.length >= S.config.limits.tabs,
      onclick: function () { closeDrawer(); openNewTab(); } }, icon('Plus'),
      h('span', { class: 'lbl' }, cfg.tabs.length >= S.config.limits.tabs ? 'Högst ' + S.config.limits.tabs + ' flikar' : 'Ny flik')));
    $nav.appendChild(h('div', { class: 'navsep' }));
    $nav.appendChild(h('button', { type: 'button', class: 'navitem' + (page === 'general' ? ' on' : ''),
      onclick: function () { page = 'general'; closeDrawer(); render(); window.scrollTo(0, 0); } }, icon('Cog'), h('span', { class: 'lbl' }, 'Allmänt')));
  }

  // ---------------------------------------------------------------- fliken: rubrik, ikon, knappen "Alla lampor"
  function moveTab(d) {
    var j = sel + d;
    if (j < 0 || j >= cfg.tabs.length) return;
    var t = cfg.tabs[sel]; cfg.tabs[sel] = cfg.tabs[j]; cfg.tabs[j] = t; sel = j; setDirty(true); render();
  }
  function renderTabCard(tab) {
    var card = h('section', { class: 'card' });
    var title = h('input', { class: 'big', type: 'text', value: tab.title, maxlength: '24', 'aria-label': 'Flikens namn', oninput: function () {
      tab.title = this.value; $title.textContent = tab.title || '(namnlös)';
      var on = $nav.querySelector('.navitem.on .lbl'); if (on) on.textContent = tab.title || '(namnlös)'; setDirty(true); } });
    var kind = TYPE_DESC[tab.type];
    var acts = h('div', null,
      h('button', { type: 'button', class: 'iconbtn', title: 'Flytta fliken uppåt (åt vänster på panelen)', 'aria-label': 'Flytta fliken uppåt', disabled: sel === 0,
        onclick: function () { moveTab(-1); } }, icon('ArrowUp')),
      h('button', { type: 'button', class: 'iconbtn', title: 'Flytta fliken nedåt (åt höger på panelen)', 'aria-label': 'Flytta fliken nedåt', disabled: sel === cfg.tabs.length - 1,
        onclick: function () { moveTab(1); } }, icon('ArrowDown')),
      h('button', { type: 'button', class: 'iconbtn', title: 'Ta bort fliken', 'aria-label': 'Ta bort fliken',
        onclick: function () { openDeleteTab(); } }, icon('Delete')));
    card.appendChild(h('div', { class: 'tabhead' },
      h('button', { type: 'button', class: 'iconpick', title: 'Byt ikon', 'aria-label': 'Byt ikon', 'aria-expanded': iconsOpen ? 'true' : 'false',
        onclick: function () { iconsOpen = !iconsOpen; render(); } }, icon(tab.icon)),
      h('div', null, title, h('div', { class: 'tabkind' }, kind)), acts));
    if (iconsOpen) {
      var grid = h('div', { class: 'icons', role: 'group', 'aria-label': 'Ikon för fliken' });
      S.config.icons.forEach(function (n) {
        grid.appendChild(h('button', { type: 'button', class: n === tab.icon ? 'on' : '', 'aria-pressed': n === tab.icon ? 'true' : 'false', title: n,
          onclick: function () { tab.icon = n; iconsOpen = false; setDirty(true); render(); } }, icon(n)));
      });
      card.appendChild(grid);
    }
    if (tab.type === 'lights') card.appendChild(renderAllRow(tab));
    if (tab.type === 'graph') {
      card.appendChild(h('div', { class: 'allrow' }, h('div', { class: 'field' }, h('span', null, 'Intervall när fliken öppnas'),
        seg(S.config.graph_hours.map(function (x) { return [x, HOURS_TXT[x]]; }), tab.hours || 24, function (v) { tab.hours = v; setDirty(true); render(); }))));
    }
    return card;
  }
  function renderAllRow(tab) {
    var lamps = hasLamp(tab), on = tab.show_all !== false;
    var full = !on && tab.items.length > S.config.limits.lamps;
    var sw = h('input', { type: 'checkbox', class: 'switch', checked: on, disabled: full, onchange: function () {
      tab.show_all = this.checked; setDirty(true); render(); } });
    var row = h('div', { class: 'allrow' },
      h('label', { class: 'check' }, sw, h('span', null, 'Visa knappen som slår om alla lampor på fliken')),
      h('label', { class: 'field' }, h('span', null, 'Text på knappen'),
        h('input', { type: 'text', value: tab.all_label || 'Alla lampor', maxlength: '24', disabled: !on, oninput: function () {
          tab.all_label = this.value; setDirty(true); var n = $app.querySelector('.slot.all .nm'); if (n) n.textContent = this.value; } })));
    if (full) row.appendChild(h('p', { class: 'hint warn' }, 'Fliken är full (' + tab.items.length + ' saker). Ta bort en först om knappen ska visas.'));
    else if (on && !lamps) row.appendChild(h('p', { class: 'hint' }, 'Knappen visas när fliken har minst en lampa eller strömbrytare. Den rör inte scener, automationer eller hjälpare.'));
    return row;
  }

  // ---------------------------------------------------------------- förhandsvisning: rutorna som de ligger på panelen
  function renderPreview(tab) {
    var em = entMap(), lim = limit(tab), card = h('section', { class: 'card' });
    card.appendChild(h('div', { class: 'hd' }, h('h2', null, 'På fliken'),
      h('span', { class: 'sub' }, tab.items.length + ' av ' + lim + ' platser')));
    var grid = h('div', { class: 'slots ' + (tab.type === 'lights' ? 'btn8' : 'val') });
    var total = tab.type === 'lights' ? 8 : S.config.limits.sensors;
    tab.items.forEach(function (it, i) { grid.appendChild(tab.type === 'lights' ? buttonSlot(tab, it, i, em) : valueSlot(tab, it, i, em)); });
    var used = tab.items.length;
    if (showsAll(tab)) { grid.appendChild(allSlot(tab)); used++; }
    for (var k = used; k < total; k++) {
      grid.appendChild(h('div', { class: 'slot empty', 'data-idx': String(tab.items.length),
        onclick: function () { var q = document.getElementById('q'); if (q) { q.scrollIntoView({ block: 'center' }); q.focus({ preventScroll: true }); } } },
        k === used ? 'Ledig plats' : ''));
    }
    var bd = h('div', { class: 'bd' }, h('div', { class: 'screen' }, grid));
    var hint = tab.items.length ? ['Dra i ', icon('DragVertical', 's18 inl'), ' för att flytta. Tryck på en ruta för namn och inställningar.']
      : (tab.type === 'lights' ? 'Inget valt än. Kryssa i lampor, scener eller annat i listan nedanför.'
                               : 'Inget valt än. Kryssa i sensorer eller hjälpare i listan nedanför.');
    var foot = h('div', { class: 'prevfoot' }, h('p', { class: 'hint' }, hint));
    if (tab.type === 'sensors') {
      foot.appendChild(h('button', { type: 'button', class: 'btn', disabled: tab.items.length >= lim,
        onclick: function () { tab.items.push({ placeholder: true }); setDirty(true); render(); } }, icon('Plus', 's18'), 'Tom ruta'));
    }
    bd.appendChild(foot);
    card.appendChild(bd);
    return card;
  }
  function grip(tab, i) {
    var g = h('button', { type: 'button', class: 'grip', title: 'Dra för att flytta (eller piltangenterna)', 'aria-label': 'Flytta, plats ' + (i + 1),
      'data-grip': String(i) }, icon('DragVertical', 's20'));
    g.addEventListener('pointerdown', function (ev) { startDrag(ev, tab, i, g); });
    g.addEventListener('click', function (ev) { ev.stopPropagation(); });
    g.addEventListener('keydown', function (ev) {
      var d = { ArrowUp: -1, ArrowLeft: -1, ArrowDown: 1, ArrowRight: 1 }[ev.key];
      if (!d) return;
      ev.preventDefault();
      var j = i + d;
      if (j < 0 || j >= tab.items.length) return;
      moveItem(tab, i, j); focusGrip = j; render();
    });
    return g;
  }
  function moveItem(tab, i, j) {
    var it = tab.items.splice(i, 1)[0];
    tab.items.splice(Math.max(0, Math.min(j, tab.items.length)), 0, it);
    setDirty(true);
  }
  function buttonSlot(tab, it, i, em) {
    var e = em[it.entity_id], on = lit(e);
    var cls = 'slot' + (on ? ' on' + (amber(it.entity_id) ? '' : ' blue') : '') + (!e && S.entities ? ' miss' : '') + (e && e.state === 'unavailable' ? ' na' : '');
    return h('div', { class: cls, 'data-idx': String(i), role: 'button', tabindex: '0', 'aria-label': (it.name || (e && e.name) || it.entity_id) + ', inställningar',
      onclick: function () { openItem(tab, i); }, onkeydown: function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); openItem(tab, i); } } },
      h('span', { class: 'ic' }, icon(panelIcon(e, it.entity_id))),
      h('span', { class: 'tx' }, h('div', { class: 'nm' }, it.name || (e && e.name) || it.entity_id),
        h('div', { class: 'st' }, S.entities ? stateText(e, it) : it.entity_id)),
      grip(tab, i));
  }
  function valueSlot(tab, it, i, em) {
    if (it.placeholder) {
      return h('div', { class: 'slot ph', 'data-idx': String(i), role: 'button', tabindex: '0', 'aria-label': 'Tom ruta, inställningar',
        onclick: function () { openItem(tab, i); }, onkeydown: function (ev) { if (ev.key === 'Enter') openItem(tab, i); } }, 'Tom ruta', grip(tab, i));
    }
    var e = em[it.entity_id], txt = S.entities ? stateText(e, it) : '–', unit = '';
    if (e && e.unit && txt.slice(-e.unit.length - 1) === ' ' + e.unit) { unit = e.unit; txt = txt.slice(0, -e.unit.length - 1); }
    return h('div', { class: 'slot' + (!e && S.entities ? ' miss' : ''), 'data-idx': String(i), role: 'button', tabindex: '0',
      'aria-label': (it.name || (e && e.name) || it.entity_id) + ', inställningar',
      onclick: function () { openItem(tab, i); }, onkeydown: function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); openItem(tab, i); } } },
      h('div', { class: 'row1' }, icon(entIcon(e, it.entity_id), 's18'), h('span', { class: 'nm' }, it.name || (e && e.name) || it.entity_id)),
      h('div', { class: 'val' }, txt, unit ? h('small', null, unit) : null),
      grip(tab, i));
  }
  function allSlot(tab) {
    var em = entMap(), lamps = tab.items.filter(function (it) { return amber(it.entity_id); });
    var n = lamps.filter(function (it) { return lit(em[it.entity_id]); }).length;
    return h('div', { class: 'slot all' + (n ? ' on blue' : ''), role: 'button', tabindex: '0', 'aria-label': 'Knappen för alla lampor',
      onclick: function () { var f = $app.querySelector('.allrow input[type=text]'); if (f && !f.disabled) f.focus(); } },
      h('span', { class: 'ic' }, icon('LightbulbMultiple')),
      h('span', { class: 'tx' }, h('div', { class: 'nm' }, tab.all_label || 'Alla lampor'),
        h('div', { class: 'st' }, n + ' av ' + lamps.length + ' tända')));
  }

  // dra och släpp med greppet (mus och finger)
  function startDrag(ev, tab, i, g) {
    if (ev.button !== undefined && ev.button !== 0) return;
    ev.preventDefault();
    var slot = g.closest('.slot'), grid = slot.parentNode, r = slot.getBoundingClientRect();
    var ghost = slot.cloneNode(true); ghost.classList.add('ghost');
    ghost.style.width = r.width + 'px'; ghost.style.height = r.height + 'px'; ghost.style.left = r.left + 'px'; ghost.style.top = r.top + 'px';
    document.body.appendChild(ghost); slot.classList.add('dragging');
    var dx = ev.clientX - r.left, dy = ev.clientY - r.top, target = null;
    try { g.setPointerCapture(ev.pointerId); } catch (e) { /* äldre webbläsare */ }
    function move(e2) {
      ghost.style.left = (e2.clientX - dx) + 'px'; ghost.style.top = (e2.clientY - dy) + 'px';
      var el = document.elementFromPoint(e2.clientX, e2.clientY), s = el && el.closest ? el.closest('.slot') : null;
      if (s && s.parentNode !== grid) s = null;
      if (s && (s.classList.contains('all') || s.getAttribute('data-idx') === null)) s = null;
      if (target && target !== s) target.classList.remove('target');
      target = s; if (target && target !== slot) target.classList.add('target');
      if (e2.clientY < 60) window.scrollBy(0, -12); else if (e2.clientY > window.innerHeight - 90) window.scrollBy(0, 12);
    }
    function end(e2) {
      g.removeEventListener('pointermove', move); g.removeEventListener('pointerup', end); g.removeEventListener('pointercancel', end);
      ghost.remove(); slot.classList.remove('dragging');
      if (target) target.classList.remove('target');
      if (e2.type === 'pointerup' && target && target !== slot) {
        var j = parseInt(target.getAttribute('data-idx'), 10);
        if (!isNaN(j)) { moveItem(tab, i, Math.min(j, tab.items.length - 1)); render(); }
      }
    }
    g.addEventListener('pointermove', move); g.addEventListener('pointerup', end); g.addEventListener('pointercancel', end);
  }

  // ---------------------------------------------------------------- grafflik: kurvorna och en förhandsvisning ur historiken
  var GCOL = ['#4fc3f7', '#ffb74d', '#81c784'], HOURS_TXT = { 6: '6 tim', 24: '24 tim', 168: '7 dagar', 720: '30 dagar' };
  var histCache = {};
  function renderGraphPreview(tab) {
    var em = entMap(), lim = limit(tab), card = h('section', { class: 'card' });
    card.appendChild(h('div', { class: 'hd' }, h('h2', null, 'I grafen'), h('span', { class: 'sub' }, tab.items.length + ' av ' + lim + ' kurvor')));
    var bd = h('div', { class: 'bd' });
    var listEl = h('div', { class: 'slots gl' });
    tab.items.forEach(function (it, i) {
      var e = em[it.entity_id];
      listEl.appendChild(h('div', { class: 'slot gs' + (!e && S.entities ? ' miss' : ''), 'data-idx': String(i), role: 'button', tabindex: '0',
        'aria-label': (it.name || (e && e.name) || it.entity_id) + ', inställningar',
        onclick: function () { openItem(tab, i); }, onkeydown: function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); openItem(tab, i); } } },
        h('span', { class: 'sw', 'data-c': String(i) }),
        h('span', { class: 'tx' }, h('div', { class: 'nm' }, it.name || (e && e.name) || it.entity_id),
          h('div', { class: 'st' }, S.entities ? stateText(e, it) : it.entity_id)),
        grip(tab, i)));
    });
    if (tab.items.length < lim) {
      listEl.appendChild(h('div', { class: 'slot empty', 'data-idx': String(tab.items.length),
        onclick: function () { var q = document.getElementById('q'); if (q) { q.scrollIntoView({ block: 'center' }); q.focus({ preventScroll: true }); } } },
        'Plats för ' + (lim - tab.items.length) + (tab.items.length ? ' till' : '') + ' (kryssa i nedanför)'));
    }
    bd.appendChild(listEl);
    var chartBox = h('div', { class: 'gchart' });
    bd.appendChild(chartBox);
    bd.appendChild(h('p', { class: 'hint' }, 'Förhandsvisning ur Home Assistants historik (' + HOURS_TXT[tab.hours || 24] +
      '). På panelen väljer man intervall med knappar ovanför grafen; max och min visas med tid. Tryck på ett värdekort på en värdeflik för att se samma graf för ett enskilt värde.'));
    card.appendChild(bd);
    if (!tab.items.length) {
      chartBox.appendChild(h('p', { class: 'empty-note' }, 'Inget valt än. Kryssa i upp till ' + lim + ' sensorer i listan nedanför.'));
    } else if (!S.connected) {
      chartBox.appendChild(h('p', { class: 'empty-note' }, 'Ingen kontakt med Home Assistant.'));
    } else {
      var ids = tab.items.map(function (it) { return it.entity_id; }).join(','), hours = tab.hours || 24, key = ids + '|' + hours;
      var c = histCache[key];
      if (c && c.data && Date.now() - c.at < 120000) drawChart(chartBox, tab, c.data);
      else {
        chartBox.appendChild(h('p', { class: 'empty-note' }, 'Hämtar historik …'));
        if (!c || !c.loading) {
          histCache[key] = { loading: true, at: Date.now() };
          fetch('/api/history?ids=' + encodeURIComponent(ids) + '&hours=' + hours, { cache: 'no-store' }).then(function (r) { return r.json(); })
            .then(function (res) {
              histCache[key] = { at: Date.now(), data: res.ok ? res : null, err: res.ok ? null : res.error };
              if (cfg.tabs[sel] === tab && page === 'tab') render();
            }).catch(function () { histCache[key] = { at: Date.now(), data: null, err: 'Ingen kontakt med panelen.' }; });
        }
        if (c && c.err) { chartBox.textContent = ''; chartBox.appendChild(h('p', { class: 'warn' }, c.err)); }
      }
    }
    return card;
  }
  function drawChart(box, tab, res) {
    var NS = 'http://www.w3.org/2000/svg', W = 720, H = 240, L = 44, R = 10, T = 12, B = 26;
    var em = entMap(), all = [], t0 = res.from, t1 = res.to;
    tab.items.forEach(function (it) {
      var s = res.series[it.entity_id]; if (!s) return;
      (s.band || []).forEach(function (b) { all.push(b[1], b[2]); });
      (s.points || []).forEach(function (p) { if (p[1] != null) all.push(p[1]); });
    });
    if (!all.length) {
      var nost = tab.items.some(function (it) { var s = res.series[it.entity_id]; return s && s.nostats; });
      box.appendChild(h('p', { class: 'empty-note' }, nost ? 'Home Assistant sparar ingen långtidsstatistik för det här. Välj 7 dagar eller kortare.'
                                                           : 'Ingen historik för den här perioden.'));
      return;
    }
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    if (hi - lo < 1e-9) { lo -= 0.5; hi += 0.5; }
    // jämna steg på y-axeln, som på panelen
    var raw = (hi - lo) / 4, mag = Math.pow(10, Math.floor(Math.log10(raw))), step = mag;
    [1, 2, 2.5, 5, 10].some(function (m) { step = m * mag; return step >= raw; });
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
    var ticks = Math.round((hi - lo) / step), tdec = step >= 1 ? 0 : (step >= 0.1 ? 1 : 2);
    function X(t) { return L + (t - t0) / (t1 - t0) * (W - L - R); }
    function Y(v) { return T + (hi - v) / (hi - lo) * (H - T - B); }
    function el(tag, attrs, txt) { var e = document.createElementNS(NS, tag); Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); }); if (txt != null) e.textContent = txt; return e; }
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'chart', role: 'img', 'aria-label': 'Graf' });
    for (var i = 0; i <= ticks && i <= 12; i++) {
      var v = lo + step * i, y = Y(v);
      svg.appendChild(el('line', { x1: L, x2: W - R, y1: y, y2: y, class: 'grid' }));
      svg.appendChild(el('text', { x: L - 6, y: y + 4, class: 'ax', 'text-anchor': 'end' }, num(v, tdec)));
    }
    for (var j = 0; j <= 4; j++) {
      var t = t0 + (t1 - t0) * j / 4, d = new Date(t * 1000);
      var lab = (t1 - t0) > 2 * 86400 ? d.getDate() + '/' + (d.getMonth() + 1) : ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
      svg.appendChild(el('text', { x: X(t), y: H - 6, class: 'ax', 'text-anchor': j === 0 ? 'start' : (j === 4 ? 'end' : 'middle') }, lab));
    }
    var legend = h('div', { class: 'glegend' });
    tab.items.forEach(function (it, n) {
      var s = res.series[it.entity_id], e = em[it.entity_id]; if (!s) return;
      var col = GCOL[n % 3], pts = [];
      if (s.band && tab.items.length === 1) {
        var up = s.band.map(function (b) { return X(b[0]) + ',' + Y(b[2]); }), dn = s.band.slice().reverse().map(function (b) { return X(b[0]) + ',' + Y(b[1]); });
        svg.appendChild(el('polygon', { points: up.concat(dn).join(' '), fill: col, 'fill-opacity': '0.22' }));
      }
      var segs = [[]];
      (s.points || []).forEach(function (p) { if (p[1] == null) segs.push([]); else segs[segs.length - 1].push(X(p[0]) + ',' + Y(p[1])); });
      segs.forEach(function (sg) { if (sg.length > 1) svg.appendChild(el('polyline', { points: sg.join(' '), fill: 'none', stroke: col, 'stroke-width': '2', 'stroke-linejoin': 'round' })); });
      var dec = it.decimals == null ? 1 : it.decimals, unit = e && e.unit ? ' ' + e.unit : '';
      if (tab.items.length === 1) {
        [['max', '#ef9a9a', -8], ['min', '#90caf9', 16]].forEach(function (m) {
          var x = s[m[0]]; if (!x) return;
          svg.appendChild(el('circle', { cx: X(x[1]), cy: Y(x[0]), r: 4, fill: '#1c1c1c', stroke: m[1], 'stroke-width': 2 }));
          svg.appendChild(el('text', { x: Math.min(Math.max(X(x[1]), L + 16), W - R - 16), y: Y(x[0]) + m[2], class: 'mm', fill: m[1], 'text-anchor': 'middle' }, num(x[0], dec)));
        });
      }
      legend.appendChild(h('span', { class: 'gl-item' }, h('span', { class: 'sw', 'data-c': String(n) }), it.name || (e && e.name) || it.entity_id,
        h('span', { class: 'mx' }, 'Max ' + (s.max ? num(s.max[0], dec) + unit : '–')), h('span', { class: 'mn' }, 'Min ' + (s.min ? num(s.min[0], dec) + unit : '–'))));
    });
    box.appendChild(legend);
    box.appendChild(svg);
  }

  // ---------------------------------------------------------------- lägg till: sök och grovsortera
  // Grupperna går att fälla ihop. Standard: områden och typer öppna, enheter (apparater) ihopfällda. Under sökning är allt öppet.
  function folded(key, def) { var v = prefs.fold[key]; return v === undefined ? def : v === 1; }
  function setFold(key, closed) { prefs.fold[key] = closed ? 1 : 0; savePrefs(); }
  function renderPicker(tab) {
    var card = h('section', { class: 'card', id: 'picker' });
    card.appendChild(h('div', { class: 'hd' }, h('h2', null, 'Lägg till från Home Assistant'),
      h('button', { type: 'button', class: 'iconbtn', title: 'Hämta listan igen', 'aria-label': 'Hämta listan igen', onclick: reloadEntities }, icon('Restart'))));
    var bd = h('div', { class: 'bd' });
    card.appendChild(bd);
    if (!S.entities) {
      bd.appendChild(h('p', { class: 'warn' }, S.error || 'Inga enheter att visa.'));
      bd.appendChild(h('button', { type: 'button', class: 'btn', onclick: reloadEntities }, 'Försök igen'));
      return card;
    }
    var types = TYPES[tab.type], chips = prefs.chips[tab.type] || [];
    var am = areaMap(), devs = S.devices || {};
    var base = S.entities.filter(function (e) { return typeOf(e, tab.type) && (!e.hid || prefs.hidden); });
    var counts = {};
    base.forEach(function (e) { var k = typeOf(e, tab.type); counts[k] = (counts[k] || 0) + 1; });
    var inp = h('input', { type: 'search', id: 'q', placeholder: 'Sök på namn, område, enhet eller id', value: search, 'aria-label': 'Sök',
      oninput: function () { search = this.value; clr.hidden = !search; fill(); } });
    var clr = h('button', { type: 'button', class: 'iconbtn', 'aria-label': 'Rensa sökningen', hidden: !search,
      onclick: function () { search = ''; inp.value = ''; clr.hidden = true; fill(); inp.focus(); } }, icon('Close', 's20'));
    bd.appendChild(h('div', { class: 'search' }, icon('Magnify', 's20'), inp, clr));
    var chipRow = h('div', { class: 'filters', role: 'group', 'aria-label': 'Typ' });
    types.forEach(function (t) {
      var on = chips.indexOf(t.k) >= 0;
      if (!counts[t.k] && !on) return;
      chipRow.appendChild(h('button', { type: 'button', class: 'chip' + (on ? ' on' : ''), 'aria-pressed': on ? 'true' : 'false',
        onclick: function () {
          var c = prefs.chips[tab.type] = (prefs.chips[tab.type] || []).slice(), at = c.indexOf(t.k);
          if (at >= 0) c.splice(at, 1); else c.push(t.k);
          savePrefs(); render(); } },
        on ? icon('Check') : icon(t.icon), t.label, h('span', { class: 'n' }, String(counts[t.k] || 0))));
    });
    bd.appendChild(chipRow);
    var areaOpts = [['', 'Alla områden']].concat((S.areas || []).map(function (a) { return [a.id, a.name]; }), [['-', 'Utan område']]);
    if (prefs.area && prefs.area !== '-' && !am[prefs.area]) prefs.area = '';
    var tools = h('div', { class: 'tools' },
      h('label', { class: 'field' }, h('span', null, 'Område'), select(areaOpts, prefs.area, function (v) { prefs.area = v; savePrefs(); fill(); })),
      h('label', { class: 'field' }, h('span', null, 'Gruppera efter'), select([['area', 'Område och enhet'], ['device', 'Enhet'], ['type', 'Typ'], ['none', 'Ingen gruppering']],
        prefs.group, function (v) { prefs.group = v; savePrefs(); fill(); })));
    if (S.hidden_known) {
      tools.appendChild(h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: prefs.hidden, onchange: function () {
        prefs.hidden = this.checked; savePrefs(); render(); } }), 'Visa dolda och tekniska'));
    }
    bd.appendChild(tools);
    var foldAll = h('div', { class: 'foldall' },
      h('button', { type: 'button', class: 'btn text', onclick: function () { foldEvery(true); } }, icon('UnfoldLessHorizontal', 's18'), 'Fäll ihop alla'),
      h('button', { type: 'button', class: 'btn text', onclick: function () { foldEvery(false); } }, icon('UnfoldMoreHorizontal', 's18'), 'Fäll ut alla'));
    var info = h('p', { class: 'count', 'aria-live': 'polite' }), list = h('div');
    bd.appendChild(h('div', { class: 'countrow' }, info, foldAll)); bd.appendChild(list);
    var keysShown = [];
    function foldEvery(closed) { keysShown.forEach(function (k) { prefs.fold[k] = closed ? 1 : 0; }); savePrefs(); fill(); }

    function devName(e) { return e.dev && devs[e.dev] ? devs[e.dev] : ''; }
    function areaGroup(e) {
      var key = e.area && am[e.area] ? e.area : '~';
      var a = am[key];
      var ic = a && a.icon && ICONS[pascal(a.icon.replace('mdi:', ''))] ? pascal(a.icon.replace('mdi:', '')) : 'TextureBox';
      return { key: key, name: key === '~' ? 'Utan område' : a.name, icon: ic, last: key === '~' };
    }
    function row(e, mine, full, showArea) {
      var on = !!mine[e.id], dis = !on && full;
      var cb = h('input', { type: 'checkbox', checked: on, disabled: dis, 'aria-label': e.name });
      var sub = [DOM_NAME[dom(e.id)] || dom(e.id)];
      if (showArea && e.area && am[e.area]) sub.push(am[e.area].name);
      sub.push(e.id + (e.hid ? ' (dold)' : ''));
      var r = h('label', { class: 'erow' + (lit(e) ? ' on' + (amber(e.id) ? '' : ' blue') : '') + (dis ? ' full' : ''), title: dis ? 'Fliken är full' : null },
        cb, h('span', { class: 'ic' }, icon(entIcon(e))),
        h('span', { class: 't' }, h('div', null, e.name), h('div', { class: 'id' }, sub.join(' · '))),
        h('span', { class: 's' }, stateText(e)));
      cb.addEventListener('change', function () { toggle(tab, e, cb); });
      return r;
    }
    // en hopfällbar grupp: rubrik (ikon, namn, antal, valda, "Lägg till alla") och innehåll
    function groupBox(level, key, name, ic, rows, defClosed, q, mine, full, body) {
      var gkey = tab.type + ':' + prefs.group + ':' + key;
      keysShown.push(gkey);
      var closed = !q && folded(gkey, defClosed);
      var box = h('div', { class: 'group lv' + level + (closed ? ' closed' : '') });
      var chosen = rows.filter(function (e) { return mine[e.id]; }).length;
      var addable = rows.filter(function (e) { return !mine[e.id]; });
      box.appendChild(h('div', { class: 'ghd' },
        h('button', { type: 'button', class: 'tog', 'aria-expanded': closed ? 'false' : 'true', onclick: function () {
          var c = !box.classList.contains('closed'); setFold(gkey, c); box.classList.toggle('closed', c); this.setAttribute('aria-expanded', c ? 'false' : 'true'); } },
          icon('ChevronDown', 'chev s20'), ic ? icon(ic, 's20') : null, h('span', { class: 'gn' }, name), h('span', { class: 'gc' }, String(rows.length)),
          chosen ? h('span', { class: 'gsel' }, chosen + ' på fliken') : null),
        addable.length > 1 || (addable.length === 1 && level === 0) ? h('button', { type: 'button', class: 'btn', disabled: full, title: 'Lägger till så många som får plats',
          onclick: function () { addMany(tab, addable); } }, icon('Plus', 's18'), 'Lägg till alla') : null));
      box.appendChild(body);
      return box;
    }

    function fill() {
      list.textContent = ''; keysShown = [];
      var q = search.trim().toLowerCase(), mine = inTab(tab), full = tab.items.length >= limit(tab);
      var rows = base.filter(function (e) {
        if (chips.length && chips.indexOf(typeOf(e, tab.type)) < 0 && !mine[e.id]) return false;
        if (prefs.area === '-' ? !!e.area : (prefs.area && e.area !== prefs.area)) return false;
        if (q) {
          var hay = (e.name + ' ' + e.id + ' ' + (e.area && am[e.area] ? am[e.area].name : '') + ' ' + devName(e)).toLowerCase();
          if (hay.indexOf(q) < 0) return false;
        }
        return true;
      });
      var shown = 0, CAP = 500;
      function rowsBox(rs, showArea) {
        var b = h('div', { class: 'rows' });
        rs.forEach(function (e) { if (shown < CAP) { shown++; b.appendChild(row(e, mine, full, showArea)); } });
        return b;
      }
      function bucket(rs, keyFn) {
        var out = [], m = {};
        rs.forEach(function (e) { var g = keyFn(e); if (!m[g.key]) { m[g.key] = g; g.rows = []; out.push(g); } m[g.key].rows.push(e); });
        out.sort(function (a, b) { return (a.last ? 1 : 0) - (b.last ? 1 : 0) || a.name.localeCompare(b.name, 'sv'); });
        return out;
      }
      if (prefs.group === 'none') {
        list.appendChild(rowsBox(rows, true));
      } else if (prefs.group === 'type') {
        var order = types.map(function (t) { return t.k; });
        var tg = bucket(rows, function (e) { var t = types[order.indexOf(typeOf(e, tab.type))]; return { key: t.k, name: t.label, icon: t.icon }; });
        tg.sort(function (a, b) { return order.indexOf(a.key) - order.indexOf(b.key); });
        tg.forEach(function (g) { list.appendChild(groupBox(0, g.key, g.name, g.icon, g.rows, false, q, mine, full, rowsBox(g.rows, true))); });
      } else if (prefs.group === 'device') {
        bucket(rows, function (e) { var n = devName(e); return n ? { key: e.dev, name: n, icon: 'Devices' } : { key: '~', name: 'Utan enhet', icon: 'Shape', last: true }; })
          .forEach(function (g) { list.appendChild(groupBox(0, 'd:' + g.key, g.name, g.icon, g.rows, true, q, mine, full, rowsBox(g.rows, true))); });
      } else {
        // område, och inom området en hopfällbar grupp per enhet som har flera saker
        bucket(rows, areaGroup).forEach(function (g) {
          var body = h('div', { class: 'rows' });
          var sub = bucket(g.rows, function (e) { var n = devName(e); return n ? { key: e.dev, name: n } : { key: '~', name: '', last: true }; });
          var singles = [];
          sub.forEach(function (d) {
            if (d.key === '~' || d.rows.length < 2) { singles = singles.concat(d.rows); return; }
            body.appendChild(groupBox(1, g.key + '/' + d.key, d.name, 'Devices', d.rows, true, q, mine, full, rowsBox(d.rows, false)));
          });
          singles.sort(function (a, b) { return a.name.localeCompare(b.name, 'sv'); });
          if (singles.length) body.appendChild(rowsBox(singles, false));
          list.appendChild(groupBox(0, 'a:' + g.key, g.name, g.icon, g.rows, false, q, mine, full, body));
        });
      }
      if (!rows.length) {
        list.appendChild(h('p', { class: 'empty-note' }, q ? 'Inget matchar ”' + search.trim() + '”. Pröva ett annat ord eller ta bort filtren.'
                                                         : 'Inget att visa med de här filtren.'));
      }
      info.textContent = rows.length + (rows.length === 1 ? ' träff' : ' träffar') + (rows.length > shown ? ' (visar ' + shown + ', sök för att begränsa)' : '')
        + (full ? '. Fliken är full: ta bort något först.' : '');
      foldAll.hidden = prefs.group === 'none' || !rows.length;
    }
    fill();
    return card;
  }
  function toggle(tab, e, cb) {
    var idx = -1;
    tab.items.forEach(function (it, i) { if (it.entity_id === e.id) idx = i; });
    if (cb.checked && idx < 0) {
      if (!addEntity(tab, e)) { cb.checked = false; toast('Fliken är full (' + limit(tab) + ' platser).', true); return; }
      if (tab.type === 'graph') unitWarn(tab);
    } else if (!cb.checked && idx >= 0) {
      tab.items.splice(idx, 1);
    }
    setDirty(true); render();
  }
  function addMany(tab, ents) {
    var n = 0;
    for (var i = 0; i < ents.length; i++) { if (!addEntity(tab, ents[i])) break; n++; }
    setDirty(true); render();
    if (tab.type === 'graph') unitWarn(tab);
    else toast(n === ents.length ? 'La till ' + n + '.' : 'La till ' + n + ' av ' + ents.length + ': fliken är full.', n < ents.length);
  }
  function unitWarn(tab) {
    var em = entMap(), units = {};
    tab.items.forEach(function (it) { var e = em[it.entity_id]; units[(e && e.unit) || ''] = 1; });
    if (Object.keys(units).length > 1) toast('Kurvorna har olika enheter (' + Object.keys(units).filter(Boolean).join(', ') + ') men delar samma skala.', true);
  }

  // ---------------------------------------------------------------- dialoger
  function closeDlg() { $dlg.hidden = true; $dlg.textContent = ''; document.removeEventListener('keydown', dlgKey); }
  function dlgKey(ev) { if (ev.key === 'Escape') { closeDlg(); render(); } }
  function openDlg(title, ic, body, foot) {
    $dlg.textContent = '';
    var box = h('div', { class: 'dbox', role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
      h('div', { class: 'dh' }, ic ? icon(ic) : null, h('h3', null, title),
        h('button', { type: 'button', class: 'iconbtn', 'aria-label': 'Stäng', onclick: function () { closeDlg(); render(); } }, icon('Close'))),
      h('div', { class: 'db' }, body), h('div', { class: 'df' }, foot));
    $dlg.appendChild(box);
    $dlg.hidden = false;
    $dlg.onclick = function (ev) { if (ev.target === $dlg) { closeDlg(); render(); } };
    document.addEventListener('keydown', dlgKey);
    var coarse = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
    var f = coarse ? box.querySelector('.dh .iconbtn') : box.querySelector('.db input, .db select, .db button, .df .fill');
    if (f) setTimeout(function () { f.focus(); }, 0);
  }
  function seg(options, value, onchange) {
    var box = h('div', { class: 'seg', role: 'group' });
    options.forEach(function (o) {
      box.appendChild(h('button', { type: 'button', class: String(o[0]) === String(value) ? 'on' : '', 'aria-pressed': String(o[0]) === String(value) ? 'true' : 'false',
        onclick: function () { onchange(o[0]); Array.prototype.forEach.call(box.children, function (b) { b.className = ''; b.setAttribute('aria-pressed', 'false'); });
          this.className = 'on'; this.setAttribute('aria-pressed', 'true'); } }, o[1]));
    });
    return box;
  }
  function openItem(tab, i) {
    var it = tab.items[i], em = entMap(), am = areaMap();
    var close = function () { closeDlg(); render(); };
    var body = [], title;
    if (it.placeholder) {
      title = 'Tom ruta';
      body.push(h('p', { class: 'muted' }, 'En grå ruta som håller platsen, så att resten hamnar där du vill.'));
    } else {
      var e = em[it.entity_id], d = dom(it.entity_id);
      title = it.name || (e && e.name) || it.entity_id;
      body.push(h('label', { class: 'field' }, h('span', null, 'Namn på panelen'),
        h('input', { type: 'text', value: it.name || '', maxlength: '40', placeholder: e ? e.name : it.entity_id,
          oninput: function () { it.name = this.value; setDirty(true); } })));
      body.push(h('dl', { class: 'kv' },
        h('dt', null, 'Typ'), h('dd', null, DOM_NAME[d] || d),
        h('dt', null, 'Område'), h('dd', null, e && e.area && am[e.area] ? am[e.area].name : '–'),
        h('dt', null, 'Läge nu'), h('dd', { class: e ? '' : 'warn' }, S.entities ? stateText(e, it) : 'okänt (ingen kontakt)'),
        h('dt', null, 'Id'), h('dd', null, it.entity_id)));
      if (d === 'light' && e) {
        var can = [];
        if (e.dim) can.push('dimra');
        if (e.ct) can.push('vitt ' + e.ct[0] + '–' + e.ct[1] + ' K');
        if (e.rgb) can.push('färg');
        if (can.length) body.push(h('p', { class: 'hint' }, 'Lampan kan: ' + can.join(', ') + '. Tryck på namnet på panelen för dimvyn'
          + (e.ct || e.rgb ? ', där väljer du Ljusstyrka, Vitt eller Färg.' : '.')));
      }
      if (d === 'light') {
        var cur = typeof it.dimmable === 'boolean' ? (it.dimmable ? 'yes' : 'no') : 'auto';
        body.push(h('div', { class: 'field' }, h('span', null, 'Dimbar (trycka på namnet öppnar dimvyn)'),
          seg([['auto', 'Automatiskt'], ['yes', 'Ja'], ['no', 'Nej']], cur, function (v) {
            if (v === 'auto') delete it.dimmable; else it.dimmable = (v === 'yes'); setDirty(true); })));
      }
      if (tab.type !== 'lights' && ['sensor', 'input_number', 'counter', 'number'].indexOf(d) >= 0) {
        body.push(h('div', { class: 'field' }, h('span', null, 'Decimaler'),
          seg([[0, '0'], [1, '1'], [2, '2'], [3, '3']], it.decimals == null ? 1 : it.decimals, function (v) { it.decimals = v; setDirty(true); })));
      }
      if (ACTIONS.indexOf(d) >= 0) body.push(h('p', { class: 'hint' }, d === 'scene' ? 'Ett tryck på panelen aktiverar scenen.' :
        (d === 'script' ? 'Ett tryck på panelen startar skriptet.' : 'Ett tryck på panelen trycker på knappen.')));
      if (d === 'automation') body.push(h('p', { class: 'hint' }, 'Växeln på panelen slår på och av automationen (den körs inte direkt).'));
    }
    var n = tab.items.length;
    openDlg(title, it.placeholder ? 'Shape' : entIcon(em[it.entity_id], it.entity_id), body, [
      h('button', { type: 'button', class: 'btn danger', onclick: function () { tab.items.splice(i, 1); setDirty(true); close(); } }, icon('Delete', 's18'), 'Ta bort från fliken'),
      h('span', { class: 'spacer' }),
      h('button', { type: 'button', class: 'iconbtn', 'aria-label': 'Flytta en plats bakåt', title: 'Flytta en plats bakåt', disabled: i === 0,
        onclick: function () { moveItem(tab, i, i - 1); closeDlg(); render(); openItem(tab, i - 1); } }, icon('ArrowLeft')),
      h('button', { type: 'button', class: 'iconbtn', 'aria-label': 'Flytta en plats framåt', title: 'Flytta en plats framåt', disabled: i === n - 1,
        onclick: function () { moveItem(tab, i, i + 1); closeDlg(); render(); openItem(tab, i + 1); } }, icon('ArrowRight')),
      h('button', { type: 'button', class: 'btn fill', onclick: close }, 'Klar')]);
  }
  function openDeleteTab() {
    var tab = cfg.tabs[sel];
    openDlg('Ta bort fliken ”' + (tab.title || '(namnlös)') + '”?', 'Delete',
      [h('p', { class: 'muted' }, 'Fliken och det som ligger på den försvinner från panelen när du sparar. Inget ändras i Home Assistant.'
        + (cfg.tabs.length === 1 ? ' Utan flikar visar panelen en välkomstskärm med adressen hit.' : ''))],
      [h('button', { type: 'button', class: 'btn text', onclick: function () { closeDlg(); } }, 'Avbryt'),
       h('button', { type: 'button', class: 'btn danger', onclick: function () {
         cfg.tabs.splice(sel, 1); sel = Math.max(0, sel - 1); setDirty(true); closeDlg(); render(); } }, 'Ta bort fliken')]);
  }
  var KIND_ORDER = { lights: ['light', 'switch', 'input_boolean', 'fan', 'scene', 'script', 'automation', 'input_button', 'button'],
                     sensors: ['sensor', 'binary_sensor', 'input_number', 'counter', 'input_select', 'input_datetime', 'input_text'],
                     graph: ['sensor', 'input_number', 'counter', 'number'] };
  var CAT_ORDER = ['temp', 'humidity', 'energy', 'other', 'battery'];
  function openNewTab() {
    var st = { type: 'lights', title: '', area: '', touched: false };
    var nameIn = h('input', { type: 'text', maxlength: '24', placeholder: 'Till exempel Vardagsrum', oninput: function () { st.title = this.value; st.touched = !!this.value; } });
    var areaHint = h('p', { class: 'hint' });
    function areaCount(aid) {
      return (S.entities || []).filter(function (e) { return e.area === aid && !e.hid && typeOf(e, st.type); }).length;
    }
    var areaSel = h('select');
    function fillAreas() {
      areaSel.textContent = '';
      areaSel.appendChild(h('option', { value: '' }, 'Nej, börja med en tom flik'));
      (S.areas || []).forEach(function (a) { var n = areaCount(a.id); areaSel.appendChild(h('option', { value: a.id, disabled: !n }, a.name + ' (' + n + ')')); });
      areaSel.value = st.area && areaCount(st.area) ? st.area : '';
      st.area = areaSel.value;
      areaHint.textContent = S.entities ? (S.areas && S.areas.length ? 'Fliken fylls med det som finns i området, så mycket som får plats. Du kan ändra efteråt.'
        : 'Home Assistant har inga områden (eller så får panelen inte läsa dem).') : 'Ingen kontakt med Home Assistant: områdena går inte att läsa just nu.';
    }
    areaSel.addEventListener('change', function () {
      st.area = this.value;
      var a = areaMap()[st.area];
      if (a && !st.touched) { nameIn.value = a.name.slice(0, 24); st.title = nameIn.value; }
    });
    var kinds = h('div', { class: 'kindpick', role: 'group', 'aria-label': 'Sort' });
    function kindBtn(type, ic, k, d) {
      return h('button', { type: 'button', class: st.type === type ? 'on' : '', 'aria-pressed': st.type === type ? 'true' : 'false', onclick: function () {
        st.type = type; Array.prototype.forEach.call(kinds.children, function (b) { b.className = ''; b.setAttribute('aria-pressed', 'false'); });
        this.className = 'on'; this.setAttribute('aria-pressed', 'true'); fillAreas(); } },
        h('span', { class: 'k' }, icon(ic, 's20'), k), h('span', { class: 'd' }, d));
    }
    kinds.appendChild(kindBtn('lights', 'Lightbulb', 'Knappar', 'Lampor, strömbrytare, scener, automationer, skript, hjälpare. Upp till 8.'));
    kinds.appendChild(kindBtn('sensors', 'Thermometer', 'Värden', 'Temperaturer, luftfuktighet och andra sensorer, väder, hjälpare. Upp till 11.'));
    kinds.appendChild(kindBtn('graph', 'ChartLine', 'Graf', 'Hur värden ändrats över tid, med max och min. Upp till 3 kurvor.'));
    fillAreas();
    openDlg('Ny flik', 'Plus', [
      h('label', { class: 'field' }, h('span', null, 'Namn'), nameIn),
      h('div', { class: 'field' }, h('span', null, 'Vad ska fliken visa?'), kinds),
      h('label', { class: 'field' }, h('span', null, 'Fyll fliken från ett område?'), areaSel), areaHint], [
      h('button', { type: 'button', class: 'btn text', onclick: function () { closeDlg(); } }, 'Avbryt'),
      h('button', { type: 'button', class: 'btn fill', onclick: function () { createTab(st); } }, 'Skapa fliken')]);
  }
  function createTab(st) {
    var a = areaMap()[st.area];
    var title = (st.title || '').trim() || (a ? a.name : { lights: 'Lampor', sensors: 'Temperaturer', graph: 'Graf' }[st.type]);
    var aicon = a && a.icon ? pascal(a.icon.replace('mdi:', '')) : '';
    var t = { id: 'flik' + Date.now().toString(36), title: title.slice(0, 24), type: st.type,
              icon: st.type === 'graph' ? 'ChartLine' : (S.config.icons.indexOf(aicon) >= 0 ? aicon :
                    (st.type === 'lights' ? (a ? 'Sofa' : 'Lightbulb') : 'Thermometer')), items: [] };
    if (st.type === 'lights') { t.all_label = 'Alla lampor'; t.show_all = true; }
    if (st.type === 'graph') t.hours = 24;
    if (a) {
      var order = KIND_ORDER[st.type];
      var ents = (S.entities || []).filter(function (e) { return e.area === a.id && !e.hid && typeOf(e, st.type); });
      ents.sort(function (x, y) {
        var dx = order.indexOf(dom(x.id)), dy = order.indexOf(dom(y.id));
        if (dx !== dy) return dx - dy;
        if (st.type !== 'lights' && dom(x.id) === 'sensor' && dom(y.id) === 'sensor') {
          var cx = CAT_ORDER.indexOf(sensorCat(x)), cy = CAT_ORDER.indexOf(sensorCat(y));
          if (cx !== cy) return cx - cy;
        }
        return x.name.localeCompare(y.name, 'sv');
      });
      ents.forEach(function (e) { addEntity(t, e); });
    }
    cfg.tabs.push(t); sel = cfg.tabs.length - 1; page = 'tab'; setDirty(true); closeDlg(); render(); window.scrollTo(0, 0);
    if (a) toast('Fliken fick ' + t.items.length + ' saker från ' + a.name + '. Spara när du är nöjd.');
  }

  // ---------------------------------------------------------------- allmänt
  function renderGeneral() {
    var card = h('section', { class: 'card' }, h('div', { class: 'hd' }, h('h2', null, 'Allmänt')));
    card.appendChild(h('div', { class: 'bd' }, h('div', { class: 'grid2' },
      h('label', { class: 'field' }, h('span', null, 'Decimaltecken'), select([[',', 'Komma (21,5)'], ['.', 'Punkt (21.5)']], cfg.locale.decimal_separator,
        function (v) { cfg.locale.decimal_separator = v; setDirty(true); })),
      h('label', { class: 'field' }, h('span', null, 'Steg för plus och minus i dimvyn'), select([['5', '5 %'], ['10', '10 %'], ['20', '20 %'], ['25', '25 %']], cfg.ui.dim_step,
        function (v) { cfg.ui.dim_step = parseInt(v, 10); setDirty(true); })),
      h('label', { class: 'field' }, h('span', null, 'Dimvyn stängs efter'), select([['30', '30 sekunder'], ['60', '1 minut'], ['90', '90 sekunder'], ['180', '3 minuter'], ['0', 'Aldrig']],
        cfg.ui.dim_timeout, function (v) { cfg.ui.dim_timeout = parseInt(v, 10); setDirty(true); }))),
      h('p', { class: 'hint' }, 'Skärmens ljusstyrka och hur snart den släcks ställer du in på panelen själv (kugghjulet).')));
    return [card, renderBackup()];
  }

  // ---------------------------------------------------------------- säkerhetskopia: hela konfigurationen som fil
  function renderBackup() {
    var file = h('input', { type: 'file', accept: '.json,application/json', class: 'filein', id: 'restore-file', onchange: function () {
      var f = this.files && this.files[0]; this.value = '';
      if (!f) return;
      if (f.size > 256 * 1024) { toast('Filen är för stor för att vara en konfiguration.', true); return; }
      var rd = new FileReader();
      rd.onload = function () { previewRestore(String(rd.result || ''), f.name); };
      rd.onerror = function () { toast('Kunde inte läsa filen.', true); };
      rd.readAsText(f);
    } });
    return h('section', { class: 'card' }, h('div', { class: 'hd' }, h('h2', null, 'Säkerhetskopia')),
      h('div', { class: 'bd' },
        h('p', { class: 'muted small' }, 'Spara hela konfigurationen (flikar, vad som ligger på dem, namn och inställningarna här) som en fil. '
          + 'Läs in filen på en annan platta för att få samma panel där. Home Assistants adress och token följer inte med; de hör till varje platta.'),
        h('div', { class: 'btns' },
          h('a', { class: 'btn', href: '/api/export', download: '' }, icon('Download', 's18'), 'Ladda ned konfigurationen'),
          h('label', { class: 'btn', for: 'restore-file' }, icon('Upload', 's18'), 'Läs in från fil …'), file),
        dirty ? h('p', { class: 'hint warn' }, 'Filen innehåller det som är sparat. Spara först om du vill få med dina senaste ändringar.') : null));
  }
  function previewRestore(text, fname) {
    var doc;
    try { doc = JSON.parse(text); } catch (e) { toast('Filen är inte en konfiguration (ogiltig JSON).', true); return; }
    if (!doc || typeof doc !== 'object' || !Array.isArray(doc.tabs)) { toast('Filen saknar flikar och ser inte ut att vara en konfiguration härifrån.', true); return; }
    var em = entMap(), n = 0, missing = [];
    doc.tabs.forEach(function (t) { (t.items || []).forEach(function (it) { if (it && it.entity_id) { n++; if (S.entities && !em[it.entity_id]) missing.push(it.entity_id); } }); });
    var body = [
      h('p', null, fname + (doc.exported ? ', sparad ' + String(doc.exported).slice(0, 16).replace('T', ' ') : '') + (doc.version ? ' (version ' + doc.version + ')' : '') + '.'),
      h('dl', { class: 'kv' }, h('dt', null, 'Flikar'), h('dd', null, doc.tabs.length ? doc.tabs.map(function (t) { return (t.title || '(namnlös)') + ' (' + ((t.items || []).length) + ')'; }).join(', ') : 'inga'),
        h('dt', null, 'Saker'), h('dd', null, String(n)))];
    if (missing.length) {
      body.push(h('p', { class: 'warn small' }, missing.length + ' av dem finns inte i den här Home Assistant och visas som saknade: '
        + missing.slice(0, 6).join(', ') + (missing.length > 6 ? ' …' : '')));
    }
    body.push(h('p', { class: 'hint' }, 'Det som visas nu ersätts. Inget sparas förrän du trycker Spara, så du kan ångra.'));
    openDlg('Läs in konfigurationen?', 'Upload', body, [
      h('button', { type: 'button', class: 'btn text', onclick: function () { closeDlg(); } }, 'Avbryt'),
      h('button', { type: 'button', class: 'btn fill', onclick: function () {
        cfg.tabs = doc.tabs.slice(0, S.config.limits.tabs);
        if (doc.locale && (doc.locale.decimal_separator === ',' || doc.locale.decimal_separator === '.')) cfg.locale.decimal_separator = doc.locale.decimal_separator;
        if (doc.ui) ['dim_step', 'dim_timeout'].forEach(function (k) { if (typeof doc.ui[k] === 'number') cfg.ui[k] = doc.ui[k]; });
        sel = 0; page = 'tab'; setDirty(true); closeDlg(); render(); window.scrollTo(0, 0);
        toast('Inläst. Tryck Spara för att använda den på panelen.');
      } }, 'Ersätt')]);
  }

  // ---------------------------------------------------------------- inga flikar
  function renderNoTabs() {
    return h('section', { class: 'card welcome' }, h('div', { class: 'bd' },
      h('h2', null, 'Inga flikar än'),
      h('p', null, 'Panelen visar och styr ditt Home Assistant: lampor, scener, automationer och hjälpare som knappar, temperaturer och andra värden, '
        + 'och grafer över hur de ändrats. Utan flikar visar den en välkomstskärm med adressen hit.'),
      h('p', { class: 'muted' }, 'Skapa en flik och välj vad som ska ligga på den. En flik kan fyllas direkt från ett område i Home Assistant. '
        + 'Har du en sparad konfiguration från en annan platta läser du in den under Allmänt.'),
      h('div', { class: 'btns' },
        h('button', { type: 'button', class: 'btn fill', onclick: openNewTab }, icon('Plus', 's18'), 'Skapa första fliken'),
        h('button', { type: 'button', class: 'btn', onclick: function () { page = 'general'; render(); } }, icon('Upload', 's18'), 'Läs in en sparad konfiguration'))));
  }

  // ---------------------------------------------------------------- allt
  function render() {
    var y = window.scrollY;
    $conn.className = 'conn ' + (S.connected ? 'ok' : 'bad');
    $conn.title = S.connected ? 'Ansluten till Home Assistant' : 'Ingen kontakt med Home Assistant';
    renderNav();
    $app.textContent = '';
    $topact.textContent = '';
    if (page === 'general') {
      $title.textContent = 'Allmänt';
      add($app, renderGeneral());
    } else if (!cfg.tabs.length) {
      $title.textContent = 'Panelinställningar';
      $app.appendChild(renderNoTabs());
    } else {
      var tab = cfg.tabs[sel];
      $title.textContent = tab.title || '(namnlös)';
      if (!S.connected) $app.appendChild(h('p', { class: 'warn' }, 'Ingen kontakt med Home Assistant. Du kan ordna och döpa om, men inte se läget eller lägga till nytt.'));
      $app.appendChild(renderTabCard(tab));
      $app.appendChild(tab.type === 'graph' ? renderGraphPreview(tab) : renderPreview(tab));
      $app.appendChild(renderPicker(tab));
    }
    window.scrollTo(0, y);
    if (focusGrip != null) { var g = $app.querySelector('[data-grip="' + focusGrip + '"]'); if (g) g.focus(); focusGrip = null; }
  }

  load();
})();
'''
