from __future__ import annotations

from datetime import datetime, timezone

from .analyzers import RawFactorScore, analyze_all, market_regime
from .models import (
    Decision,
    DecisionResponse,
    FactorScore,
    MarketSnapshot,
    PerformanceSummary,
    SafetyGate,
    SignalOverlay,
    StrategyConfig,
)
from .pdf_mode import evaluate_pdf_mode


def _weighted_side_score(raw: list[RawFactorScore], config: StrategyConfig, side: Decision) -> float:
    total = 0.0
    weight_sum = 0.0
    for item in raw:
        fc = config.factor(item.name)
        score = item.buy if side == Decision.BUY else item.sell
        total += score * fc.weight
        weight_sum += fc.weight
    return total / weight_sum if weight_sum else 0.0


def _candidate_from_scores(buy_score: float, sell_score: float) -> Decision:
    if buy_score > sell_score:
        return Decision.BUY
    if sell_score > buy_score:
        return Decision.SELL
    return Decision.WAIT


def _safety(snapshot: MarketSnapshot, config: StrategyConfig) -> list[SafetyGate]:
    spread_ok = config.safety.max_spread_points <= 0 or snapshot.spread_points <= config.safety.max_spread_points
    gates = [SafetyGate(name="spread", passed=spread_ok, reason=f"spread={snapshot.spread_points} points; limit={config.safety.max_spread_points}")]
    news_ok = not ((config.safety.block_high_news and snapshot.news_risk == "HIGH") or (config.safety.block_unknown_news and snapshot.news_risk == "UNKNOWN"))
    gates.append(SafetyGate(name="news", passed=news_ok, reason=f"news_risk={snapshot.news_risk}"))
    account_ok = not config.safety.demo_only or snapshot.account_mode == "DEMO"
    gates.append(SafetyGate(name="account_mode", passed=account_ok, reason=f"account_mode={snapshot.account_mode}; demo_only={config.safety.demo_only}"))
    gates.append(SafetyGate(name="market_data", passed=snapshot.ask > snapshot.bid > 0 and snapshot.point > 0, reason="bid/ask/point sanity check"))

    regime = market_regime(snapshot)
    if config.safety.regime_filter_enabled:
        regime_ok = (
            regime.trend_strength_atr >= config.safety.regime_min_trend_atr
            and regime.atr_ratio >= config.safety.regime_min_atr_ratio
        )
        regime_reason = (
            f"regime trend={regime.trend_strength_atr:.2f} ATR "
            f"(min {config.safety.regime_min_trend_atr:.2f}); "
            f"ATR ratio={regime.atr_ratio:.2f} "
            f"(min {config.safety.regime_min_atr_ratio:.2f})"
        )
    else:
        regime_ok = True
        regime_reason = (
            f"regime filter disabled; trend={regime.trend_strength_atr:.2f} ATR; "
            f"ATR ratio={regime.atr_ratio:.2f}"
        )
    gates.append(SafetyGate(name="market_regime", passed=regime_ok, reason=regime_reason))
    return gates


def _apply_overlays(
    base_buy: float,
    base_sell: float,
    overlays: list[SignalOverlay],
) -> tuple[float, float, float, float]:
    """Apply bounded live modifiers without allowing overlays to dominate factors."""

    buy_modifier = sum(item.buy_modifier for item in overlays if item.available)
    sell_modifier = sum(item.sell_modifier for item in overlays if item.available)
    buy_modifier = max(-10.0, min(10.0, buy_modifier))
    sell_modifier = max(-10.0, min(10.0, sell_modifier))
    buy_score = max(0.0, min(100.0, base_buy + buy_modifier))
    sell_score = max(0.0, min(100.0, base_sell + sell_modifier))
    return buy_score, sell_score, buy_modifier, sell_modifier


