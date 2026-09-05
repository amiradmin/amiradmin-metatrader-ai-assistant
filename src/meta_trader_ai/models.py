from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Decision(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class FactorName(str, Enum):
    DYNAMIC = "dynamic_levels"
    STATIC = "static_levels"
    FIBONACCI = "fibonacci"
    PATTERNS = "patterns"
    PIVOTS = "pivots"
    DIVERGENCE = "divergence"


class FactorConfig(BaseModel):
    min_score: float = Field(60.0, ge=0, le=100)
    weight: float = Field(1.0, gt=0, le=10)
    required: bool = False


class DecisionRuleConfig(BaseModel):
    min_pass_count: int = Field(4, ge=1, le=6)
    min_total_score: float = Field(68.0, ge=0, le=100)
    min_side_edge: float = Field(12.0, ge=0, le=100)


class SafetyConfig(BaseModel):
    max_spread_points: int = Field(60, ge=0)
    block_high_news: bool = True
    block_unknown_news: bool = False
    demo_only: bool = True


class StrategyConfig(BaseModel):
    dynamic_levels: FactorConfig = FactorConfig(min_score=60, weight=1.0, required=True)
    static_levels: FactorConfig = FactorConfig(min_score=65, weight=1.2, required=True)
    fibonacci: FactorConfig = FactorConfig(min_score=55, weight=0.8, required=False)
    patterns: FactorConfig = FactorConfig(min_score=60, weight=1.0, required=False)
    pivots: FactorConfig = FactorConfig(min_score=55, weight=0.8, required=False)
    divergence: FactorConfig = FactorConfig(min_score=60, weight=1.0, required=False)
    decision: DecisionRuleConfig = DecisionRuleConfig()
    safety: SafetyConfig = SafetyConfig()

    def factor(self, name: FactorName) -> FactorConfig:
        return getattr(self, name.value)


class Bar(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float

    @model_validator(mode="after")
    def validate_ohlc(self) -> "Bar":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high is below OHLC values")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low is above OHLC values")
        return self


class DailyContext(BaseModel):
    high: float
    low: float
    close: float


class MarketSnapshot(BaseModel):
    symbol: str
    timeframe: str = "M15"
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    point: float = Field(gt=0)
    spread_points: int = Field(ge=0)
    bars: list[Bar] = Field(min_length=60)
    previous_day: DailyContext | None = None
    news_risk: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"] = "UNKNOWN"
    account_mode: Literal["DEMO", "REAL", "CONTEST", "UNKNOWN"] = "UNKNOWN"


class FactorScore(BaseModel):
    name: FactorName
    label: str
    buy_score: float = Field(ge=0, le=100)
    sell_score: float = Field(ge=0, le=100)
    min_score: float = Field(ge=0, le=100)
    weight: float = Field(gt=0)
    required: bool
    candidate_score: float = Field(ge=0, le=100)
    passed: bool
    reason: str


class SafetyGate(BaseModel):
    name: str
    passed: bool
    reason: str


class PerformanceSummary(BaseModel):
    trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy_r: float = 0.0
    max_drawdown_r: float = 0.0
    previous_expectancy_r: float | None = None
    trend: Literal["COLLECTING", "IMPROVING", "DEGRADING", "FLAT"] = "COLLECTING"


class DecisionResponse(BaseModel):
    signal_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str
    timeframe: str
    candidate: Decision
    decision: Decision
    trade_allowed: bool
    buy_score: float
    sell_score: float
    side_edge: float
    passed_count: int
    min_pass_count: int
    blockers: list[str]
    primary_blocker: str | None = None
    factors: list[FactorScore]
    safety: list[SafetyGate]
    performance: PerformanceSummary


class TradeOutcome(BaseModel):
    signal_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    pnl_money: float
    r_multiple: float
    closed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LearningRecommendation(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sample_size: int
    status: Literal["INSUFFICIENT_DATA", "NO_CHANGE", "CANDIDATE_AVAILABLE"]
    current_expectancy_r: float
    proposed_thresholds: dict[str, float]
    reasons: list[str]
