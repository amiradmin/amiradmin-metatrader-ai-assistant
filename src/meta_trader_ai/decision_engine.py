from __future__ import annotations

from datetime import datetime, timezone

from .analyzers import RawFactorScore, analyze_all
from .models import Decision, DecisionResponse, FactorScore, MarketSnapshot, PerformanceSummary, SafetyGate, StrategyConfig


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
    return gates


def build_decision(snapshot: MarketSnapshot, config: StrategyConfig, performance: PerformanceSummary | None = None) -> DecisionResponse:
    raw = analyze_all(snapshot)
    buy_score = _weighted_side_score(raw, config, Decision.BUY)
    sell_score = _weighted_side_score(raw, config, Decision.SELL)
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
        blockers.extend(g.reason for g in safety if not g.passed)
        if blockers:
            decision = Decision.WAIT

    newest_bar_time = max(b.time for b in snapshot.bars)
    signal_id = f"{snapshot.symbol}_{snapshot.timeframe}_{newest_bar_time}_{candidate.value}"
    trade_allowed = decision in (Decision.BUY, Decision.SELL) and all(g.passed for g in safety)
    return DecisionResponse(
        signal_id=signal_id,
        generated_at=datetime.now(timezone.utc),
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        candidate=candidate,
        decision=decision,
        trade_allowed=trade_allowed,
        buy_score=round(buy_score, 2),
        sell_score=round(sell_score, 2),
        side_edge=round(side_edge, 2),
        passed_count=passed_count,
        min_pass_count=config.decision.min_pass_count,
        max_open_trades=config.safety.max_open_trades,
        blockers=blockers,
        primary_blocker=blockers[0] if blockers else None,
        factors=factors,
        safety=safety,
        performance=performance or PerformanceSummary(),
    )