def build_decision(
    snapshot: MarketSnapshot,
    config: StrategyConfig,
    performance: PerformanceSummary | None = None,
    overlays: list[SignalOverlay] | None = None,
) -> DecisionResponse:
    raw = analyze_all(snapshot)
    base_buy_score = _weighted_side_score(raw, config, Decision.BUY)
    base_sell_score = _weighted_side_score(raw, config, Decision.SELL)
    active_overlays = overlays or []
    buy_score, sell_score, overlay_buy, overlay_sell = _apply_overlays(
        base_buy_score,
        base_sell_score,
        active_overlays,
    )
    candidate = _candidate_from_scores(buy_score, sell_score)
    factors: list[FactorScore] = []
    passed_count = 0
    required_failed: list[str] = []

    for item in raw:
        fc = config.factor(item.name)
        if candidate == Decision.BUY:
            score, reason = item.buy, item.buy_reason
        elif candidate == Decision.SELL:
            score, reason = item.sell, item.sell_reason
        else:
            score, reason = max(item.buy, item.sell), "buy/sell scores are tied"
        passed = candidate != Decision.WAIT and score >= fc.min_score
        if passed:
            passed_count += 1
        if fc.required and not passed:
            required_failed.append(item.label)
        factors.append(FactorScore(
            name=item.name,
            label=item.label,
            buy_score=round(item.buy, 2),
            sell_score=round(item.sell, 2),
            min_score=fc.min_score,
            weight=fc.weight,
            required=fc.required,
            candidate_score=round(score, 2),
            passed=passed,
            reason=reason,
        ))

    safety = _safety(snapshot, config)
    blockers: list[str] = []
    decision = candidate
    side_edge = abs(buy_score - sell_score)

    pdf_evaluation = evaluate_pdf_mode(snapshot, candidate) if config.strategy_mode == "PDF" else None

    if candidate == Decision.WAIT:
        blockers.append("buy/sell scores are tied; no directional candidate")
    else:
        if side_edge < config.decision.min_side_edge:
            blockers.append(f"side edge {side_edge:.1f} < {config.decision.min_side_edge:.1f}")
        side_score = buy_score if candidate == Decision.BUY else sell_score
        if side_score < config.decision.min_total_score:
            blockers.append(f"total score {side_score:.1f} < {config.decision.min_total_score:.1f}")
        if passed_count < config.decision.min_pass_count:
            blockers.append(f"passed {passed_count}/6 < required {config.decision.min_pass_count}/6")
        blockers.extend(f"required factor failed: {label}" for label in required_failed)
        if pdf_evaluation is not None and not pdf_evaluation.allowed and pdf_evaluation.reason:
            blockers.append(pdf_evaluation.reason)
        blockers.extend(g.reason for g in safety if not g.passed)
        if blockers:
            decision = Decision.WAIT

    newest_bar_time = max(b.time for b in snapshot.bars)
    signal_id = (
        f"{snapshot.symbol}_{snapshot.timeframe}_{newest_bar_time}_"
        f"{candidate.value}_{config.strategy_mode}"
    )
    trade_allowed = decision in (Decision.BUY, Decision.SELL) and all(g.passed for g in safety)

    if pdf_evaluation is None:
        pdf_status = "DISABLED"
        pdf_regime = "UNAVAILABLE"
        pdf_range_zone = "UNAVAILABLE"
        pdf_breakout_status = "UNAVAILABLE"
        pdf_lower_touch_count = 0
        pdf_upper_touch_count = 0
    else:
        pdf_status = pdf_evaluation.status
        pdf_regime = pdf_evaluation.regime.value
        pdf_range_zone = pdf_evaluation.range_zone.value
        pdf_breakout_status = pdf_evaluation.breakout.value
        pdf_lower_touch_count = pdf_evaluation.lower_touch_count
        pdf_upper_touch_count = pdf_evaluation.upper_touch_count

    return DecisionResponse(
        signal_id=signal_id,
        generated_at=datetime.now(timezone.utc),
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        candidate=candidate,
        decision=decision,
        trade_allowed=trade_allowed,
        strategy_mode=config.strategy_mode,
        pdf_status=pdf_status,
        pdf_regime=pdf_regime,
        pdf_range_zone=pdf_range_zone,
        pdf_breakout_status=pdf_breakout_status,
        pdf_lower_touch_count=pdf_lower_touch_count,
        pdf_upper_touch_count=pdf_upper_touch_count,
        buy_score=round(buy_score, 2),
        sell_score=round(sell_score, 2),
        side_edge=round(side_edge, 2),
        passed_count=passed_count,
        min_pass_count=config.decision.min_pass_count,
        max_open_trades=config.safety.max_open_trades,
        risk_percent=config.safety.risk_percent,
        reward_risk_ratio=config.safety.reward_risk_ratio,
        base_buy_score=round(base_buy_score, 2),
        base_sell_score=round(base_sell_score, 2),
        overlay_buy_modifier=round(overlay_buy, 2),
        overlay_sell_modifier=round(overlay_sell, 2),
        overlays=active_overlays,
        blockers=blockers,
        primary_blocker=blockers[0] if blockers else None,
        factors=factors,
        safety=safety,
        performance=performance or PerformanceSummary(),
    )
