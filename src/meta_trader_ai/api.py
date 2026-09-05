from __future__ import annotations

from fastapi import FastAPI

from .config_store import StrategyConfigStore
from .decision_engine import build_decision
from .journal import DecisionJournal
from .learning import recommend_thresholds
from .models import DecisionResponse, LearningRecommendation, MarketSnapshot, PerformanceSummary, StrategyConfig, TradeOutcome
from .performance import PerformanceStore

app = FastAPI(title="MetaTrader AI Assistant v2", version="0.1.0")
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
