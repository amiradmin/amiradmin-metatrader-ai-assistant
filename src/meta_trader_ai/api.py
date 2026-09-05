from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .config_store import StrategyConfigStore
from .decision_engine import build_decision
from .journal import DecisionJournal
from .learning import recommend_thresholds
from .models import DecisionResponse, LearningRecommendation, MarketSnapshot, PerformanceSummary, StrategyConfig, TradeOutcome
from .performance import PerformanceStore

app = FastAPI(title="MetaTrader AI Assistant v2", version="0.1.1")
config_store = StrategyConfigStore()
performance_store = PerformanceStore()
decision_journal = DecisionJournal()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "six-factor-explainable", "execution": "mt5-demo-guarded"}


@app.get("/strategy/config", response_model=StrategyConfig)
def get_strategy_config() -> StrategyConfig:
    return config_store.load()


@app.put("/strategy/config", response_model=StrategyConfig)
def put_strategy_config(config: StrategyConfig) -> StrategyConfig:
    return config_store.save(config)


@app.post("/analyze", response_model=DecisionResponse)
def analyze(snapshot: MarketSnapshot) -> DecisionResponse:
    response = build_decision(snapshot, config_store.load(), performance_store.summary())
    decision_journal.append(response.model_dump(mode="json"))
    return response


@app.post("/performance/trades", response_model=PerformanceSummary)
def record_trade(outcome: TradeOutcome) -> PerformanceSummary:
    performance_store.append(outcome)
    return performance_store.summary()


@app.get("/performance", response_model=PerformanceSummary)
def performance() -> PerformanceSummary:
    return performance_store.summary()


@app.get("/learning/recommendation", response_model=LearningRecommendation)
def learning_recommendation() -> LearningRecommendation:
    return recommend_thresholds(config_store.load(), performance_store.load(), decision_journal)


@app.get("/control", response_class=HTMLResponse)
def control_panel() -> str:
    return r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MetaTrader AI Bridge Control</title><style>body{font-family:system-ui,sans-serif;background:#111827;color:#e5e7eb;margin:0;padding:24px}.wrap{max-width:820px;margin:auto}.card{background:#1f2937;border:1px solid #374151;border-radius:16px;padding:20px;margin:14px 0}.row{display:grid;grid-template-columns:210px 1fr 70px;gap:14px;align-items:center;margin:14px 0}input[type=range]{width:100%}input[type=number]{width:66px;background:#111827;color:#fff;border:1px solid #4b5563;border-radius:8px;padding:7px}button{background:#2563eb;color:white;border:0;border-radius:10px;padding:11px 18px;font-weight:700;cursor:pointer}.ok{color:#4ade80}.muted{color:#9ca3af}code{color:#93c5fd}</style></head><body><div class="wrap"><h1>MetaTrader AI v2 — Bridge Control</h1><p class="muted">Change the six minimum scores live. MT5 uses the next analysis response; no EA recompile is needed.</p><div class="card" id="factors"></div><div class="card"><div class="row"><label>Minimum passed factors</label><input id="min_pass_count" type="range" min="1" max="6"><input id="min_pass_count_n" type="number" min="1" max="6"></div><div class="row"><label>Minimum total score</label><input id="min_total_score" type="range" min="0" max="100"><input id="min_total_score_n" type="number" min="0" max="100"></div><div class="row"><label>Minimum BUY/SELL edge</label><input id="min_side_edge" type="range" min="0" max="100"><input id="min_side_edge_n" type="number" min="0" max="100"></div></div><button onclick="save()">Save live thresholds</button> <span id="status"></span><p class="muted">Performance: <code>/performance</code> • Learning candidate: <code>/learning/recommendation</code></p></div><script>const factorNames=['dynamic_levels','static_levels','fibonacci','patterns','pivots','divergence'];let cfg;function bind(id,obj,key){const r=document.getElementById(id),n=document.getElementById(id+'_n');r.value=obj[key];n.value=obj[key];r.oninput=()=>n.value=r.value;n.oninput=()=>r.value=n.value;}async function load(){cfg=await(await fetch('/strategy/config')).json();const box=document.getElementById('factors');box.innerHTML='<h2>Factor minimums</h2>';for(const name of factorNames){box.insertAdjacentHTML('beforeend',`<div class="row"><label>${name.replaceAll('_',' ')}</label><input id="${name}" type="range" min="0" max="100" step="1"><input id="${name}_n" type="number" min="0" max="100" step="1"></div>`);bind(name,cfg[name],'min_score');}bind('min_pass_count',cfg.decision,'min_pass_count');bind('min_total_score',cfg.decision,'min_total_score');bind('min_side_edge',cfg.decision,'min_side_edge');}async function save(){for(const name of factorNames)cfg[name].min_score=Number(document.getElementById(name).value);cfg.decision.min_pass_count=Number(document.getElementById('min_pass_count').value);cfg.decision.min_total_score=Number(document.getElementById('min_total_score').value);cfg.decision.min_side_edge=Number(document.getElementById('min_side_edge').value);const res=await fetch('/strategy/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});const st=document.getElementById('status');if(res.ok){st.textContent='Saved';st.className='ok';}else{st.textContent='Save failed';st.className='';}}load();</script></body></html>'''
