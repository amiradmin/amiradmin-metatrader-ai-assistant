from meta_trader_ai.decision_engine import build_decision
from meta_trader_ai.models import Bar, DailyContext, MarketSnapshot, StrategyConfig


def snapshot(up: bool = True) -> MarketSnapshot:
    bars = []
    price = 2000.0
    for i in range(120):
        step = 0.8 if up else -0.8
        o = price
        c = price + step + (0.15 if i % 5 else -0.1)
        h = max(o, c) + 0.5
        l = min(o, c) - 0.5
        bars.append(Bar(time=1_700_000_000 + i * 900, open=o, high=h, low=l, close=c))
        price = c
    return MarketSnapshot(symbol="XAUUSD_o", timeframe="M15", bid=price - 0.1, ask=price + 0.1, point=0.01, spread_points=20, bars=bars, previous_day=DailyContext(high=2020, low=1980, close=2005), news_risk="LOW", account_mode="DEMO")


def test_decision_is_explainable() -> None:
    response = build_decision(snapshot(), StrategyConfig())
    assert len(response.factors) == 6
    assert {f.name.value for f in response.factors} == {"dynamic_levels", "static_levels", "fibonacci", "patterns", "pivots", "divergence"}
    assert response.buy_score >= 0
    assert response.sell_score >= 0
    assert len(response.safety) >= 4
    regime_gate = next(g for g in response.safety if g.name == "market_regime")
    assert regime_gate.passed is True
    assert "disabled" in regime_gate.reason


def test_decision_exposes_bridge_live_risk_and_reward_ratio() -> None:
    config = StrategyConfig()
    config.safety.risk_percent = 0.35
    config.safety.reward_risk_ratio = 2.5
    response = build_decision(snapshot(), config)

    assert response.risk_percent == 0.35
    assert response.reward_risk_ratio == 2.5


def test_edge_gate_keeps_leading_candidate_explainable() -> None:
    config = StrategyConfig()
    config.decision.min_side_edge = 100.0
    response = build_decision(snapshot(), config)

    assert response.decision.value == "WAIT"
    assert response.candidate.value in {"BUY", "SELL"}
    assert response.candidate.value != "WAIT"
    assert response.primary_blocker is not None
    assert response.primary_blocker.startswith("side edge")

    for factor in response.factors:
        expected = factor.buy_score if response.candidate.value == "BUY" else factor.sell_score
        assert factor.candidate_score == expected
        assert factor.passed == (factor.candidate_score >= factor.min_score)


def test_real_account_is_blocked_by_default() -> None:
    s = snapshot()
    s.account_mode = "REAL"
    response = build_decision(s, StrategyConfig())
    assert response.trade_allowed is False
    assert any("account_mode" in blocker for blocker in response.blockers) or response.candidate.value == "WAIT"


def test_market_regime_filter_can_block_entry() -> None:
    config = StrategyConfig()
    config.dynamic_levels.required = False
    config.static_levels.required = False
    config.decision.min_pass_count = 1
    config.decision.min_total_score = 0
    config.decision.min_side_edge = 0
    config.safety.regime_filter_enabled = True
    config.safety.regime_min_trend_atr = 0.0
    config.safety.regime_min_atr_ratio = 5.0

    response = build_decision(snapshot(), config)
    regime_gate = next(g for g in response.safety if g.name == "market_regime")

    assert regime_gate.passed is False
    assert response.trade_allowed is False
    assert any("ATR ratio=" in blocker for blocker in response.blockers)
