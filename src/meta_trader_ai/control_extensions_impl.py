from __future__ import annotations


_PROFESSIONAL_STYLE = r'''
/* MetaTrader AI professional control-center skin */
:root{
  --pro-bg:#070b12;
  --pro-surface:rgba(16,24,38,.86);
  --pro-surface-2:rgba(11,18,29,.92);
  --pro-border:rgba(148,163,184,.16);
  --pro-border-strong:rgba(96,165,250,.28);
  --pro-text:#eef4fb;
  --pro-muted:#91a0b5;
  --pro-green:#4ade80;
  --pro-amber:#fbbf24;
  --pro-red:#fb7185;
  --pro-shadow:0 18px 55px rgba(0,0,0,.28);
}
html{scroll-behavior:smooth}
body{
  min-height:100vh;padding:0!important;color:var(--pro-text)!important;
  background:
    radial-gradient(circle at 12% -5%,rgba(34,211,238,.12),transparent 30%),
    radial-gradient(circle at 88% 5%,rgba(96,165,250,.13),transparent 28%),
    linear-gradient(180deg,var(--pro-bg) 0%,#090e17 45%,#070a10 100%)!important;
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;
}
body::before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;
  background-image:linear-gradient(rgba(148,163,184,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(148,163,184,.025) 1px,transparent 1px);
  background-size:42px 42px;
}
.wrap{max-width:1360px!important;margin:0 auto!important;padding:28px 28px 72px!important}
.control-hero{
  position:relative;overflow:hidden;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:26px;align-items:center;
  padding:26px 28px;margin:0 0 16px;border:1px solid var(--pro-border-strong);border-radius:22px;
  background:linear-gradient(135deg,rgba(18,29,46,.96),rgba(10,17,28,.94));box-shadow:var(--pro-shadow);
}
.control-hero::after{
  content:"";position:absolute;width:320px;height:320px;border-radius:50%;right:-120px;top:-200px;
  background:rgba(34,211,238,.09);pointer-events:none
}
.hero-eyebrow{
  display:flex;align-items:center;gap:9px;margin-bottom:7px;color:#7dd3fc;
  font-size:12px;font-weight:800;letter-spacing:.15em;text-transform:uppercase
}
.hero-eyebrow::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--pro-green);box-shadow:0 0 16px rgba(74,222,128,.7)}
.control-hero h1{font-size:clamp(26px,3vw,39px)!important;line-height:1.12;margin:0!important;letter-spacing:-.035em;color:#f8fbff}
.control-hero p{max-width:760px;margin:10px 0 0!important;color:var(--pro-muted)!important;font-size:14px;line-height:1.75}
.hero-side{display:flex;flex-direction:column;align-items:flex-end;gap:12px;position:relative;z-index:1}
.hero-badges{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.hero-badge{
  display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border-radius:999px;border:1px solid var(--pro-border);
  background:rgba(2,6,12,.4);color:#cbd5e1;font-size:11px;font-weight:750;letter-spacing:.035em
}
.hero-badge.live{color:#86efac;border-color:rgba(74,222,128,.25);background:rgba(22,101,52,.12)}
.hero-link{
  display:inline-flex!important;align-items:center;justify-content:center;gap:8px;padding:10px 14px!important;border-radius:11px!important;
  border:1px solid rgba(96,165,250,.28)!important;background:rgba(37,99,235,.12)!important;color:#bfdbfe!important;
  font-weight:750;text-decoration:none!important
}
.command-nav{
  position:sticky;top:10px;z-index:80;display:flex;gap:7px;overflow-x:auto;padding:8px;margin:0 0 18px;
  border:1px solid var(--pro-border);border-radius:14px;background:rgba(7,11,18,.82);backdrop-filter:blur(16px);
  box-shadow:0 10px 35px rgba(0,0,0,.2);scrollbar-width:none
}
.command-nav::-webkit-scrollbar{display:none}
.command-nav a{
  flex:0 0 auto;padding:8px 11px;border-radius:9px;color:#94a3b8;text-decoration:none;font-size:12px;font-weight:700;
  border:1px solid transparent;transition:.18s ease
}
.command-nav a:hover,.command-nav a.active{color:#e0f2fe;background:rgba(56,189,248,.1);border-color:rgba(56,189,248,.2)}
.card{
  position:relative;overflow:visible;background:linear-gradient(180deg,var(--pro-surface),var(--pro-surface-2))!important;
  border:1px solid var(--pro-border)!important;border-radius:20px!important;padding:22px!important;margin:14px 0!important;
  box-shadow:0 14px 42px rgba(0,0,0,.18)!important;
}
.card::before{
  content:"";position:absolute;left:0;top:20px;bottom:20px;width:2px;border-radius:2px;
  background:linear-gradient(180deg,rgba(96,165,250,.55),rgba(34,211,238,.05))
}
.card h2{margin:0 0 18px!important;font-size:18px!important;letter-spacing:-.015em;color:#f3f7fb}
.card-kicker{display:block;margin:0 0 5px;color:#64748b;font-size:10px;font-weight:850;letter-spacing:.13em;text-transform:uppercase}
.card[data-accent="green"]::before{background:linear-gradient(180deg,rgba(74,222,128,.7),rgba(74,222,128,.05))}
.card[data-accent="amber"]::before{background:linear-gradient(180deg,rgba(251,191,36,.7),rgba(251,191,36,.05))}
.card[data-accent="purple"]::before{background:linear-gradient(180deg,rgba(167,139,250,.7),rgba(167,139,250,.05))}
.card[data-accent="red"]::before{background:linear-gradient(180deg,rgba(251,113,133,.7),rgba(251,113,133,.05))}
.row{
  grid-template-columns:minmax(190px,260px) minmax(180px,1fr) 88px!important;gap:16px!important;
  min-height:46px;padding:8px 0;margin:0!important;border-bottom:1px solid rgba(148,163,184,.07)
}
.row:last-of-type{border-bottom:0}.row>label{color:#dbe4ef;font-size:13px;font-weight:650;line-height:1.5}
input[type="range"]{width:100%;accent-color:#38bdf8}
input[type="number"],input[type="date"],.field input{
  min-height:40px;background:#090f19!important;color:#edf5ff!important;border:1px solid rgba(148,163,184,.18)!important;
  border-radius:10px!important;padding:9px 10px!important;outline:none;transition:.18s ease
}
input[type="number"]:focus,input[type="date"]:focus,.field input:focus{border-color:rgba(96,165,250,.65)!important;box-shadow:0 0 0 3px rgba(59,130,246,.11)}
input[type="checkbox"]{accent-color:#22c55e;cursor:pointer}
.fields{gap:12px!important}
.field{padding:13px;border:1px solid rgba(148,163,184,.1);border-radius:13px;background:rgba(2,6,12,.22)}
.field label{color:#8fa1b6!important;font-weight:650}
.actions{gap:9px!important}
.primary-actions{
  position:sticky;bottom:14px;z-index:70;padding:12px!important;margin:16px 0!important;
  border:1px solid rgba(96,165,250,.2);border-radius:15px;background:rgba(7,11,18,.91);
  backdrop-filter:blur(18px);box-shadow:0 14px 40px rgba(0,0,0,.38)
}
button,.linkbtn,.nav a{min-height:40px;border-radius:10px!important;transition:transform .16s ease,border-color .16s ease,filter .16s ease,background .16s ease}
button:hover:not(:disabled),.linkbtn:hover,.nav a:hover{transform:translateY(-1px);filter:brightness(1.08)}
button:focus-visible,.linkbtn:focus-visible,.command-nav a:focus-visible,input:focus-visible{outline:2px solid #60a5fa!important;outline-offset:2px}
button{background:#2563eb!important;border:1px solid rgba(147,197,253,.16)!important;box-shadow:none!important}
button.recommended{background:#0f766e!important;border-color:rgba(52,211,153,.22)!important}
button.research{background:#a16207!important;border-color:rgba(251,191,36,.25)!important}
button.regime{background:#6d28d9!important;border-color:rgba(196,181,253,.22)!important}
button.ninja{background:linear-gradient(180deg,#c81e45,#9f1239)!important;border-color:rgba(251,113,133,.45)!important;color:#fff1f2!important}
button.pdfmode{background:#0f766e!important;border-color:rgba(45,212,191,.28)!important}
button.pdfmode.on{background:#15803d!important;border-color:rgba(134,239,172,.32)!important}
button:disabled{opacity:.42!important;cursor:not-allowed!important;transform:none!important}
#status,#recommendStatus,#compareMsg,#btMsg{display:inline-flex;align-items:center;min-height:32px;padding:4px 8px;border-radius:8px;font-size:12px;font-weight:700}
.muted{color:var(--pro-muted)!important}.ok{color:var(--pro-green)!important}.bad{color:var(--pro-red)!important}.warn{color:var(--pro-amber)!important}
code{color:#93c5fd!important;background:rgba(59,130,246,.08);border:1px solid rgba(96,165,250,.1);border-radius:5px;padding:1px 5px}
.statusbox{background:rgba(2,6,12,.38)!important;border:1px solid rgba(148,163,184,.13)!important;border-radius:13px!important;padding:14px 15px!important;line-height:1.7!important}
.metrics{grid-template-columns:repeat(5,minmax(130px,1fr))!important;gap:10px!important}
.metric{min-height:90px;background:rgba(2,6,12,.38)!important;border:1px solid rgba(148,163,184,.12)!important;border-radius:14px!important;padding:13px!important}
.metric b{font-size:22px!important;color:#f8fbff;font-variant-numeric:tabular-nums}.metric small{color:#718096}
.tablewrap{border:1px solid rgba(148,163,184,.12);border-radius:14px;overflow:auto!important;background:rgba(2,6,12,.24)}
table{margin:0!important}
th{position:sticky;top:0;z-index:2;background:#0d1521;color:#8fa1b6!important;font-size:11px!important;text-transform:uppercase;letter-spacing:.05em}
th,td{padding:11px!important;border-bottom:1px solid rgba(148,163,184,.08)!important}
tbody tr:hover{background:rgba(96,165,250,.035)}
.pill{background:rgba(15,23,42,.5);border-color:rgba(148,163,184,.15)!important}
.ninja-note{
  display:flex;gap:10px;align-items:flex-start;margin:-4px 0 14px;padding:11px 13px;border:1px solid rgba(251,113,133,.2);
  border-radius:12px;background:rgba(159,18,57,.08);color:#fecdd3;font-size:12px;line-height:1.65
}
.ninja-note b{white-space:nowrap;color:#fda4af}
.tip:hover::after,.tip:focus::after,.tip:hover::before,.tip:focus::before{content:none!important;display:none!important}
.tipbox{
  display:none;position:absolute;left:50%;bottom:calc(100% + 10px);transform:translateX(-50%);width:360px;
  max-width:min(380px,calc(100vw - 32px));padding:11px 13px;border:1px solid #475569;border-radius:10px;
  background:#020617;color:#f8fafc;font-size:13px;font-weight:500;line-height:1.9;direction:rtl;unicode-bidi:isolate;
  text-align:right;white-space:normal;overflow-wrap:break-word;word-break:normal;font-family:system-ui,sans-serif;
  z-index:10000;box-shadow:0 12px 32px rgba(0,0,0,.45)
}
.tip:hover>.tipbox,.tip:focus>.tipbox{display:block}
.tipbox bdi{direction:ltr;unicode-bidi:isolate;display:inline;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#bfdbfe;font-weight:650;white-space:normal}
@media(max-width:1050px){
  .control-hero{grid-template-columns:1fr}.hero-side{align-items:flex-start}.hero-badges{justify-content:flex-start}
  .metrics{grid-template-columns:repeat(3,minmax(120px,1fr))!important}
}
@media(max-width:760px){
  .wrap{padding:14px 12px 54px!important}.control-hero{padding:20px;border-radius:17px}
  .command-nav{top:6px;margin-bottom:12px}.card{padding:17px!important;border-radius:16px!important}
  .row{grid-template-columns:1fr!important;gap:8px!important;padding:11px 0}.row>input[type="number"]{width:100%}
  .fields,.metrics{grid-template-columns:1fr!important}.primary-actions{position:static}
  button,.linkbtn{width:100%;justify-content:center;text-align:center}.hero-side{width:100%}.hero-link{width:100%}
}
'''


