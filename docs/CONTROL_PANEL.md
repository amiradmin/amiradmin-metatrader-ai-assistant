# Bridge control panel

Run the bridge, then open:

```text
http://127.0.0.1:8000/control
```

The page has live sliders for the minimum score of all six factors plus the global decision thresholds. Saving writes the same `StrategyConfig` used by `POST /analyze`, so the next MT5 analysis uses the new values without recompiling the EA.

The JSON API remains available at `GET/PUT /strategy/config` for automation or versioned experiments.
