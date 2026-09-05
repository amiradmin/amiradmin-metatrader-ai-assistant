# Optional live signal overlays

The Bridge can optionally add three bounded confidence modifiers to the live `/analyze` workflow. All three are OFF by default and can be inserted/removed independently from `/control`.

## Safety semantics

- They modify BUY/SELL total scores only; they are not hard safety gates.
- Unavailable or timed-out sources are fail-open: the six-factor strategy continues unchanged.
- Combined overlay contribution is capped at 10 score points per side so external context cannot dominate the core factors.
- Historical replay/training does **not** inject current Myfxbook or COT values into historical bars. This avoids look-ahead leakage.
- Demo-only execution safeguards remain independent from these toggles.

## Myfxbook retail sentiment

The official Myfxbook `get-community-outlook` API is used as a small contrarian modifier. Cache TTL is 5 minutes.

Preferred setup:

```bash
export MYFXBOOK_SESSION='your-session-id'
```

Alternatively the Bridge can create a session from environment variables:

```bash
export MYFXBOOK_EMAIL='you@example.com'
export MYFXBOOK_PASSWORD='...'
```

Do not put credentials in Git or in `strategy_config.json`.

## Order-flow proxy

The local order-flow overlay uses VWAP, a directional activity/CVD proxy and a volume-profile-style POC estimate. EA v0.24 sends each completed M15 bar's MT5 `tick_volume` in the live snapshot, so the overlay uses broker tick activity when v0.24 is installed. Older EA snapshots remain compatible and fall back to candle-range activity, clearly labeled as an `OHLC activity proxy`.

This is an independent implementation. It is not a copy of a TradingView script and is not a claim of centralized order-book data for spot XAUUSD.

## CFTC COT

The Bridge queries the CFTC Public Reporting Environment Disaggregated Futures Only dataset for Gold and reads Managed Money long/short positioning. Cache TTL is 6 hours. COT is weekly macro context, so its maximum modifier is intentionally smaller than intraday context.

## Status

```bash
curl -s http://127.0.0.1:8000/integrations/status | python3 -m json.tool
```

After a live `/analyze` call, the status also includes the last overlay result/reason. Each decision stored in `data/decisions.jsonl` includes base scores, overlay modifiers and per-source reasons for Pit Stop diagnosis.