_PROFESSIONAL_SCRIPT = r'''
<script>
(function(){
  const qs=(s,r=document)=>r.querySelector(s);
  const qsa=(s,r=document)=>Array.from(r.querySelectorAll(s));

  function addKicker(card,text,accent){
    if(!card||card.dataset.proReady==='1')return;
    card.dataset.proReady='1';
    if(accent)card.dataset.accent=accent;
    const h=qs('h2',card);
    if(!h)return;
    const k=document.createElement('span');
    k.className='card-kicker';
    k.textContent=text;
    h.parentNode.insertBefore(k,h);
  }

  function decorate(){
    const wrap=qs('.wrap');
    if(!wrap)return;

    const actions=qsa('.actions').find(x=>qs('#saveBtn',x));
    if(actions)actions.classList.add('primary-actions');

    for(const card of qsa('.card')){
      const title=(qs('h2',card)?.textContent||'').trim();
      if(card.id==='factors'){addKicker(card,'Signal engine','blue');continue}
      if(title.startsWith('Decision & execution')){
        card.id='execution-gates';addKicker(card,'Execution policy','blue');
      }else if(title.startsWith('Optional workflow')){
        card.id='signal-overlays';addKicker(card,'Context inputs','purple');
      }else if(title.startsWith('Live news calendar')){
        card.id='news-calendar';addKicker(card,'Event risk','amber');
      }else if(title.startsWith('Model-recommended')){
        card.id='recommended-profile';addKicker(card,'Adaptive research','green');
      }else if(title.startsWith('LONA independent')){
        card.id='lona-validation';addKicker(card,'Independent validation','green');
      }else if(title.startsWith('Our Model vs LONA')){
        card.id='engine-comparison';addKicker(card,'Cross-engine parity','purple');
      }else if(title.startsWith('Historical continuous')){
        card.id='historical-replay';addKicker(card,'Backtest workspace','amber');
      }
    }

    if(actions&&!qs('.ninja-note')){
      const note=document.createElement('div');
      note.className='ninja-note';
      note.innerHTML='<b>DEMO RISK</b><span>Ninja is intentionally aggressive. It is visually separated from normal research presets to reduce accidental use.</span>';
      actions.insertAdjacentElement('afterend',note);
    }

    const nav=qs('.command-nav');
    if(nav&&!nav.dataset.watchReady){
      nav.dataset.watchReady='1';
      const links=qsa('a[href^="#"]',nav);
      const pairs=links.map(a=>[a,qs(a.getAttribute('href'))]).filter(x=>x[1]);
      if('IntersectionObserver' in window){
        const obs=new IntersectionObserver(entries=>{
          const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio)[0];
          if(!visible)return;
          for(const [a,el] of pairs)a.classList.toggle('active',el===visible.target);
        },{rootMargin:'-18% 0px -67% 0px',threshold:[0,.1,.35,.7]});
        for(const [,el] of pairs)obs.observe(el);
      }
    }
  }

  decorate();
  new MutationObserver(()=>decorate()).observe(document.body,{childList:true,subtree:true});
  setTimeout(decorate,0);
  setTimeout(decorate,500);
})();
</script>
'''


