#!/usr/bin/env bash
set -euo pipefail

BRIDGE_BASE_URL="${BRIDGE_BASE_URL:-http://127.0.0.1:8000}"
SYMBOL="${MTAI_SYMBOL:-XAUUSD_o}"
TIMEFRAME="${MTAI_TIMEFRAME:-M15}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${TMPDIR:-/tmp}/mtai_live_debug_${STAMP}"
OUT_ZIP="$(pwd)/mtai_live_debug_${STAMP}.zip"

mkdir -p "$OUT_DIR"

curl -fsS "$BRIDGE_BASE_URL/health" > "$OUT_DIR/health.json"
curl -fsS "$BRIDGE_BASE_URL/strategy/config" > "$OUT_DIR/strategy_config.json"
curl -fsS "$BRIDGE_BASE_URL/performance" > "$OUT_DIR/performance.json"
curl -fsS "$BRIDGE_BASE_URL/history/status?symbol=${SYMBOL}&timeframe=${TIMEFRAME}" > "$OUT_DIR/history_status.json"
curl -fsS "$BRIDGE_BASE_URL/history/export.csv?symbol=${SYMBOL}&timeframe=${TIMEFRAME}" > "$OUT_DIR/${SYMBOL}_${TIMEFRAME}_history.csv"

if [[ -f data/decisions.jsonl ]]; then
  tail -n 500 data/decisions.jsonl > "$OUT_DIR/recent_decisions.jsonl"
fi
if [[ -f data/trade_outcomes.jsonl ]]; then
  tail -n 200 data/trade_outcomes.jsonl > "$OUT_DIR/recent_trade_outcomes.jsonl"
fi
if [[ -f strategy_config.json ]]; then
  cp strategy_config.json "$OUT_DIR/strategy_config_file.json"
fi

cat > "$OUT_DIR/README.txt" <<EOF
MetaTrader AI live debug pack
Created: $(date -Is)
Bridge: ${BRIDGE_BASE_URL}
Symbol: ${SYMBOL}
Timeframe: ${TIMEFRAME}

Contents:
- current Bridge health and strategy parameters
- full synced MT5 history CSV for LONA/backtest
- history status
- current performance summary
- latest decision journal rows (if present)
- latest closed trade outcomes (if present)

Upload this ZIP to ChatGPT for rapid diagnosis and LONA validation.
EOF

python3 - "$OUT_DIR" "$OUT_ZIP" <<'PY'
from pathlib import Path
import sys, zipfile
src = Path(sys.argv[1])
dst = Path(sys.argv[2])
with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for p in sorted(src.iterdir()):
        if p.is_file():
            zf.write(p, p.name)
print(dst)
PY

rm -rf "$OUT_DIR"
printf '\nLive debug pack ready:\n%s\n' "$OUT_ZIP"
