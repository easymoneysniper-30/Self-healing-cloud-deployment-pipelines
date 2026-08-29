"""Unit tests for Drift Detection and Anomaly Monitoring Subsystems."""

import pytest
from src.core.models import DriftSeverity, IncidentType
from src.core.state_store import StateStore
from src.telemetry.anomaly_detector import AnomalyDetector
from src.telemetry.drift_detector import DriftDetector


@pytest.fixture
def temp_store(tmp_path):
    db_file = tmp_path / "test_telemetry.db"
    return StateStore(str(db_file))


def test_drift_detector_clean(temp_store):
    detector = DriftDetector(state_store=temp_store)
    cfg = {"replicas": 3, "environment": {"LOG_LEVEL": "INFO"}}
    finding, incident = detector.compare_configurations("test-app", cfg, cfg)
    assert finding is None
    assert incident is None


def test_drift_detector_severity_classification(temp_store):
    detector = DriftDetector(state_store=temp_store)
    ref_cfg = {
        "metadata": {"labels": {"app": "v1"}},
        "environment": {
            "LOG_LEVEL": "INFO",
            "ALLOW_PRIVILEGED_ACCESS": "false",
            "DATABASE_URL": "postgres://user:pwd@db:5432/main",
        },
    }

    # Live config has drifted security keys and functional keys
    live_cfg = {
        "metadata": {"labels": {"app": "v1-custom"}},  # Cosmetic
        "environment": {
            "LOG_LEVEL": "DEBUG",  # Functional
            "ALLOW_PRIVILEGED_ACCESS": "true",  # Critical Security
            "DATABASE_URL": "postgres://untrusted:bad@db:5432/main",  # Critical Security
        },
    }

    finding, incident = detector.compare_configurations("payments-service", live_cfg, ref_cfg)
    assert finding is not None
    assert incident is not None
    assert finding.overall_severity == DriftSeverity.CRITICAL_SECURITY
    assert len(finding.diff_items) >= 3
    assert incident.incident_type == IncidentType.CONFIGURATION_DRIFT


def test_anomaly_detector_nominal(temp_store):
    detector = AnomalyDetector(state_store=temp_store)
    # Nominal metrics
    metrics = {"latency_p95_ms": 45.0, "error_rate_pct": 0.05, "cpu_util_pct": 30.0}
    anomalies, incident = detector.analyze_metrics("payments-service", metrics)
    assert len(anomalies) == 0
    assert incident is None


def test_anomaly_detector_threshold_breach(temp_store):
    detector = AnomalyDetector(state_store=temp_store)
    # Severe latency and error rate breach
    metrics = {"latency_p95_ms": 950.0, "error_rate_pct": 14.5}
    anomalies, incident = detector.analyze_metrics(
        "payments-service", metrics, recent_deployment_time=60.0
    )
    assert len(anomalies) == 2
    assert incident is not None
    assert incident.incident_type == IncidentType.PERFORMANCE_ANOMALY
    assert any(a.correlated_recent_deploy for a in anomalies)
