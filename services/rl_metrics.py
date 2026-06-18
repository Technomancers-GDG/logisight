"""Persistent RL training metrics store.

Records episode outcomes and training step data in memory (ring buffers)
and persists to append-only JSONL files for survival across restarts.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
EPISODE_LOG_PATH = DATA_DIR / "rl_training_log.jsonl"
TRAINING_LOG_PATH = DATA_DIR / "rl_training_steps.jsonl"
OUTCOME_LOG_PATH = DATA_DIR / "rl_episode_outcomes.jsonl"
MAX_RING_SIZE = 2000


@dataclass(slots=True)
class RLEpisodeRecord:
    episode_id: int
    timestamp: str              # ISO format
    simulation_time: str
    vehicle_id: int
    state_vector: list[float]   # 10-dim input
    action: str                 # chosen action
    reward: float               # computed reward
    q_values: list[float]       # Q-values for all 5 actions
    chosen_by: str              # "exploration" | "exploitation" | "rule_fallback"
    sla_met: bool | None = None
    stockout_prevented: bool | None = None
    co2_delta: float | None = None


@dataclass(slots=True)
class RLTrainingRecord:
    train_step: int
    timestamp: str
    loss: float
    epsilon: float
    avg_reward_last_50: float
    buffer_size: int
    q_value_mean: float
    q_value_std: float
    target_network_synced: bool


class RLMetricsStore:
    """In-memory + disk-backed store for RL episode and training metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._episode_counter = 0
        self._episodes: deque[RLEpisodeRecord] = deque(maxlen=MAX_RING_SIZE)
        self._training_records: deque[RLTrainingRecord] = deque(maxlen=MAX_RING_SIZE)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    # ── Persistence ──────────────────────────────────────────────────

    def _load_from_disk(self) -> None:
        """Reload records from JSONL files on startup."""
        if EPISODE_LOG_PATH.exists():
            try:
                with EPISODE_LOG_PATH.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        self._episodes.append(RLEpisodeRecord(**data))
                if self._episodes:
                    self._episode_counter = self._episodes[-1].episode_id
                logger.info("Loaded %d episode records from disk.", len(self._episodes))
            except Exception as exc:
                logger.warning("Could not load episode log: %s", exc)

        if TRAINING_LOG_PATH.exists():
            try:
                with TRAINING_LOG_PATH.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        self._training_records.append(RLTrainingRecord(**data))
                logger.info("Loaded %d training records from disk.", len(self._training_records))
            except Exception as exc:
                logger.warning("Could not load training log: %s", exc)

        if OUTCOME_LOG_PATH.exists():
            try:
                with OUTCOME_LOG_PATH.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        for ep in self._episodes:
                            if ep.episode_id == data["episode_id"]:
                                ep.sla_met = data.get("sla_met", ep.sla_met)
                                ep.stockout_prevented = data.get("stockout_prevented", ep.stockout_prevented)
                                ep.co2_delta = data.get("co2_delta", ep.co2_delta)
                                break
                logger.info("Applied %d outcome records.", sum(1 for _ in OUTCOME_LOG_PATH.open() if _.strip()))
            except Exception as exc:
                logger.warning("Could not load outcomes log: %s", exc)

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except Exception as exc:
            logger.error("Failed to persist record to %s: %s", path, exc)

    # ── Recording ────────────────────────────────────────────────────

    def record_episode(
        self,
        *,
        simulation_time: str,
        vehicle_id: int,
        state_vector: list[float],
        action: str,
        reward: float,
        q_values: list[float],
        chosen_by: str,
        sla_met: bool | None = None,
        stockout_prevented: bool | None = None,
        co2_delta: float | None = None,
    ) -> RLEpisodeRecord:
        with self._lock:
            self._episode_counter += 1
            record = RLEpisodeRecord(
                episode_id=self._episode_counter,
                timestamp=datetime.utcnow().isoformat(),
                simulation_time=simulation_time,
                vehicle_id=vehicle_id,
                state_vector=state_vector,
                action=action,
                reward=reward,
                q_values=q_values,
                chosen_by=chosen_by,
                sla_met=sla_met,
                stockout_prevented=stockout_prevented,
                co2_delta=co2_delta,
            )
            self._episodes.append(record)
        self._append_jsonl(EPISODE_LOG_PATH, asdict(record))
        return record

    def record_episode_outcome(
        self,
        *,
        episode_id: int | None = None,
        sla_met: bool,
        stockout_prevented: bool,
        co2_delta: float,
    ) -> None:
        """Update the most recent episode (or by id) with outcome data."""
        with self._lock:
            if not self._episodes:
                return
            target: RLEpisodeRecord | None = None
            if episode_id is not None:
                for ep in reversed(self._episodes):
                    if ep.episode_id == episode_id:
                        target = ep
                        break
            else:
                target = self._episodes[-1]
            if target is not None:
                target.sla_met = sla_met
                target.stockout_prevented = stockout_prevented
                target.co2_delta = co2_delta
                self._append_jsonl(OUTCOME_LOG_PATH, {
                    "episode_id": target.episode_id,
                    "sla_met": sla_met,
                    "stockout_prevented": stockout_prevented,
                    "co2_delta": co2_delta,
                })

    def record_training_step(
        self,
        *,
        train_step: int,
        loss: float,
        epsilon: float,
        avg_reward_last_50: float,
        buffer_size: int,
        q_value_mean: float,
        q_value_std: float,
        target_network_synced: bool,
    ) -> RLTrainingRecord:
        record = RLTrainingRecord(
            train_step=train_step,
            timestamp=datetime.utcnow().isoformat(),
            loss=loss,
            epsilon=epsilon,
            avg_reward_last_50=avg_reward_last_50,
            buffer_size=buffer_size,
            q_value_mean=q_value_mean,
            q_value_std=q_value_std,
            target_network_synced=target_network_synced,
        )
        with self._lock:
            self._training_records.append(record)
        self._append_jsonl(TRAINING_LOG_PATH, asdict(record))
        return record

    # ── Queries ──────────────────────────────────────────────────────

    def get_episodes(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            records = list(self._episodes)[-limit:]
        return [asdict(r) for r in records]

    def get_training_history(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            records = list(self._training_records)[-limit:]
        return [asdict(r) for r in records]

    def get_summary(self) -> dict[str, Any]:
        with self._lock:
            episodes = list(self._episodes)
            training = list(self._training_records)

        total_episodes = len(episodes)
        total_training = len(training)
        if not episodes:
            avg_reward = 0.0
            avg_reward_last_100 = 0.0
            sla_rate = 0.0
        else:
            rewards = [e.reward for e in episodes]
            avg_reward = sum(rewards) / len(rewards)
            last_100 = [e.reward for e in episodes[-100:]]
            avg_reward_last_100 = sum(last_100) / len(last_100) if last_100 else avg_reward
            sla_known = [e for e in episodes if e.sla_met is not None]
            sla_rate = (
                sum(1 for e in sla_known if e.sla_met) / max(len(sla_known), 1) * 100
            )

        last_loss = training[-1].loss if training else None
        last_epsilon = training[-1].epsilon if training else None
        losses_last_100 = [r.loss for r in training[-100:] if r.loss is not None]
        avg_loss_last_100 = sum(losses_last_100) / len(losses_last_100) if losses_last_100 else None

        return {
            "total_episodes": total_episodes,
            "total_training_steps": total_training,
            "avg_reward": round(avg_reward, 4),
            "avg_reward_last_100": round(avg_reward_last_100, 4),
            "avg_loss_last_100": round(avg_loss_last_100, 6) if avg_loss_last_100 is not None else None,
            "sla_success_rate_pct": round(sla_rate, 2),
            "last_loss": round(last_loss, 6) if last_loss is not None else None,
            "last_epsilon": round(last_epsilon, 4) if last_epsilon is not None else None,
        }

    def get_action_distribution(self, last_n: int = 200) -> dict[str, int]:
        with self._lock:
            episodes = list(self._episodes)[-last_n:]
        return dict(Counter(e.action for e in episodes))

    def get_reward_trend(self, window: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            episodes = list(self._episodes)
        if not episodes:
            return []
        trend: list[dict[str, Any]] = []
        for i in range(len(episodes)):
            start = max(0, i - window + 1)
            window_episodes = episodes[start : i + 1]
            avg = sum(e.reward for e in window_episodes) / len(window_episodes)
            trend.append({
                "episode_id": episodes[i].episode_id,
                "avg_reward": round(avg, 4),
                "reward": round(episodes[i].reward, 4),
            })
        return trend

    def clear(self) -> None:
        with self._lock:
            self._episodes.clear()
            self._training_records.clear()
            self._episode_counter = 0
        # Truncate log files
        for path in (EPISODE_LOG_PATH, TRAINING_LOG_PATH):
            try:
                path.write_text("", encoding="utf-8")
            except Exception as exc:
                logger.warning("Could not truncate %s: %s", path, exc)


# ── Singleton ────────────────────────────────────────────────────────

_rl_metrics_instance: RLMetricsStore | None = None


def get_rl_metrics() -> RLMetricsStore:
    global _rl_metrics_instance
    if _rl_metrics_instance is None:
        _rl_metrics_instance = RLMetricsStore()
    return _rl_metrics_instance