def inject_forex_factory_control(html: str) -> str:
    'Add live news controls, PDF mode, robust tooltips, and professional UX.'

    marker = '<p class="actions"><button id="saveBtn">'
    card = r'''
<div class="card"><h2>Live news calendar</h2>
<div class="row"><label title="تقویم اقتصادی Forex Factory؛ برای طلا رویدادهای مهم USD را بررسی می‌کند.">Forex Factory calendar</label><input id="forex_factory_enabled" type="checkbox" style="width:22px;height:22px"><span id="forexFactoryState" class="muted">OFF</span></div>
<div id="forexFactoryStatus" class="statusbox muted">Checking Forex Factory calendar…</div>
<p class="muted">For XAUUSD the Bridge watches USD High/Medium events from the Forex Factory weekly JSON export. High-impact releases can feed the existing <code>news_risk</code> safety gate. A feed timeout returns <code>UNKNOWN</code>; the current default <code>block_unknown_news=false</code> keeps this fail-open.</p>
</div>
'''
    if marker in html and 'id="forex_factory_enabled"' not in html:
        html = html.replace(marker, card + marker, 1)

    ninja_marker = '<button id="ninjaPresetBtn" class="ninja">Ninja · Aggressive DEMO</button>'
    pdf_button = '<button id="pdfModeBtn" class="pdfmode">PDF Mode: OFF</button>'
    if ninja_marker in html and 'id="pdfModeBtn"' not in html:
        html = html.replace(ninja_marker, ninja_marker + pdf_button, 1)

    old_header = (
        '<h1>MetaTrader AI v2 — Bridge Control</h1>'
        '<p class="muted">Live explainable thresholds, continuous historical replay and independent LONA validation.</p>'
        '<div class="nav"><a href="/train">Open Training Lab →</a></div>'
    )
    professional_header = r'''
<header class="control-hero">
  <div>
    <div class="hero-eyebrow">META TRADER AI</div>
    <h1>Bridge Control Center</h1>
    <p>Live explainable thresholds, guarded execution controls, workflow signals, independent validation and continuous historical replay — organized by trading workflow.</p>
  </div>
  <div class="hero-side">
    <div class="hero-badges">
      <span class="hero-badge live">● BRIDGE CONTROL</span>
      <span class="hero-badge">XAUUSD · M15</span>
      <span class="hero-badge">DEMO GUARDED</span>
    </div>
    <a class="hero-link" href="/train">Open Training Lab →</a>
  </div>
</header>
<nav class="command-nav" aria-label="Control sections">
  <a href="#factors">Decision factors</a>
  <a href="#execution-gates">Execution</a>
  <a href="#signal-overlays">Signals</a>
  <a href="#news-calendar">News</a>
  <a href="#recommended-profile">Recommended</a>
  <a href="#lona-validation">Validation</a>
  <a href="#engine-comparison">Comparison</a>
  <a href="#historical-replay">Backtest</a>
</nav>'''
    if old_header in html and 'class="control-hero"' not in html:
        html = html.replace(old_header, professional_header, 1)

    if '</style>' in html and 'MetaTrader AI professional control-center skin' not in html:
        html = html.replace('</style>', _PROFESSIONAL_STYLE + '</style>', 1)

    ff_script = r'''
<script>
(function(){
  const ff=document.getElementById('forex_factory_enabled');
  const state=document.getElementById('forexFactoryState');
  const status=document.getElementById('forexFactoryStatus');
  if(!ff||!state||!status)return;
  function paint(on){state.textContent=on?'ON':'OFF';state.className=on?'ok':'muted'}
  async function refreshFF(){
    try{
      const cfg=await (await fetch('/news/sources')).json();
      ff.checked=Boolean(cfg.forex_factory_enabled);paint(ff.checked);
      const d=await (await fetch('/news/status')).json();
      const last=d.last;
      status.className='statusbox '+(last&&last.available?(last.risk==='HIGH'?'bad':last.risk==='MEDIUM'?'warn':'ok'):'muted');
      status.textContent=last?`${last.risk} · ${last.reason}`:`${d.enabled?'Enabled':'Disabled'} · waiting for next live /analyze call`;
    }catch(e){status.className='statusbox bad';status.textContent='Forex Factory status failed: '+e.message}
  }
  ff.onchange=async()=>{
    ff.disabled=true;
    try{
      const r=await fetch('/news/sources',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({forex_factory_enabled:ff.checked})});
      if(!r.ok)throw new Error('save failed');
      paint(ff.checked);await refreshFF();
    }catch(e){ff.checked=!ff.checked;paint(ff.checked);status.className='statusbox bad';status.textContent=e.message}
    finally{ff.disabled=false}
  };
  refreshFF();
  setInterval(refreshFF,30000);
})();
</script>
'''
    if '</body>' in html and '/news/sources' not in html:
        html = html.replace('</body>', ff_script + '</body>', 1)

    pdf_script = r'''
<script>
(function(){
  const btn=document.getElementById('pdfModeBtn');
  if(!btn)return;
  function paint(mode){
    const on=String(mode||'NORMAL').toUpperCase()==='PDF';
    btn.textContent=on?'PDF Mode: ON':'PDF Mode: OFF';
    btn.classList.toggle('on',on);
    btn.dataset.mode=on?'PDF':'NORMAL';
  }
  async function refreshPdfMode(){
    try{
      const r=await fetch('/strategy/config');
      const d=await r.json();
      if(!r.ok)throw new Error(d.detail||'strategy config failed');
      paint(d.strategy_mode);
    }catch(e){btn.textContent='PDF Mode: ERROR';btn.classList.remove('on')}
  }
  btn.onclick=async()=>{
    btn.disabled=true;
    try{
      const get=await fetch('/strategy/config');
      const cfg=await get.json();
      if(!get.ok)throw new Error(cfg.detail||'load failed');
      cfg.strategy_mode=String(cfg.strategy_mode||'NORMAL').toUpperCase()==='PDF'?'NORMAL':'PDF';
      const put=await fetch('/strategy/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
      const saved=await put.json();
      if(!put.ok)throw new Error(saved.detail||'save failed');
      paint(saved.strategy_mode);
    }catch(e){btn.textContent='PDF Mode: ERROR'}
    finally{btn.disabled=false}
  };
  refreshPdfMode();
})();
</script>
'''
    if '</body>' in html and 'PDF Mode toggle runtime' not in html:
        html = html.replace('</body>', '<!-- PDF Mode toggle runtime -->' + pdf_script + '</body>', 1)

    tooltip_script = r'''
<script>
(function(){
  const latinRun=/([A-Za-z0-9][A-Za-z0-9_.:+/%=-]*(?:\\s+[A-Za-z0-9][A-Za-z0-9_.:+/%=-]*)*)/g;

  function renderMixedDirection(box,text){
    box.textContent='';
    let cursor=0;
    for(const match of text.matchAll(latinRun)){
      const start=match.index||0;
      if(start>cursor)box.appendChild(document.createTextNode(text.slice(cursor,start)));
      const isolate=document.createElement('bdi');
      isolate.dir='ltr';
      isolate.textContent=match[0];
      box.appendChild(isolate);
      cursor=start+match[0].length;
    }
    if(cursor<text.length)box.appendChild(document.createTextNode(text.slice(cursor)));
  }

  function enhanceTip(tip){
    if(tip.dataset.mixedBidiReady==='1')return;
    const text=tip.dataset.tip||'';
    if(!text)return;
    tip.dataset.mixedBidiReady='1';
    const box=document.createElement('span');
    box.className='tipbox';
    box.dir='rtl';
    box.lang='fa';
    box.setAttribute('role','tooltip');
    renderMixedDirection(box,text);
    tip.appendChild(box);
  }

  function enhanceAll(root=document){
    if(root.matches&&root.matches('.tip'))enhanceTip(root);
    if(root.querySelectorAll)root.querySelectorAll('.tip').forEach(enhanceTip);
  }

  enhanceAll();
  const observer=new MutationObserver(records=>{
    for(const record of records){
      for(const node of record.addedNodes){
        if(node.nodeType===1)enhanceAll(node);
      }
    }
  });
  observer.observe(document.documentElement,{childList:true,subtree:true});
  setTimeout(()=>enhanceAll(),0);
  setTimeout(()=>enhanceAll(),500);
})();
</script>
'''
    if '</body>' in html and 'mixed-bidi tooltip runtime' not in html:
        html = html.replace('</body>', '<!-- mixed-bidi tooltip runtime -->' + tooltip_script + '</body>', 1)

    if '</body>' in html and 'professional control UX runtime' not in html:
        html = html.replace('</body>', '<!-- professional control UX runtime -->' + _PROFESSIONAL_SCRIPT + '</body>', 1)
    return html
