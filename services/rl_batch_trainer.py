"""Batch training service for the RL decision engine.

Runs multiple training epochs over the accumulated replay buffer and
records each step into the persistent metrics store.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import torch

from services.rl_decision_engine import get_rl_engine
from services.rl_metrics import get_rl_metrics

logger = logging.getLogger(__name__)


class RLBatchTrainer:
    """Runs N training epochs over the replay buffer in a single batch."""

    def train_batch(self, epochs: int = 100) -> dict[str, Any]:
        """Run *epochs* training iterations over the replay buffer.

        Returns a summary dict with loss/epsilon curves and final stats.
        """
        engine = get_rl_engine()
        metrics = get_rl_metrics()

        if len(engine.replay_buffer) < engine.batch_size:
            return {
                "status": "insufficient_data",
                "buffer_size": len(engine.replay_buffer),
                "epochs_completed": 0,
            }

        loss_curve: list[float] = []
        epsilon_curve: list[float] = []
        epochs_completed = 0

        for _ in range(epochs):
            result = engine.train_step_update()
            if result is None:
                break
            epochs_completed += 1
            loss_curve.append(result["loss"])
            epsilon_curve.append(result["epsilon"])

            # Compute running reward average from recent episodes
            recent_episodes = metrics.get_episodes(limit=50)
            if recent_episodes:
                avg_reward = sum(e["reward"] for e in recent_episodes) / len(recent_episodes)
            else:
                avg_reward = 0.0

            # Q-value stats from a small sample
            q_mean = 0.0
            q_std = 0.0
            if len(engine.replay_buffer) >= 5:
                sample = engine.replay_buffer.sample(min(5, len(engine.replay_buffer)), engine.device)
                if sample is not None:
                    with torch.no_grad():
                        q_vals = engine.q_network(sample[0])
                        q_mean = float(q_vals.mean().item())
                        q_std = float(q_vals.std().item())

            target_synced = result["train_step"] % engine.target_update_freq == 0

            metrics.record_training_step(
                train_step=result["train_step"],
                loss=result["loss"],
                epsilon=result["epsilon"],
                avg_reward_last_50=round(avg_reward, 4),
                buffer_size=len(engine.replay_buffer),
                q_value_mean=round(q_mean, 4),
                q_value_std=round(q_std, 4),
                target_network_synced=target_synced,
            )

        # Save weights after batch
        if epochs_completed > 0:
            engine.save_weights()

        return {
            "status": "completed",
            "epochs_completed": epochs_completed,
            "final_loss": loss_curve[-1] if loss_curve else None,
            "final_epsilon": epsilon_curve[-1] if epsilon_curve else None,
            "loss_curve": loss_curve,
            "epsilon_curve": epsilon_curve,
        }
