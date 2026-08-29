"""Unit tests for Core Models and StateStore Cryptographic Audit Log."""

import os
import sqlite3
import pytest
from src.core.models import (
    AuditEvent,
    ChaosExperiment,
    DeploymentEvent,
    DeploymentLifecycleEvent,
    DriftSeverity,
    Incident,
    IncidentStatus,
    IncidentType,
    generate_correlation_id,
    utc_now,
)
from src.core.state_store import StateStore


@pytest.fixture
def temp_store(tmp_path):
    db_file = tmp_path / "test_store.db"
    return StateStore(str(db_file))


def test_models_serialization():
    cid = generate_correlation_id()
    assert cid.startswith("corr-")

    incident = Incident(
        correlation_id=cid,
        service_name="payments-service",
        incident_type=IncidentType.DEPLOYMENT_FAILURE,
        summary="Test deployment crash",
    )
    assert incident.status == IncidentStatus.DETECTED
    json_data = incident.model_dump_json()
    assert "payments-service" in json_data


def test_state_store_incident_crud(temp_store):
    cid = generate_correlation_id()
    incident = Incident(
        correlation_id=cid,
        service_name="checkout-service",
        incident_type=IncidentType.CONFIGURATION_DRIFT,
        summary="Drift detected on checkout",
    )
    temp_store.save_incident(incident)

    retrieved = temp_store.get_incident(incident.incident_id)
    assert retrieved is not None
    assert retrieved.correlation_id == cid
    assert retrieved.status == IncidentStatus.DETECTED

    # Update incident
    retrieved.status = IncidentStatus.RESOLVED
    retrieved.recovery_duration_seconds = 1.25
    temp_store.save_incident(retrieved)

    updated = temp_store.get_incident(incident.incident_id)
    assert updated.status == IncidentStatus.RESOLVED
    assert updated.recovery_duration_seconds == 1.25


def test_tamper_evident_audit_log_chaining(temp_store):
    cid = generate_correlation_id()

    # Append 3 sequential events
    e1 = temp_store.append_audit_event(
        cid, "DiagnosticAgent", "DIAGNOSIS_STARTED", {"step": 1}
    )
    e2 = temp_store.append_audit_event(
        cid, "PolicyEngine", "POLICY_VALIDATION_PASSED", {"step": 2}
    )
    e3 = temp_store.append_audit_event(
        cid, "RepairAgent", "ROLLBACK_EXECUTED", {"step": 3}
    )

    # Initial prev_hash is 64 zeros
    assert e1.prev_hash == "0" * 64
    assert e2.prev_hash == e1.current_hash
    assert e3.prev_hash == e2.current_hash

    # Verify integrity passes
    is_valid, err = temp_store.verify_audit_log_integrity()
    assert is_valid is True
    assert err is None


def test_audit_log_tamper_detection(temp_store):
    cid = generate_correlation_id()
    temp_store.append_audit_event(cid, "Agent1", "EVENT_1", {"v": 1})
    temp_store.append_audit_event(cid, "Agent2", "EVENT_2", {"v": 2})

    # Tamper with the database directly (simulating malicious database modification)
    with temp_store._get_connection() as conn:
        conn.execute("UPDATE audit_log SET actor = 'MaliciousHacker' WHERE sequence_id = 1")
        conn.commit()

    # Integrity verification must fail
    is_valid, err = temp_store.verify_audit_log_integrity()
    assert is_valid is False
    assert "tampered" in err.lower() or "mismatch" in err.lower()


def test_circuit_breaker_state(temp_store):
    service = "payments-service"
    cb = temp_store.get_circuit_breaker(service)
    assert cb["consecutive_failures"] == 0
    assert cb["is_tripped"] is False

    # Record 2 failures
    assert temp_store.record_repair_failure(service, max_threshold=3) is False
    assert temp_store.record_repair_failure(service, max_threshold=3) is False

    # 3rd failure trips breaker
    assert temp_store.record_repair_failure(service, max_threshold=3) is True
    cb = temp_store.get_circuit_breaker(service)
    assert cb["is_tripped"] is True

    # Reset
    temp_store.reset_circuit_breaker(service)
    cb_reset = temp_store.get_circuit_breaker(service)
    assert cb_reset["consecutive_failures"] == 0
    assert cb_reset["is_tripped"] is False
