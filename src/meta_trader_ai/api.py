from __future__ import annotations

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from .backtest_date import ReplaySettings, run_date_backtest, run_range_backtest
from .config_store import StrategyConfigStore
from .control_extensions import inject_forex_factory_control
from .control_page import control_page_html
from .decision_engine import build_decision
from .external_signals import ExternalSignalHub
from .history import HistoryStore
from .journal import DecisionJournal
from .learning import model_recommended_config, recommend_thresholds
from .live_page import live_page_html
from .live_state import LiveStateStore
from .lona_store import LonaReportStore
from .models import (
    BacktestSummary,
    DecisionResponse,
    HistoryStatus,
    HistorySync,
    LearningRecommendation,
    MarketSnapshot,
    PerformanceSummary,
    RangeBacktestSummary,
    StrategyConfig,
    TradeOutcome,
)
from .news_calendar import ForexFactoryCalendar, NewsSourceStore
from .performance import PerformanceStore
from .training import TrainingRequest, train_thresholds
from .training_page import training_page_html

app = FastAPI(title="MetaTrader AI Assistant v2", version="0.3.6")
config_store = StrategyConfigStore()
performance_store = PerformanceStore()
decision_journal = DecisionJournal()
history_store = HistoryStore()
lona_store = LonaReportStore()
signal_hub = ExternalSignalHub()
news_source_store = NewsSourceStore()
forex_factory_calendar = ForexFactoryCalendar()
live_state_store = LiveStateStore()


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "engine": "six-factor-explainable",
        "execution": "mt5-demo-guarded",
        "historical_replay": "continuous-range-and-multi-position-enabled",
        "training_lab": "multi-position-enabled",
        "lona_validation": "panel-enabled",
        "cross_engine_comparison": "continuous-parity-enabled",
        "signal_overlays": "optional-live-modifiers-enabled",
        "news_calendar": "optional-forex-factory-live-risk-enabled",
        "live_dashboard": "mt5-snapshot-and-decision-enabled",
    }


@app.get("/strategy/config", response_model=StrategyConfig)
def get_strategy_config() -> StrategyConfig:
    return config_store.load()


@app.put("/strategy/config", response_model=StrategyConfig)
def put_strategy_config(config: StrategyConfig) -> StrategyConfig:
    return config_store.save(config)


@app.get("/integrations/status")
def integrations_status() -> dict[str, dict[str, object]]:
    return signal_hub.status(config_store.load())


@app.get("/news/sources")
def get_news_sources() -> dict[str, bool]:
    return news_source_store.load()


@app.put("/news/sources")
def put_news_sources(payload: dict[str, object] = Body(...)) -> dict[str, bool]:
    return news_source_store.save(payload)


@app.get("/news/status")
def news_status() -> dict[str, object]:
    enabled = news_source_store.load()["forex_factory_enabled"]
    return forex_factory_calendar.status(enabled)


def _recommended_payload() -> dict[str, object]:
    current = config_store.load()
    recommended, learning, source = model_recommended_config(
        performance_store.load(), decision_journal
    )
    recommended.strategy_mode = current.strategy_mode
    recommended.safety = current.safety.model_copy(deep=True)
    recommended.integrations = current.integrations.model_copy(deep=True)
    return {
        "source": source,
        "sample_size": learning.sample_size,
        "learning_status": learning.status,
        "current_expectancy_r": learning.current_expectancy_r,
        "config": recommended.model_dump(mode="json"),
        "proposed_thresholds": learning.proposed_thresholds,
        "reasons": learning.reasons,
        "risk_policy": "Signal thresholds only; execution limits, risk and integration toggles are not raised automatically.",
    }


@app.get("/strategy/recommended")
def get_recommended_strategy() -> dict[str, object]:
    return _recommended_payload()


@app.post("/strategy/apply-recommended", response_model=StrategyConfig)
def apply_recommended_strategy() -> StrategyConfig:
    current = config_store.load()
    recommended, _, _ = model_recommended_config(
        performance_store.load(), decision_journal
    )
    recommended.strategy_mode = current.strategy_mode
    recommended.safety = current.safety.model_copy(deep=True)
    recommended.integrations = current.integrations.model_copy(deep=True)
    return config_store.save(recommended)


@app.post("/analyze", response_model=DecisionResponse)
def analyze(snapshot: MarketSnapshot) -> DecisionResponse:
    config = config_store.load()
    live_snapshot = snapshot
    news_assessment = None
    if news_source_store.load()["forex_factory_enabled"]:
        news_assessment = forex_factory_calendar.assess(snapshot)
        live_snapshot = snapshot.model_copy(update={"news_risk": news_assessment.risk})

    overlays = signal_hub.collect(live_snapshot, config)
    response = build_decision(
        live_snapshot,
        config,
        performance_store.summary(),
        overlays=overlays,
    )
    live_state_store.update(live_snapshot, response)
    journal_payload = response.model_dump(mode="json")
    if news_assessment is not None:
        journal_payload["news_context"] = {
            "source": news_assessment.source,
            "available": news_assessment.available,
            "risk": news_assessment.risk,
            "reason": news_assessment.reason,
            "observed_at": news_assessment.observed_at,
            "next_event": news_assessment.next_event,
        }
    decision_journal.append(journal_payload)
    return response


