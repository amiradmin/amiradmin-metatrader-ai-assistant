from __future__ import annotations


def inject_forex_factory_control(html: str) -> str:
    """Add live news controls plus the independent PDF strategy-mode toggle."""

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

    if '</style>' in html and 'button.pdfmode' not in html:
        html = html.replace(
            '</style>',
            'button.pdfmode{background:#0f766e;box-shadow:0 0 0 1px #34d399 inset}'
            'button.pdfmode.on{background:#16a34a;box-shadow:0 0 0 1px #86efac inset}'
            '.tip:hover::after,.tip:focus::after{'
            'width:320px;max-width:min(340px,calc(100vw - 32px));'
            'direction:rtl;unicode-bidi:plaintext;text-align:start;'
            'overflow-wrap:anywhere;word-break:normal;line-height:1.85;'
            'font-family:system-ui,sans-serif}'
            '</style>',
            1,
        )

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
    return html
