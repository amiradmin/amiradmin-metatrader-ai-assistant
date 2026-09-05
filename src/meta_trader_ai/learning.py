from __future__ import annotations

from collections import defaultdict

from .journal import DecisionJournal
from .models import FactorName, LearningRecommendation, StrategyConfig, TradeOutcome


def recommend_thresholds(config: StrategyConfig, outcomes: list[TradeOutcome], journal: DecisionJournal, min_samples: int = 30) -> LearningRecommendation:
    if len(outcomes) < min_samples:
        return LearningRecommendation(sample_size=len(outcomes), status="INSUFFICIENT_DATA", current_expectancy_r=(sum(t.r_multiple for t in outcomes) / len(outcomes)) if outcomes else 0.0, proposed_thresholds={}, reasons=[f"Need at least {min_samples} closed trades before proposing threshold changes."])

    current_expectancy = sum(t.r_multiple for t in outcomes[-50:]) / min(50, len(outcomes))
    proposed: dict[str, float] = {}
    reasons: list[str] = []
    buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for outcome in outcomes[-120:]:
        decision = journal.find(outcome.signal_id)
        if not decision:
            continue
        for factor in decision.get("factors", []):
            name = factor.get("name")
            score = factor.get("candidate_score")
            if name is not None and score is not None:
                buckets[str(name)].append((float(score), outcome.r_multiple))

    for factor_name in FactorName:
        rows = buckets.get(factor_name.value, [])
        if len(rows) < 20:
            continue
        current = config.factor(factor_name).min_score
        above = [r for s, r in rows if s >= current]
        near_below = [r for s, r in rows if current - 10 <= s < current]
        if len(above) >= 10 and len(near_below) >= 6:
            e_above = sum(above) / len(above)
            e_below = sum(near_below) / len(near_below)
            if e_below < e_above - 0.20 and current <= 90:
                proposed[factor_name.value] = min(95.0, current + 5.0)
                reasons.append(f"{factor_name.value}: near-below-threshold expectancy {e_below:+.2f}R vs pass-zone {e_above:+.2f}R; candidate +5.")
            elif e_below > e_above + 0.20 and current >= 10:
                proposed[factor_name.value] = max(5.0, current - 5.0)
                reasons.append(f"{factor_name.value}: near-below-threshold expectancy {e_below:+.2f}R beats pass-zone {e_above:+.2f}R; candidate -5.")

    return LearningRecommendation(sample_size=len(outcomes), status="CANDIDATE_AVAILABLE" if proposed else "NO_CHANGE", current_expectancy_r=current_expectancy, proposed_thresholds=proposed, reasons=reasons or ["No threshold change has enough forward evidence yet."])


def model_recommended_config(
    outcomes: list[TradeOutcome],
    journal: DecisionJournal,
    *,
    min_samples: int = 30,
) -> tuple[StrategyConfig, LearningRecommendation, str]:
    """Return a stable one-click profile independent from manual slider edits.

    The canonical baseline is the StrategyConfig default profile. Once enough
    closed forward trades exist, only data-supported factor threshold changes
    are overlaid on that baseline. Risk settings are deliberately not changed
    here; the recommendation button is for signal quality, not risk escalation.
    """

    recommended = StrategyConfig()
    learning = recommend_thresholds(recommended, outcomes, journal, min_samples=min_samples)

    source = "MODEL_BASELINE"
    if learning.status == "CANDIDATE_AVAILABLE":
        for name, value in learning.proposed_thresholds.items():
            if name in {factor.value for factor in FactorName}:
                getattr(recommended, name).min_score = value
        source = "LEARNED_OVERLAY"

    return recommended, learning, source
