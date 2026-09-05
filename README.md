# AmirAdmin MetaTrader AI Assistant v2

Explainable, six-factor MetaTrader 5 decision engine for **XAUUSD / M15** with a live on-chart decision tree, bridge-adjustable thresholds, guarded automatic DEMO execution, trade journaling, forward KPIs, and evidence-based learning recommendations.

> This repository starts in guarded mode. The Python engine may return BUY/SELL, but the supplied EA has a local `DemoOnly=true` hard gate by default. Test on demo before considering any live-money changes.

## The six decision factors

Each factor produces independent BUY and SELL scores from 0–100. The candidate side must satisfy the configured threshold/count rules before execution.

1. **Dynamic levels** — EMA20/EMA50 structure, slope, pullback/extension.
2. **Static levels / Order Block** — recent support/resistance plus an impulse/order-block proxy.
3. **Fibonacci** — 0.382/0.50/0.618 retracement proximity in current trend context.
4. **Patterns / Harmonic** — engulfing, rejection/pin bars, lightweight AB=CD symmetry.
5. **Pivots** — previous-day classic Pivot, S1 and R1 reaction context.
6. **Divergence / Momentum** — RSI state/divergence plus normalized MACD histogram.

The engine deliberately separates **analysis** from **safety**. Even a strong BUY/SELL is changed to WAIT when a hard safety gate fails.

## Architecture

```text
MT5 completed M15 bars + previous D1 H/L/C
                 |
                 v
        POST /analyze (FastAPI)
                 |
      +----------+----------+
      | 6 factor analyzers  |
      +----------+----------+
                 |
         weighted decision
                 |
       safety gates / config
                 |
         BUY / SELL / WAIT
                 |
      +----------+----------+
      | MT5 chart tree panel|
      | guarded DEMO trader |
      +----------+----------+
                 |
        closed trade outcome
                 |
      POST /performance/trades
                 |
   Expectancy / PF / DD / trend
                 |
      /learning/recommendation
```

## Quick start

### 1. Run the Python bridge

```bash
cd ~/Documents/Presentation

git clone https://github.com/amiradmin/amiradmin-metatrader-ai-assistant.git
cd amiradmin-metatrader-ai-assistant

uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'

uv run uvicorn meta_trader_ai.api:app --host 127.0.0.1 --port 8000
```

Check:

```bash
curl http://127.0.0.1:8000/health
```

### 2. Allow MT5 WebRequest

In MT5:

`Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL`

Add:

```text
http://127.0.0.1:8000
```

### 3. Compile and attach the EA

Copy:

```text
mt5/MetaTraderAI_DecisionTree.mq5
```

into your terminal's `MQL5/Experts/` directory, compile it in MetaEditor, then attach it to the XAUUSD M15 chart.

Suggested first-run inputs:

```text
TradeSymbol       = XAUUSD_o   # change to your broker symbol
AnalysisTimeframe = PERIOD_M15
EnableAutoTrading = true
DemoOnly          = true
RiskPercent       = 0.50
RewardRiskRatio   = 2.0
MaxOpenTrades     = 1
```

The EA sends **completed bars only**, so the decision is not based on an unfinished candle.

## Live threshold configuration

Current configuration:

```bash
curl http://127.0.0.1:8000/strategy/config | python -m json.tool
```

Example: raise Fibonacci minimum to 65 without recompiling the EA:

```bash
curl -X PUT http://127.0.0.1:8000/strategy/config \
  -H 'Content-Type: application/json' \
  -d '{
    "dynamic_levels":{"min_score":60,"weight":1.0,"required":true},
    "static_levels":{"min_score":65,"weight":1.2,"required":true},
    "fibonacci":{"min_score":65,"weight":0.8,"required":false},
    "patterns":{"min_score":60,"weight":1.0,"required":false},
    "pivots":{"min_score":55,"weight":0.8,"required":false},
    "divergence":{"min_score":60,"weight":1.0,"required":false},
    "decision":{"min_pass_count":4,"min_total_score":68,"min_side_edge":12},
    "safety":{"max_spread_points":60,"block_high_news":true,"block_unknown_news":false,"demo_only":true}
  }'
```

The bridge persists the active settings to `strategy_config.json`.

## What the chart panel shows

The panel is intentionally explainable, for example:

```text
META TRADER AI v2 | SIX-FACTOR DECISION TREE
XAUUSD_o | M15 | candidate=BUY | FINAL=WAIT
BUY 74.2 | SELL 38.1 | passed 3/6 | need 4/6

|- Dynamic levels        82/60 PASS
|- Static / OrderBlock   73/65 PASS
|- Fibonacci             49/55 FAIL
|- Patterns / Harmonic   67/60 PASS
|- Pivots                51/55 FAIL
`- Divergence / Momentum 58/60 FAIL

PERF: trades=37  E=+0.18R  WR=43.2%  DD=4.10R  trend=IMPROVING
EXECUTION: BLOCKED / WAIT
```

When `FINAL=BUY` or `FINAL=SELL` and `trade_allowed=true`, the EA can open one guarded demo position. The same `signal_id` is never executed twice during the EA session.

## Performance / learning

Closed managed positions are posted back to the bridge as R-multiples. The bridge exposes:

```bash
curl http://127.0.0.1:8000/performance
curl http://127.0.0.1:8000/learning/recommendation
```

Primary KPI is **forward expectancy in R/trade**, with supporting:

- win rate
- profit factor
- maximum drawdown in R
- previous-vs-current expectancy
- `IMPROVING / DEGRADING / FLAT / COLLECTING`

Learning is intentionally **candidate-based rather than self-modifying**. After enough closed trades, `/learning/recommendation` can propose +5/-5 threshold candidates when the observed expectancy around a factor threshold supports it. The proposal is **not applied automatically**; test it in shadow/demo forward data, then apply with `PUT /strategy/config` if it proves better. This avoids the common failure mode of overfitting after a short winning or losing streak.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | bridge health |
| GET | `/strategy/config` | read active thresholds |
| PUT | `/strategy/config` | update thresholds/weights/gates |
| POST | `/analyze` | analyze market snapshot and return explainable tree |
| POST | `/performance/trades` | record a closed trade outcome |
| GET | `/performance` | forward KPI summary |
| GET | `/learning/recommendation` | evidence-based candidate threshold changes |

## Tests

```bash
uv run pytest -q
```

Current unit tests cover explainable six-factor output, default real-account blocking, and expectancy/drawdown calculations.

## Important next integrations

This first version uses `news_risk=UNKNOWN` from the EA. The safety schema already supports LOW/MEDIUM/HIGH/UNKNOWN, so an economic-calendar/news collector can be connected next without redesigning the decision tree. The current default does **not** block UNKNOWN news; HIGH news can be configured as a hard stop once a live news source is connected.
