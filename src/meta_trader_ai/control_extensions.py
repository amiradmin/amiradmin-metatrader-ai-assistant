from __future__ import annotations


def inject_forex_factory_control(html: str) -> str:
    """Add the Forex Factory calendar control without coupling it to score overlays."""

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

    script = r'''
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
        html = html.replace('</body>', script + '</body>', 1)
    return html
