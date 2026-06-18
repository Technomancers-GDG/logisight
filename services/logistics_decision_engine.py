from __future__ import annotations

from dataclasses import dataclass

from schemas import DecisionResponse, PredictionResponse, RouteOptionRead


@dataclass(slots=True)
class EvaluatedRoute:
    route: RouteOptionRead
    route_index: int
    predicted_delay_minutes: float
    predicted_risk: float
    adjusted_score: float


class LogisticsDecisionEngine:
    """Chooses the operational route after graph score and predictions are known."""

    def decide(
        self,
        *,
        route_options: list[RouteOptionRead],
        predictions: PredictionResponse,
        delay_threshold_minutes: float = 120.0,
        risk_threshold: float = 0.7,
    ) -> DecisionResponse:
        evaluated = self._evaluate(route_options, predictions)
        if not evaluated:
            raise ValueError("At least one route option is required")

        current_route = evaluated[0]
        delay_exceeded = current_route.predicted_delay_minutes > delay_threshold_minutes
        risk_exceeded = current_route.predicted_risk > risk_threshold
        ranked = sorted(evaluated, key=lambda item: item.adjusted_score)

        if delay_exceeded or risk_exceeded:
            viable = [
                item
                for item in ranked
                if item.predicted_delay_minutes <= delay_threshold_minutes
                and item.predicted_risk <= risk_threshold
            ]
            recommended = viable[0] if viable else ranked[0]
            switched = recommended.route_index != current_route.route_index
        else:
            recommended = ranked[0]
            switched = recommended.route_index != current_route.route_index

        reason_bits = [self._business_reason(recommended, current_route)]
        if delay_exceeded:
            reason_bits.append(
                f"auto-switch evaluated because current delay exceeded {delay_threshold_minutes:.0f} min"
            )
        if risk_exceeded:
            reason_bits.append(
                f"auto-switch evaluated because current risk exceeded {risk_threshold:.2f}"
            )
        if switched:
            reason_bits.append("recommended route differs from the current shortest path")
        else:
            reason_bits.append("current shortest path remains acceptable")

        alternatives = [item.route for item in ranked if item.route_index != recommended.route_index]
        return DecisionResponse(
            recommended_route=recommended.route,
            alternatives=alternatives,
            reasoning="; ".join(reason_bits),
            switched=switched,
            delay_exceeded=delay_exceeded,
        )

    def improvement_score(self, old_route: RouteOptionRead, new_route: RouteOptionRead) -> float:
        old_metrics = old_route.business_metrics
        new_metrics = new_route.business_metrics
        old_score = old_route.score
        new_score = new_route.score
        cost_gain = old_route.total_cost - new_route.total_cost
        time_gain = old_route.total_time - new_route.total_time
        risk_gain = old_route.total_risk - new_route.total_risk
        if old_metrics and new_metrics:
            cost_gain = old_metrics.cost - new_metrics.cost
            time_gain = old_metrics.time - new_metrics.time
            risk_gain = old_metrics.risk - new_metrics.risk
        return round((old_score - new_score) + cost_gain * 0.1 + time_gain * 0.5 + risk_gain * 500, 3)

    def _evaluate(
        self,
        route_options: list[RouteOptionRead],
        predictions: PredictionResponse,
    ) -> list[EvaluatedRoute]:
        prediction_by_index = {prediction.route_index: prediction for prediction in predictions.route_risks}
        prediction_by_signature = {
            prediction.route_signature: prediction for prediction in predictions.route_risks
        }

        evaluated: list[EvaluatedRoute] = []
        for index, route in enumerate(route_options):
            signature = "|".join(route.node_sequence)
            prediction = prediction_by_index.get(index) or prediction_by_signature.get(signature)
            predicted_delay = prediction.predicted_delay_minutes if prediction else 0.0
            predicted_risk = prediction.risk if prediction else min(1.0, route.total_risk)
            # Delay is operationally expensive; risk is scaled so a high-risk
            # route can beat cheapness only when it is materially safer.
            adjusted_score = route.score + predicted_delay * 1.25 + predicted_risk * 500
            evaluated.append(
                EvaluatedRoute(
                    route=route,
                    route_index=index,
                    predicted_delay_minutes=predicted_delay,
                    predicted_risk=predicted_risk,
                    adjusted_score=adjusted_score,
                )
            )
        return evaluated

    @staticmethod
    def _business_reason(recommended: EvaluatedRoute, current_route: EvaluatedRoute) -> str:
        route_label = chr(ord("A") + min(recommended.route_index, 25))
        current = current_route.route
        selected = recommended.route
        cost_delta = current.total_cost - selected.total_cost
        time_delta = current.total_time - selected.total_time
        max_predicted_delay = max(current_route.predicted_delay_minutes, recommended.predicted_delay_minutes)
        if current.business_metrics and selected.business_metrics:
            cost_delta = current.business_metrics.cost - selected.business_metrics.cost
            time_delta = current.business_metrics.time - selected.business_metrics.time

        if abs(cost_delta) < 1:
            cost_phrase = "keeps cost neutral"
        else:
            cost_phrase = (
                f"reduces cost by INR {abs(cost_delta):,.0f}"
                if cost_delta > 0
                else f"costs INR {abs(cost_delta):,.0f} more"
            )
        if abs(time_delta) < 1:
            time_phrase = "keeps transit time neutral"
        else:
            time_phrase = (
                f"saves {time_delta / 60:.1f} hours"
                if time_delta > 0
                else f"adds {abs(time_delta) / 60:.1f} hours"
            )
        delay_phrase = ""
        if current_route.route_index != recommended.route_index and current_route.predicted_delay_minutes > recommended.predicted_delay_minutes:
            delay_phrase = f" while avoiding a predicted {current_route.predicted_delay_minutes / 60:.1f}-hour delay"
        elif max_predicted_delay >= 60:
            delay_phrase = f" while accounting for a predicted {max_predicted_delay / 60:.1f}-hour delay"
        return (
            f"Selected Route {route_label} because it {cost_phrase}, {time_phrase}, "
            f"and holds predicted risk at {recommended.predicted_risk:.2f}{delay_phrase}."
        )
