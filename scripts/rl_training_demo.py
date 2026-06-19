"""Offline RL training demo: seeds replay buffer, trains, plots convergence."""
import sys, json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from services.rl_decision_engine import get_rl_engine, StateVector
from services.rl_metrics import get_rl_metrics
from services.rl_batch_trainer import RLBatchTrainer

OUT = Path(__file__).resolve().parent.parent / "docs"

def generate_synthetic_transitions(engine, count: int = 800):
    """Fill the replay buffer with plausible dispatching transitions."""
    actions = engine.ACTIONS
    for _ in range(count):
        state = StateVector(
            utilization_norm=float(np.random.beta(2, 3)),
            route_risk=float(np.random.uniform(0, 0.4)),
            eta_multiplier=float(np.random.uniform(1.0, 1.8)),
            sla_urgency=float(np.random.beta(1.5, 2)),
            payload_norm=float(np.random.uniform(0.3, 1.0)),
            priority_norm=float(np.random.uniform(0, 1)),
            port_pressure=float(np.random.uniform(0, 0.3)),
            weather_severity=float(np.random.uniform(0, 0.6)),
            news_severity=float(np.random.uniform(0, 0.5)),
            time_of_day=float(np.random.uniform(0, 1)),
        )
        next_state = StateVector(
            utilization_norm=float(np.clip(state.utilization_norm + np.random.normal(0, 0.1), 0, 1)),
            route_risk=float(np.clip(state.route_risk + np.random.normal(0, 0.05), 0, 1)),
            eta_multiplier=float(max(1.0, state.eta_multiplier + np.random.normal(0, 0.1))),
            sla_urgency=float(np.clip(state.sla_urgency + np.random.normal(0, 0.08), 0, 1)),
            payload_norm=float(np.clip(state.payload_norm + np.random.normal(0, 0.05), 0, 1)),
            priority_norm=state.priority_norm,
            port_pressure=float(np.clip(state.port_pressure + np.random.normal(0, 0.03), 0, 1)),
            weather_severity=float(np.clip(state.weather_severity + np.random.normal(0, 0.05), 0, 1)),
            news_severity=float(np.clip(state.news_severity + np.random.normal(0, 0.04), 0, 1)),
            time_of_day=float((state.time_of_day + 0.05) % 1.0),
        )
        action = actions[np.random.randint(len(actions))]
        reward = float(np.clip(np.random.normal(0.5, 0.3), -1.0, 2.0))
        done = np.random.random() < 0.15
        engine.store_transition(state, action, reward, next_state, done)

def main():
    print("Initialising RL engine…")
    engine = get_rl_engine()
    metrics = get_rl_metrics()

    initial_buffer = len(engine.replay_buffer)
    if initial_buffer < 200:
        print(f"Seeding replay buffer (current={initial_buffer})…")
        generate_synthetic_transitions(engine, count=800)
    print(f"Buffer size: {len(engine.replay_buffer)}")

    print("Running batch training (500 epochs)…")
    trainer = RLBatchTrainer()
    result = trainer.train_batch(epochs=500)
    print(json.dumps({k: v for k, v in result.items() if k not in ("loss_curve", "epsilon_curve")}, indent=2))

    loss_curve = result.get("loss_curve", [])
    epsilon_curve = result.get("epsilon_curve", [])

    if not loss_curve:
        print("No training completed — insufficient data or engine issue.")
        return

    OUT.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("DQN Offline Training — Logisight RL Agent", fontsize=14, fontweight="bold")

    epochs = range(1, len(loss_curve) + 1)
    ax1.plot(epochs, loss_curve, color="#3b82f6", linewidth=0.8)
    ax1.set_xlabel("Training Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("Q-Network Loss")
    ax1.grid(alpha=0.3)

    ax2.plot(epochs, epsilon_curve, color="#f59e0b", linewidth=0.8)
    ax2.set_xlabel("Training Epoch")
    ax2.set_ylabel("Epsilon (exploration rate)")
    ax2.set_title("Exploration Decay")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plot_path = OUT / "rl_training_curve.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    print(f"Plot saved to {plot_path}")

    print(f"\nFinal loss: {loss_curve[-1]:.4f}")
    print(f"Final epsilon: {epsilon_curve[-1]:.4f}")
    print(f"Total epochs: {len(loss_curve)}")

if __name__ == "__main__":
    main()
