"""RL training pipeline API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import settings
from app_state import simulation_engine
from services.rl_decision_engine import get_rl_engine
from services.rl_metrics import get_rl_metrics
from services.rl_batch_trainer import RLBatchTrainer

rl_router = APIRouter(prefix="/api/rl", tags=["rl"])


# ── Request models ───────────────────────────────────────────────────

class TrainBatchRequest(BaseModel):
    epochs: int = 100


# ── Routes ───────────────────────────────────────────────────────────

@rl_router.get("/stats")
def rl_stats() -> dict[str, Any]:
    """Current RL training summary."""
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    engine = get_rl_engine()
    metrics = get_rl_metrics()
    summary = engine.get_training_summary()
    metrics_summary = metrics.get_summary()
    return {
        **summary,
        **metrics_summary,
        "rl_decisions_count": simulation_engine.rl_decisions_count,
        "rule_decisions_count": simulation_engine.rule_decisions_count,
        "rl_override_successes": simulation_engine.rl_override_successes,
    }


@rl_router.get("/training-history")
def rl_training_history(
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    """Loss curve, reward curve, epsilon curve from persistent log."""
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    metrics = get_rl_metrics()
    history = metrics.get_training_history(limit=limit)
    reward_trend = metrics.get_reward_trend(window=50)
    return {
        "training_steps": history,
        "reward_trend": reward_trend[-limit:] if reward_trend else [],
        "total_steps": len(history),
    }


@rl_router.get("/episodes")
def rl_episodes(
    limit: int = Query(default=100, ge=1, le=2000),
) -> dict[str, Any]:
    """Recent episode records."""
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    metrics = get_rl_metrics()
    episodes = metrics.get_episodes(limit=limit)
    return {
        "episodes": episodes,
        "total": len(episodes),
    }


@rl_router.get("/q-values")
def rl_q_values(
    sample_count: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """Q-value snapshot for sample states from replay buffer."""
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    engine = get_rl_engine()
    return engine.get_q_value_snapshot(sample_count=sample_count)


@rl_router.post("/train-batch")
def rl_train_batch(body: TrainBatchRequest) -> dict[str, Any]:
    """Trigger batch training over the replay buffer."""
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    trainer = RLBatchTrainer()
    return trainer.train_batch(epochs=body.epochs)


@rl_router.post("/reset")
def rl_reset() -> dict[str, str]:
    """Reset the RL agent: clear metrics and reinitialise weights."""
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    engine = get_rl_engine()
    metrics = get_rl_metrics()
    # Clear persistent metrics
    metrics.clear()
    # Reset engine state
    engine.replay_buffer.buffer.clear()
    engine.replay_buffer.position = 0
    engine.epsilon = 1.0
    engine.train_step = 0
    engine.q_network.apply(_reset_weights)
    engine.target_network.load_state_dict(engine.q_network.state_dict())
    engine.save_weights()
    # Reset simulation counters
    simulation_engine.rl_decisions_count = 0
    simulation_engine.rule_decisions_count = 0
    simulation_engine.rl_override_successes = 0
    return {"status": "reset_complete"}


@rl_router.get("/action-distribution")
def rl_action_distribution(
    last_n: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    """Action frequency breakdown from recent episodes."""
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    metrics = get_rl_metrics()
    distribution = metrics.get_action_distribution(last_n=last_n)
    total = sum(distribution.values())
    pct = {k: round(v / max(total, 1) * 100, 2) for k, v in distribution.items()}
    return {
        "counts": distribution,
        "percentages": pct,
        "total": total,
        "window": last_n,
    }


@rl_router.get("/comparison")
def rl_comparison() -> dict[str, Any]:
    """AI vs baseline comparison stats from the simulation engine."""
    if not settings.use_rl_engine:
        raise HTTPException(status_code=503, detail="RL engine is disabled")
    engine = get_rl_engine()
    metrics_store = get_rl_metrics()
    sim = simulation_engine
    current = sim.current_metrics

    total_decisions = sim.rl_decisions_count + sim.rule_decisions_count
    rl_pct = round(sim.rl_decisions_count / max(total_decisions, 1) * 100, 2)

    # Compute avg reward for RL-decided episodes vs all
    episodes = metrics_store.get_episodes(limit=500)
    rl_episodes_list = [e for e in episodes if e["chosen_by"] in ("exploration", "exploitation")]
    avg_rl_reward = (
        round(sum(e["reward"] for e in rl_episodes_list) / len(rl_episodes_list), 4)
        if rl_episodes_list else 0.0
    )
    sla_known = [e for e in rl_episodes_list if e.get("sla_met") is not None]
    rl_sla_rate = (
        round(sum(1 for e in sla_known if e["sla_met"]) / max(len(sla_known), 1) * 100, 2)
        if sla_known else 0.0
    )

    return {
        "total_decisions": total_decisions,
        "rl_decisions": sim.rl_decisions_count,
        "rule_decisions": sim.rule_decisions_count,
        "rl_decision_pct": rl_pct,
        "rl_override_successes": sim.rl_override_successes,
        "completed_trips": sim.completed_trips,
        "on_time_trips": sim.on_time_trips,
        "on_time_delivery_pct": current.on_time_delivery_pct,
        "co2_saved_kg": round(current.co2_saved_kg, 2),
        "stockouts_prevented": current.stockouts_prevented,
        "avg_rl_episode_reward": avg_rl_reward,
        "rl_sla_success_rate_pct": rl_sla_rate,
        "rl_episodes_recorded": len(rl_episodes_list),
        "epsilon": round(engine.epsilon, 4),
        "train_step": engine.train_step,
        "buffer_size": len(engine.replay_buffer),
    }


# ── Helpers ──────────────────────────────────────────────────────────

def _reset_weights(module: Any) -> None:
    """Reset linear layer weights for a fresh start."""
    import torch.nn as nn
    if isinstance(module, nn.Linear):
        module.reset_parameters()
