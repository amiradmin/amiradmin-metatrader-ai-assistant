# Deep multi-year MT5 history sync

The normal `MetaTraderAI_DecisionTree` EA keeps the most recent M15 bars fresh. For model training across one or more years, run the one-shot `mt5/DeepHistorySync.mq5` script.

## What changed

- History is stored in `.mtai_data/history/history.sqlite3` instead of repeatedly rewriting a large JSON file.
- Existing legacy `XAUUSD_o_M15.json` history is migrated automatically and kept as `*.json.migrated` backup.
- The Bridge keeps up to **500,000 bars per symbol/timeframe by default**. Override with `MTAI_HISTORY_MAX_BARS`; use `0` for no Bridge-side pruning.
- `DeepHistorySync.mq5` uploads bars in small chunks and keeps walking backward until MT5/the broker has no older data, unless `MaxBars` is set to a positive limit.

## Run it

1. Keep the Python Bridge running on `http://127.0.0.1:8000`.
2. In MT5, make sure that URL is allowed under `Tools -> Options -> Expert Advisors -> Allow WebRequest`.
3. Copy `mt5/DeepHistorySync.mq5` to your terminal's `MQL5/Scripts/` directory.
4. Compile it in MetaEditor.
5. In Navigator -> Scripts, run `DeepHistorySync` on the XAUUSD chart.
6. Keep the defaults for an unrestricted first pass:

```text
TradeSymbol       = XAUUSD_o
HistoryTimeframe  = PERIOD_M15
ChunkBars         = 2500
MaxBars           = 0       # as far back as broker/terminal provides
```

The script prints each uploaded date range and shows progress on the chart. It is safe to run again: the Bridge upserts bars by timestamp rather than duplicating them.

After completion, refresh:

```text
http://127.0.0.1:8000/train
http://127.0.0.1:8000/control
```

The date pickers will automatically expand to the earliest synced broker date.

## If MT5 stops earlier than expected

The script cannot invent history that the broker/terminal does not expose. If it stops too recently:

- open an XAUUSD M15 chart and scroll far left to encourage MT5 to download older history;
- increase MT5's `Max bars in chart` setting under `Tools -> Options -> Charts` if it is restrictive;
- wait for history download to finish, then run `DeepHistorySync` again;
- confirm the broker actually offers older XAUUSD history for that symbol.

The normal live EA can remain attached afterward; its periodic recent-history sync will update current bars without deleting the older SQLite history.
