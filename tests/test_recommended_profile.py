from __future__ import annotations

from meta_trader_ai.journal import DecisionJournal
from meta_trader_ai.learning import model_recommended_config
from meta_trader_ai.models import FactorName, StrategyConfig, TradeOutcome


def test_recommended_profile_uses_canonical_baseline_without_samples(tmp_path) -> None:
    journal = DecisionJournal(path=tmp_path / "decisions.jsonl")
    config, learning, source = model_recommended_config([], journal)

    assert source == "MODEL_BASELINE"
    assert learning.status == "INSUFFICIENT_DATA"
    assert config == StrategyConfig()
    assert config.dynamic_levels.min_score == 60
    assert config.static_levels.min_score == 50
    assert config.fibonacci.min_score == 45
    assert config.patterns.min_score == 45
    assert config.pivots.min_score == 40
    assert config.divergence.min_score == 40
    assert config.decision.min_pass_count == 3
    assert config.decision.min_total_score == 50
    assert config.decision.min_side_edge == 9


def test_recommended_profile_overlays_supported_learning_changes(tmp_path) -> None:
    journal = DecisionJournal(path=tmp_path / "decisions.jsonl")
    baseline = StrategyConfig()
    outcomes: list[TradeOutcome] = []

    for i in range(30):
        signal_id = f"sig-{i}"
        winner = i < 20
        factors = []
        for factor_name in FactorName:
            current = baseline.factor(factor_name).min_score
            factors.append(
                {
                    "name": factor_name.value,
                    "candidate_score": current + 5 if winner else current - 5,
                }
            )
        journal.append({"signal_id": signal_id, "factors": factors})
        outcomes.append(
            TradeOutcome(
                signal_id=signal_id,
                symbol="XAUUSD_o",
                side="BUY",
                pnl_money=5.0 if winner else -5.0,
                r_multiple=1.0 if winner else -1.0,
            )
        )

    config, learning, source = model_recommended_config(outcomes, journal)

    assert source == "LEARNED_OVERLAY"
    assert learning.status == "CANDIDATE_AVAILABLE"
    assert learning.sample_size == 30
    for factor_name in FactorName:
        assert config.factor(factor_name).min_score == baseline.factor(factor_name).min_score + 5

    # Decision gates stay on the canonical baseline; learning cannot loosen risk controls.
    assert config.decision == baseline.decision
    assert config.safety == baseline.safety
