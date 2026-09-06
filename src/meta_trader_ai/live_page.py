from __future__ import annotations


def live_page_html() -> str:
    return r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AMIR META TRADER AI — Live</title>
<style>
:root{color-scheme:dark;--bg:#071019;--panel:#0c1724;--panel2:#0a1320;--border:#1d2c3d;--muted:#8ea0b6;--text:#eff6ff;--blue:#38bdf8;--green:#4ade80;--red:#fb7185;--amber:#fbbf24;--purple:#c4b5fd}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 12% 0,rgba(56,189,248,.10),transparent 28%),linear-gradient(180deg,#071019,#060a10);color:var(--text);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.wrap{max-width:1440px;margin:auto;padding:22px}.hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;border:1px solid var(--border);background:linear-gradient(135deg,rgba(18,31,48,.94),rgba(9,17,29,.96));padding:22px 24px;border-radius:20px;box-shadow:0 20px 60px rgba(0,0,0,.25)}.eyebrow{font-size:11px;letter-spacing:.16em;font-weight:900;color:#7dd3fc}.hero h1{font-size:30px;margin:6px 0 7px;letter-spacing:-.035em}.hero p{margin:0;color:var(--muted);font-size:13px;line-height:1.7}.badges{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.badge{padding:7px 10px;border:1px solid var(--border);border-radius:999px;background:#08111c;color:#cbd5e1;font-size:11px;font-weight:800}.badge.ok{color:#86efac;border-color:rgba(74,222,128,.3);background:rgba(22,101,52,.12)}.badge.bad{color:#fecdd3;border-color:rgba(251,113,133,.3);background:rgba(159,18,57,.12)}.badge.warn{color:#fde68a;border-color:rgba(251,191,36,.28);background:rgba(161,98,7,.12)}.nav{display:flex;gap:8px;margin:12px 0 18px}.nav a{color:#bfdbfe;text-decoration:none;border:1px solid var(--border);border-radius:10px;padding:9px 12px;background:#091421;font-size:12px;font-weight:700}.grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(320px,.85fr);gap:14px}.card{background:linear-gradient(180deg,rgba(13,24,38,.96),rgba(8,16,27,.96));border:1px solid var(--border);border-radius:18px;padding:18px;box-shadow:0 14px 40px rgba(0,0,0,.18)}.card h2{font-size:15px;margin:0 0 14px;color:#f8fbff}.chart-card{padding:14px}.chart-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;padding:3px 4px 12px}.symbol{font-size:18px;font-weight:850}.quote{font-size:24px;font-weight:900;font-variant-numeric:tabular-nums}.sub{color:var(--muted);font-size:12px}.canvas-wrap{height:540px;position:relative;border:1px solid #172638;background:#07111d;border-radius:14px;overflow:hidden}canvas{display:block;width:100%;height:100%}.decision{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}.metric{padding:13px;border-radius:13px;border:1px solid #192a3c;background:#08131f}.metric small{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}.metric b{font-size:20px;font-variant-numeric:tabular-nums}.big-decision{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;padding:16px;border:1px solid #203246;border-radius:14px;background:#08131f}.big-decision strong{font-size:32px;letter-spacing:.04em}.BUY{color:var(--green)}.SELL{color:var(--red)}.WAIT{color:var(--amber)}.status-list{display:grid;gap:9px}.status-row{display:flex;justify-content:space-between;gap:12px;padding:10px 11px;border:1px solid #172638;border-radius:11px;background:#08131f;font-size:12px}.status-row span:first-child{color:var(--muted)}.positions{margin-top:14px}.tablewrap{overflow:auto;border:1px solid #172638;border-radius:12px}.positions table{width:100%;border-collapse:collapse;min-width:720px}.positions th,.positions td{padding:10px;border-bottom:1px solid #162638;text-align:left;font-size:12px}.positions th{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.06em;background:#0a1623;position:sticky;top:0}.empty{padding:18px;color:var(--muted);font-size:12px}.footer{margin-top:14px;color:#65758a;font-size:11px;text-align:center}.pulse{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:var(--green);box-shadow:0 0 12px rgba(74,222,128,.8)}.stale .pulse{background:var(--red);box-shadow:0 0 12px rgba(251,113,133,.7)}@media(max-width:1050px){.grid{grid-template-columns:1fr}.hero{flex-direction:column}.badges{justify-content:flex-start}.canvas-wrap{height:460px}}@media(max-width:680px){.wrap{padding:12px}.decision{grid-template-columns:1fr 1fr}.metric:last-child{grid-column:1/-1}.hero h1{font-size:24px}.canvas-wrap{height:380px}.quote{font-size:20px}}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div>
      <div class="eyebrow">AMIR META TRADER AI</div>
      <h1>Live Trading Dashboard</h1>
      <p>Live MT5 market feed, current decision, execution gates and EA-managed positions.</p>
    </div>
    <div class="badges">
      <span id="bridgeBadge" class="badge warn">BRIDGE WAITING</span>
      <span id="marketBadge" class="badge warn">MARKET UNKNOWN</span>
      <span id="algoBadge" class="badge warn">ALGO UNKNOWN</span>
      <span id="accountBadge" class="badge">ACCOUNT —</span>
    </div>
  </header>
  <div class="nav"><a href="/control">Control Center</a><a href="/train">Training Lab</a></div>

  <section class="grid">
    <div class="card chart-card">
      <div class="chart-head">
        <div><div id="symbol" class="symbol">XAUUSD_o · M15</div><div id="feedAge" class="sub">Waiting for MT5 snapshot…</div></div>
        <div style="text-align:right"><div id="quote" class="quote">—</div><div id="spread" class="sub">Spread —</div></div>
      </div>
      <div id="canvasWrap" class="canvas-wrap stale"><canvas id="chart"></canvas></div>
    </div>

    <div>
      <div class="card">
        <h2>Decision & execution</h2>
        <div class="decision">
          <div class="big-decision"><span>FINAL</span><strong id="decision" class="WAIT">WAIT</strong></div>
          <div class="metric"><small>Buy score</small><b id="buyScore">—</b></div>
          <div class="metric"><small>Sell score</small><b id="sellScore">—</b></div>
          <div class="metric"><small>Edge</small><b id="edge">—</b></div>
          <div class="metric"><small>Passed</small><b id="passed">—</b></div>
          <div class="metric"><small>Risk / trade</small><b id="risk">—</b></div>
          <div class="metric"><small>Reward : Risk</small><b id="rr">—</b></div>
        </div>
      </div>

      <div class="card" style="margin-top:14px">
        <h2>Execution readiness</h2>
        <div class="status-list">
          <div class="status-row"><span>Trade allowed</span><b id="tradeAllowed">—</b></div>
          <div class="status-row"><span>Strategy mode</span><b id="strategyMode">—</b></div>
          <div class="status-row"><span>News risk</span><b id="newsRisk">—</b></div>
          <div class="status-row"><span>PDF status</span><b id="pdfStatus">—</b></div>
          <div class="status-row"><span>Account equity</span><b id="equity">—</b></div>
          <div class="status-row"><span>Primary blocker</span><b id="blocker" style="text-align:right;max-width:220px">—</b></div>
        </div>
      </div>
    </div>
  </section>

  <section class="card positions">
    <h2>EA-managed open positions</h2>
    <div id="positions"></div>
  </section>
  <div class="footer">This dashboard mirrors the latest payload received from the MT5 EA. It does not place orders by itself.</div>
</div>
<script>
const $=id=>document.getElementById(id);
let latestBars=[];
function fmt(n,d=2){return Number.isFinite(Number(n))?Number(n).toFixed(d):'—'}
function clsBadge(el,state){el.className='badge '+state}
function drawChart(){
  const canvas=$('chart'), wrap=$('canvasWrap');
  const rect=canvas.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
  canvas.width=Math.max(1,Math.floor(rect.width*dpr)); canvas.height=Math.max(1,Math.floor(rect.height*dpr));
  const ctx=canvas.getContext('2d'); ctx.scale(dpr,dpr); const w=rect.width,h=rect.height;
  ctx.clearRect(0,0,w,h); ctx.fillStyle='#07111d';ctx.fillRect(0,0,w,h);
  const bars=latestBars.slice(-80); if(!bars.length){ctx.fillStyle='#8292a7';ctx.font='14px system-ui';ctx.fillText('Waiting for market data…',24,36);return}
  const pad={l:12,r:66,t:18,b:28}; const cw=w-pad.l-pad.r,ch=h-pad.t-pad.b;
  let min=Math.min(...bars.map(b=>Number(b.low))), max=Math.max(...bars.map(b=>Number(b.high))); if(max<=min){max=min+1}
  const span=max-min, extra=span*.06; min-=extra;max+=extra;
  const y=p=>pad.t+(max-p)/(max-min)*ch;
  ctx.strokeStyle='rgba(148,163,184,.09)';ctx.lineWidth=1;
  for(let i=0;i<=5;i++){const yy=pad.t+ch*i/5;ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke(); const price=max-(max-min)*i/5;ctx.fillStyle='#7890a8';ctx.font='10px system-ui';ctx.fillText(price.toFixed(2),w-pad.r+8,yy+3)}
  const step=cw/bars.length, body=Math.max(2,Math.min(9,step*.58));
  bars.forEach((b,i)=>{const x=pad.l+i*step+step/2, o=Number(b.open),c=Number(b.close),hi=Number(b.high),lo=Number(b.low),up=c>=o;const col=up?'#4ade80':'#fb7185';ctx.strokeStyle=col;ctx.fillStyle=col;ctx.beginPath();ctx.moveTo(x,y(hi));ctx.lineTo(x,y(lo));ctx.stroke();const top=Math.min(y(o),y(c)),bh=Math.max(1,Math.abs(y(o)-y(c)));ctx.fillRect(x-body/2,top,body,bh)});
  const last=bars[bars.length-1], lp=Number(last.close);ctx.strokeStyle='#38bdf8';ctx.setLineDash([5,5]);ctx.beginPath();ctx.moveTo(pad.l,y(lp));ctx.lineTo(w-pad.r,y(lp));ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#7dd3fc';ctx.font='10px system-ui';ctx.fillText(lp.toFixed(2),w-pad.r+8,y(lp)+3);
  [0,Math.floor(bars.length/2),bars.length-1].forEach(i=>{const d=new Date(Number(bars[i].time)*1000);ctx.fillStyle='#71849a';ctx.font='10px system-ui';ctx.fillText(d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}),pad.l+i*step,pad.t+ch+18)});
}
function renderPositions(items){
  if(!items||!items.length){$('positions').innerHTML='<div class="empty">No open positions managed by this EA.</div>';return}
  const rows=items.map(p=>`<tr><td>${p.ticket}</td><td class="${p.side}"><b>${p.side}</b></td><td>${fmt(p.volume,2)}</td><td>${fmt(p.price_open,2)}</td><td>${fmt(p.stop_loss,2)}</td><td>${fmt(p.take_profit,2)}</td><td>${fmt(p.current_price,2)}</td><td class="${Number(p.profit)>=0?'BUY':'SELL'}">${fmt(p.profit,2)}</td></tr>`).join('');
  $('positions').innerHTML=`<div class="tablewrap"><table><thead><tr><th>Ticket</th><th>Side</th><th>Volume</th><th>Entry</th><th>SL</th><th>TP</th><th>Current</th><th>P/L</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
function render(d){
  const s=d.snapshot, x=d.decision, online=Boolean(d.bridge_online);
  clsBadge($('bridgeBadge'),online?'ok':'bad');$('bridgeBadge').textContent=online?'BRIDGE ONLINE':'BRIDGE STALE';$('canvasWrap').classList.toggle('stale',!online);
  if(!s||!x)return;
  const market=s.market_session_open===true, algo=s.terminal_trade_allowed===true&&s.mql_trade_allowed===true;
  clsBadge($('marketBadge'),market?'ok':'bad');$('marketBadge').textContent=market?'MARKET OPEN':'MARKET CLOSED';
  clsBadge($('algoBadge'),algo?'ok':'bad');$('algoBadge').textContent=algo?'ALGO READY':'ALGO BLOCKED';
  $('accountBadge').textContent='ACCOUNT '+(s.account_mode||'—');clsBadge($('accountBadge'),s.account_mode==='DEMO'?'ok':'warn');
  $('symbol').textContent=`${s.symbol} · ${s.timeframe}`;$('feedAge').innerHTML=`<span class="pulse"></span>Last MT5 update ${d.age_seconds==null?'—':fmt(d.age_seconds,0)+'s'} ago`;
  $('quote').textContent=`${fmt(s.bid,2)} / ${fmt(s.ask,2)}`;$('spread').textContent=`Spread ${s.spread_points} points`;
  const dec=x.decision||'WAIT';$('decision').textContent=dec;$('decision').className=dec;
  $('buyScore').textContent=fmt(x.buy_score,1);$('sellScore').textContent=fmt(x.sell_score,1);$('edge').textContent=fmt(x.side_edge,1);$('passed').textContent=`${x.passed_count}/${x.min_pass_count}`;$('risk').textContent=fmt(x.risk_percent,2)+'%';$('rr').textContent='1:'+fmt(x.reward_risk_ratio,1);
  $('tradeAllowed').textContent=x.trade_allowed?'YES':'NO';$('tradeAllowed').className=x.trade_allowed?'BUY':'SELL';$('strategyMode').textContent=x.strategy_mode||'—';$('newsRisk').textContent=s.news_risk||'—';$('pdfStatus').textContent=x.pdf_status||'—';$('equity').textContent=s.account_equity==null?'—':'$'+fmt(s.account_equity,2);$('blocker').textContent=x.primary_blocker||'None';
  latestBars=[...(s.bars||[])];if(s.live_bar)latestBars.push(s.live_bar);drawChart();renderPositions(s.positions||[]);
}
async function refresh(){try{const r=await fetch('/live/data',{cache:'no-store'}),d=await r.json();render(d)}catch(e){clsBadge($('bridgeBadge'),'bad');$('bridgeBadge').textContent='BRIDGE ERROR'}}
window.addEventListener('resize',drawChart);refresh();setInterval(refresh,3000);
</script>
</body></html>'''
