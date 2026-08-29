"""Runtime Performance Anomaly Detector Subsystem.

Implements FR-1.4, FR-4.1, FR-4.2, FR-4.3, EI-3.
Monitors latency, error rates, and resource saturation with static thresholds and Z-score anomaly scoring.
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple
from src.core.models import (
    AnomalyFinding,
    Incident,
    IncidentStatus,
    IncidentType,
    generate_correlation_id,
    utc_now,
)
from src.core.state_store import StateStore


class AnomalyDetector:
    """Detects performance degradation and metric deviations."""

    # Default metric SLA thresholds
    DEFAULT_THRESHOLDS = {
        "latency_p95_ms": 250.0,
        "error_rate_pct": 2.0,
        "cpu_util_pct": 85.0,
        "memory_util_pct": 90.0,
    }

    def __init__(
        self,
        state_store: Optional[StateStore] = None,
        thresholds: Optional[Dict[str, float]] = None,
    ):
        self.state_store = state_store or StateStore()
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()
        # Rolling metric windows for statistical baseline computation: {service: {metric_name: [v1, v2, ...]}}
        self._metric_history: Dict[str, Dict[str, List[float]]] = {}

    def record_metric_point(
        self, service_name: str, metric_name: str, value: float, max_history: int = 50
    ) -> None:
        if service_name not in self._metric_history:
            self._metric_history[service_name] = {}
        if metric_name not in self._metric_history[service_name]:
            self._metric_history[service_name][metric_name] = []
        history = self._metric_history[service_name][metric_name]
        history.append(value)
        if len(history) > max_history:
            self._metric_history[service_name][metric_name] = history[-max_history:]

    def _compute_z_score(
        self, service_name: str, metric_name: str, current_value: float
    ) -> Tuple[float, float, Optional[float]]:
        history = self._metric_history.get(service_name, {}).get(metric_name, [])
        if len(history) < 5:
            return current_value, current_value, None

        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std_dev = math.sqrt(variance)

        if std_dev < 1e-4:
            return mean, current_value, 0.0

        z_score = (current_value - mean) / std_dev
        return mean, current_value, round(z_score, 2)

    def analyze_metrics(
        self,
        service_name: str,
        metrics: Dict[str, float],
        recent_deployment_time: Optional[float] = None,
        correlation_id: Optional[str] = None,
    ) -> Tuple[List[AnomalyFinding], Optional[Incident]]:
        """Analyzes incoming metrics stream against static SLAs and statistical Z-score deviations."""
        anomalies: List[AnomalyFinding] = []
        cid = correlation_id or generate_correlation_id()

        for metric_name, observed_value in metrics.items():
            self.record_metric_point(service_name, metric_name, observed_value)
            threshold = self.thresholds.get(metric_name, 100.0)
            baseline_mean, _, z_score = self._compute_z_score(
                service_name, metric_name, observed_value
            )

            # Anomaly condition: Exceeds SLA threshold OR exhibits sharp Z-score spike (Z >= 2.5)
            is_anomaly = (observed_value > threshold) or (
                z_score is not None and z_score >= 2.5
            )

            if is_anomaly:
                # Check if correlated with recent deployment (e.g. within last 300s)
                correlated = (
                    recent_deployment_time is not None
                    and recent_deployment_time <= 300.0
                )
                anomalies.append(
                    AnomalyFinding(
                        correlation_id=cid,
                        service_name=service_name,
                        metric_name=metric_name,
                        observed_value=observed_value,
                        baseline_value=baseline_mean,
                        threshold_value=threshold,
                        z_score=z_score,
                        correlated_recent_deploy=correlated,
                        timestamp=utc_now(),
                    )
                )

        if not anomalies:
            return [], None

        primary_anomaly = max(
            anomalies,
            key=lambda a: (
                a.observed_value / a.threshold_value
                if a.threshold_value > 0
                else a.observed_value
            ),
        )

        incident = Incident(
            correlation_id=cid,
            service_name=service_name,
            incident_type=IncidentType.PERFORMANCE_ANOMALY,
            status=IncidentStatus.DETECTED,
            summary=(
                f"Runtime anomaly on '{service_name}': {primary_anomaly.metric_name} = {primary_anomaly.observed_value:.1f} "
                f"(Threshold: {primary_anomaly.threshold_value:.1f}, Z-score: {primary_anomaly.z_score or 0.0})."
            ),
            detection_timestamp=utc_now(),
        )

        self.state_store.save_incident(incident)
        self.state_store.append_audit_event(
            correlation_id=cid,
            actor="AnomalyDetector",
            action_name="RUNTIME_ANOMALY_DETECTED",
            details={
                "service_name": service_name,
                "anomalies_count": len(anomalies),
                "metrics_breached": [
                    {
                        "metric": a.metric_name,
                        "observed": a.observed_value,
                        "threshold": a.threshold_value,
                        "z_score": a.z_score,
                    }
                    for a in anomalies
                ],
            },
        )

        return anomalies, incident