@app.get("/live/data")
def live_data() -> dict[str, object]:
    return live_state_store.payload()


@app.get("/live", response_class=HTMLResponse)
def live_dashboard() -> str:
    return live_page_html()


@app.post("/history/sync", response_model=HistoryStatus)
def sync_history(payload: HistorySync) -> HistoryStatus:
    return history_store.save(payload)


@app.get("/history/status", response_model=HistoryStatus)
def history_status(symbol: str = "XAUUSD_o", timeframe: str = "M15") -> HistoryStatus:
    return history_store.status(symbol, timeframe)


@app.get("/history/export.csv")
def export_history_csv(symbol: str = "XAUUSD_o", timeframe: str = "M15") -> StreamingResponse:
    history = history_store.load(symbol, timeframe)
    if not history:
        raise HTTPException(status_code=409, detail="No MT5 history synced yet.")

    def rows():
        yield "timestamp,broker_date,open,high,low,close,spread_points\n"
        for bar in history:
            yield (
                f"{bar.time},{bar.broker_date},{bar.open},{bar.high},{bar.low},"
                f"{bar.close},{bar.spread_points}\n"
            )

    filename = f"{symbol}_{timeframe}_mt5_history.csv"
    return StreamingResponse(
        rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/lona/status")
def lona_status() -> dict[str, object]:
    return lona_store.load()


@app.post("/lona/status")
def import_lona_status(payload: dict[str, object] = Body(...)) -> dict[str, object]:
    return lona_store.save(payload)


@app.get("/backtest", response_model=BacktestSummary)
def date_backtest(
    date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    symbol: str = "XAUUSD_o",
    timeframe: str = "M15",
    starting_balance: float = Query(1000.0, gt=0, le=100_000_000),
    risk_percent: float = Query(0.5, gt=0, le=5.0),
    reward_risk_ratio: float = Query(2.0, ge=0.5, le=10.0),
    max_open_trades: int = Query(1, ge=1, le=5),
) -> BacktestSummary:
    history = history_store.load_range(
        symbol,
        timeframe,
        date,
        date,
        lookback_bars=300,
    )
    point = history_store.point(symbol, timeframe)
    if not history or point is None:
        raise HTTPException(status_code=409, detail="No MT5 history synced yet.")
    try:
        return run_date_backtest(
            history=history,
            point=point,
            selected_date=date,
            symbol=symbol,
            timeframe=timeframe,
            config=config_store.load(),
            settings=ReplaySettings(
                starting_balance=starting_balance,
                risk_percent=risk_percent,
                reward_risk_ratio=reward_risk_ratio,
                max_open_trades=max_open_trades,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/backtest/range", response_model=RangeBacktestSummary)
def range_backtest(
    start_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    symbol: str = "XAUUSD_o",
    timeframe: str = "M15",
    starting_balance: float = Query(1000.0, gt=0, le=100_000_000),
    risk_percent: float = Query(0.5, gt=0, le=5.0),
    reward_risk_ratio: float = Query(2.0, ge=0.5, le=10.0),
    max_open_trades: int = Query(1, ge=1, le=5),
    profile: str = Query("CURRENT", pattern=r"^(CURRENT|MODEL_BASELINE)$"),
) -> RangeBacktestSummary:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date")
    history = history_store.load_range(
        symbol,
        timeframe,
        start_date,
        end_date,
        lookback_bars=300,
    )
    point = history_store.point(symbol, timeframe)
    if not history or point is None:
        raise HTTPException(status_code=409, detail="No MT5 history synced for this range.")
    config = StrategyConfig() if profile == "MODEL_BASELINE" else config_store.load()
    try:
        return run_range_backtest(
            history=history,
            point=point,
            start_date=start_date,
            end_date=end_date,
            symbol=symbol,
            timeframe=timeframe,
            config=config,
            settings=ReplaySettings(
                starting_balance=starting_balance,
                risk_percent=risk_percent,
                reward_risk_ratio=reward_risk_ratio,
                max_open_trades=max_open_trades,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/training/run")
def run_training(request: TrainingRequest) -> dict[str, object]:
    history = history_store.load(request.symbol, request.timeframe)
    point = history_store.point(request.symbol, request.timeframe)
    if not history or point is None:
        raise HTTPException(status_code=409, detail="No MT5 history synced yet.")
    base_config = StrategyConfig() if request.base_profile == "MODEL_BASELINE" else config_store.load()
    try:
        return train_thresholds(
            history=history,
            point=point,
            request=request,
            base_config=base_config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/train", response_class=HTMLResponse)
def training_page() -> str:
    return training_page_html()


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
    return inject_forex_factory_control(control_page_html())