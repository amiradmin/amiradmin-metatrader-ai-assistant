from __future__ import annotations

from math import sqrt
from random import Random
from statistics import pstdev
from typing import Literal

from pydantic import BaseModel, Field

from .backtest_date import ReplaySettings, run_date_backtest
from .models import FactorName, HistoryBar, StrategyConfig


class TrainingRequest(BaseModel):
    symbol: str = "XAUUSD_o"
    timeframe: str = "M15"
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    starting_balance: float = Field(1000.0, gt=0, le=100_000_000)
    risk_percent: float = Field(0.5, gt=0, le=5.0)
    reward_risk_ratio: float = Field(2.0, ge=0.5, le=10.0)
    iterations: int = Field(24, ge=8, le=80)
    base_profile: Literal["MODEL_BASELINE", "CURRENT"] = "MODEL_BASELINE"
    target_daily_pnl: float = Field(10.0, ge=0, le=100_000)
    seed: int = 260905


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _range_metrics(
    *,
    history: list[HistoryBar],
    point: float,
    dates: list[str],
    symbol: str,
    timeframe: str,
    config: StrategyConfig,
    starting_balance: float,
    risk_percent: float,
    reward_risk_ratio: float,
) -> dict[str, float | int]:
    balance = starting_balance
    all_r: list[float] = []
    daily_r: list[float] = []
    daily_pnl: list[float] = []
    wins = 0
    losses = 0
    signals = 0
    buy_trades = 0
    sell_trades = 0

    for selected_date in dates:
        summary = run_date_backtest(
            history=history,
            point=point,
            selected_date=selected_date,
            symbol=symbol,
            timeframe=timeframe,
            config=config,
            settings=ReplaySettings(
                starting_balance=balance,
                risk_percent=risk_percent,
                reward_risk_ratio=reward_risk_ratio,
            ),
        )
        balance = summary.ending_balance
        wins += summary.wins
        losses += summary.losses
        signals += summary.signals
        buy_trades += summary.buy_trades
        sell_trades += summary.sell_trades
        daily_r.append(summary.net_r)
        daily_pnl.append(summary.estimated_pnl_money)
        all_r.extend(trade.r_multiple for trade in summary.trades_detail)

    cumulative = 0.0
    peak = 0.0
    max_drawdown_r = 0.0
    for value in all_r:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown_r = max(max_drawdown_r, peak - cumulative)

    trades = len(all_r)
    net_r = sum(all_r)
    expectancy_r = net_r / trades if trades else 0.0
    trading_days = len(dates)
    profitable_days = sum(1 for value in daily_pnl if value > 0)
    avg_daily_pnl = (balance - starting_balance) / trading_days if trading_days else 0.0
    avg_daily_r = sum(daily_r) / trading_days if trading_days else 0.0
    daily_r_std = pstdev(daily_r) if len(daily_r) > 1 else 0.0
    win_rate = wins / trades * 100.0 if trades else 0.0
    profitable_days_percent = profitable_days / trading_days * 100.0 if trading_days else 0.0

    # Training objective deliberately uses R-based quality and drawdown rather
    # than dollar profit, so the optimizer cannot "win" merely by raising risk.
    # Sparse strategies are penalized because a one-trade lucky sample is not
    # enough evidence to promote a threshold profile.
    sample_target = max(8, trading_days // 2)
    sample_factor = min(1.0, trades / sample_target) if sample_target else 0.0
    if trades == 0:
        objective = -9.0
    else:
        quality = 0.65 * expectancy_r + 0.35 * avg_daily_r
        stability_penalty = 0.06 * max_drawdown_r + 0.08 * daily_r_std
        breadth_bonus = 0.05 * (profitable_days_percent / 100.0)
        scarcity_penalty = (1.0 - sample_factor) * 0.50
        objective = quality - stability_penalty + breadth_bonus - scarcity_penalty

    return {
        "trading_days": trading_days,
        "trades": trades,
        "signals": signals,
        "buy_trades": buy_trades,
        "sell_trades": sell_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
        "net_r": round(net_r, 4),
        "expectancy_r": round(expectancy_r, 4),
        "avg_daily_r": round(avg_daily_r, 4),
        "max_drawdown_r": round(max_drawdown_r, 4),
        "daily_r_std": round(daily_r_std, 4),
        "profitable_days": profitable_days,
        "profitable_days_percent": round(profitable_days_percent, 2),
        "starting_balance": round(starting_balance, 2),
        "ending_balance": round(balance, 2),
        "total_pnl": round(balance - starting_balance, 2),
        "avg_daily_pnl": round(avg_daily_pnl, 2),
        "objective": round(objective, 6),
    }


def _candidate(base: StrategyConfig, rng: Random, index: int) -> StrategyConfig:
    candidate = base.model_copy(deep=True)
    if index == 0:
        return candidate

    factor_bounds = {
        FactorName.DYNAMIC: (40.0, 75.0),
        FactorName.STATIC: (35.0, 70.0),
        FactorName.FIBONACCI: (25.0, 70.0),
        FactorName.PATTERNS: (25.0, 70.0),
        FactorName.PIVOTS: (25.0, 65.0),
        FactorName.DIVERGENCE: (25.0, 70.0),
    }
    offsets = (-15.0, -10.0, -5.0, 0.0, 0.0, 5.0, 10.0, 15.0)
    for factor_name in FactorName:
        low, high = factor_bounds[factor_name]
        current = base.factor(factor_name).min_score
        candidate.factor(factor_name).min_score = _clamp(current + rng.choice(offsets), low, high)

    candidate.decision.min_pass_count = rng.choice((2, 3, 3, 3, 4))
    candidate.decision.min_total_score = _clamp(
        base.decision.min_total_score + rng.choice((-10.0, -5.0, 0.0, 0.0, 5.0, 10.0)),
        38.0,
        65.0,
    )
    candidate.decision.min_side_edge = _clamp(
        base.decision.min_side_edge + rng.choice((-4.0, -2.0, 0.0, 0.0, 2.0, 4.0)),
        5.0,
        16.0,
    )
    return candidate


def _config_summary(config: StrategyConfig) -> dict[str, float | int | bool]:
    return {
        **{factor.value: config.factor(factor).min_score for factor in FactorName},
        "min_pass_count": config.decision.min_pass_count,
        "min_total_score": config.decision.min_total_score,
        "min_side_edge": config.decision.min_side_edge,
    }


def train_thresholds(
    *,
    history: list[HistoryBar],
    point: float,
    request: TrainingRequest,
    base_config: StrategyConfig,
) -> dict[str, object]:
    if request.start_date > request.end_date:
        raise ValueError("start_date must be <= end_date")

    dates = sorted(
        {
            bar.broker_date
            for bar in history
            if request.start_date <= bar.broker_date <= request.end_date
        }
    )
    if len(dates) < 15:
        raise ValueError("Training needs at least 15 synced trading days so train/validation/holdout are meaningful.")

    # Chronological 60/20/20 split. The holdout segment is never used to choose
    # thresholds; it is only opened after the candidate has been selected.
    train_end = max(1, int(len(dates) * 0.60))
    validation_end = max(train_end + 1, int(len(dates) * 0.80))
    validation_end = min(validation_end, len(dates) - 1)
    train_dates = dates[:train_end]
    validation_dates = dates[train_end:validation_end]
    holdout_dates = dates[validation_end:]
    if not validation_dates or not holdout_dates:
        raise ValueError("Not enough dates for chronological train/validation/holdout split.")

    kwargs = {
        "history": history,
        "point": point,
        "symbol": request.symbol,
        "timeframe": request.timeframe,
        "starting_balance": request.starting_balance,
        "risk_percent": request.risk_percent,
        "reward_risk_ratio": request.reward_risk_ratio,
    }

    baseline_train = _range_metrics(dates=train_dates, config=base_config, **kwargs)
    baseline_validation = _range_metrics(dates=validation_dates, config=base_config, **kwargs)
    baseline_holdout = _range_metrics(dates=holdout_dates, config=base_config, **kwargs)

    rng = Random(request.seed)
    train_ranked: list[tuple[float, int, StrategyConfig, dict[str, float | int]]] = []
    seen: set[tuple[object, ...]] = set()

    for index in range(request.iterations):
        config = _candidate(base_config, rng, index)
        key = tuple(_config_summary(config).values())
        if key in seen:
            continue
        seen.add(key)
        metrics = _range_metrics(dates=train_dates, config=config, **kwargs)
        train_ranked.append((float(metrics["objective"]), index, config, metrics))

    if not train_ranked:
        raise ValueError("No candidate configurations were generated.")
    train_ranked.sort(key=lambda row: row[0], reverse=True)

    finalists: list[dict[str, object]] = []
    for train_score, index, config, train_metrics in train_ranked[: min(6, len(train_ranked))]:
        validation_metrics = _range_metrics(dates=validation_dates, config=config, **kwargs)
        finalists.append(
            {
                "index": index,
                "config": config,
                "train": train_metrics,
                "validation": validation_metrics,
                "selection_score": float(validation_metrics["objective"]),
                "train_score": train_score,
            }
        )

    finalists.sort(key=lambda row: float(row["selection_score"]), reverse=True)
    winner = finalists[0]
    winner_config = winner["config"]
    assert isinstance(winner_config, StrategyConfig)
    holdout_metrics = _range_metrics(dates=holdout_dates, config=winner_config, **kwargs)

    baseline_holdout_objective = float(baseline_holdout["objective"])
    holdout_objective = float(holdout_metrics["objective"])
    holdout_trades = int(holdout_metrics["trades"])
    holdout_expectancy = float(holdout_metrics["expectancy_r"])
    min_holdout_trades = max(3, len(holdout_dates) // 3)
    promising = (
        holdout_trades >= min_holdout_trades
        and holdout_expectancy > 0
        and holdout_objective > baseline_holdout_objective
    )

    top_candidates: list[dict[str, object]] = []
    for row in finalists[:5]:
        cfg = row["config"]
        assert isinstance(cfg, StrategyConfig)
        top_candidates.append(
            {
                "index": row["index"],
                "config": _config_summary(cfg),
                "train": row["train"],
                "validation": row["validation"],
            }
        )

    return {
        "status": "PROMISING" if promising else "NEEDS_MORE_WORK",
        "method": "chronological walk-forward threshold search",
        "warning": "Historical optimization can overfit. A candidate must still prove itself in DEMO/forward trading before real-money use.",
        "target_daily_pnl": request.target_daily_pnl,
        "base_profile": request.base_profile,
        "iterations_requested": request.iterations,
        "candidates_evaluated": len(train_ranked),
        "split": {
            "all_days": len(dates),
            "train_days": len(train_dates),
            "validation_days": len(validation_dates),
            "holdout_days": len(holdout_dates),
            "train": [train_dates[0], train_dates[-1]],
            "validation": [validation_dates[0], validation_dates[-1]],
            "holdout": [holdout_dates[0], holdout_dates[-1]],
        },
        "baseline": {
            "config": _config_summary(base_config),
            "train": baseline_train,
            "validation": baseline_validation,
            "holdout": baseline_holdout,
        },
        "candidate": {
            "config": winner_config.model_dump(mode="json"),
            "summary": _config_summary(winner_config),
            "train": winner["train"],
            "validation": winner["validation"],
            "holdout": holdout_metrics,
            "holdout_avg_daily_gap_to_target": round(float(holdout_metrics["avg_daily_pnl"]) - request.target_daily_pnl, 2),
        },
        "top_candidates": top_candidates,
        "promotion_allowed": promising,
        "promotion_reason": (
            "Holdout beat the baseline with positive expectancy and enough trades. Promote only to DEMO/forward testing."
            if promising
            else "Candidate did not clear the holdout promotion gates; keep the current stable baseline."
        ),
    }
