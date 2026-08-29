"""Unit tests for Policy Engine & Safety Envelope (SR-1 to SR-11)."""

import pytest
from src.core.models import (
    ActionType,
    RepairAction,
    RollbackCheckpoint,
)
from src.core.policy_engine import PolicyEngine
from src.core.state_store import StateStore


@pytest.fixture
def temp_engine(tmp_path):
    db_file = tmp_path / "test_policy.db"
    store = StateStore(str(db_file))
    return PolicyEngine(state_store=store)


def test_policy_allowlist_validation(temp_engine):
    checkpoint = RollbackCheckpoint(
        service_name="payments-service",
        known_good_version="v2.0.0",
        known_good_config={},
    )
    # 1. Allowlisted action with high confidence
    valid_action = RepairAction(
        action_type=ActionType.ROLLBACK_DEPLOYMENT,
        service_name="payments-service",
        rollback_checkpoint=checkpoint,
        rationale="Rollback",
    )
    res = temp_engine.validate_repair_action(valid_action, confidence_score=0.95)
    assert res.is_allowed is True
    assert res.requires_human_approval is False


def test_policy_confidence_threshold_gating(temp_engine):
    checkpoint = RollbackCheckpoint(
        service_name="payments-service",
        known_good_version="v2.0.0",
        known_good_config={},
    )
    # Low confidence action (65% < 80% threshold)
    low_conf_action = RepairAction(
        action_type=ActionType.ROLLBACK_DEPLOYMENT,
        service_name="payments-service",
        rollback_checkpoint=checkpoint,
        rationale="Ambiguous failure",
    )
    res = temp_engine.validate_repair_action(low_conf_action, confidence_score=0.65)
    assert res.confidence_met is False
    assert res.requires_human_approval is True


def test_policy_blast_radius_violation(temp_engine):
    checkpoint = RollbackCheckpoint(
        service_name="unauthorized-core-db",
        known_good_version="v1.0.0",
        known_good_config={},
    )
    unauthorized_action = RepairAction(
        action_type=ActionType.ROLLBACK_DEPLOYMENT,
        service_name="unauthorized-core-db",
        rollback_checkpoint=checkpoint,
        rationale="Unauthorized target",
    )
    res = temp_engine.validate_repair_action(unauthorized_action, confidence_score=0.99)
    assert res.violates_blast_radius is True
    assert res.is_allowed is False
    assert res.requires_human_approval is True


def test_policy_circuit_breaker_enforcement(temp_engine):
    service = "payments-service"
    checkpoint = RollbackCheckpoint(
        service_name=service,
        known_good_version="v2.0.0",
        known_good_config={},
    )
    action = RepairAction(
        action_type=ActionType.ROLLBACK_DEPLOYMENT,
        service_name=service,
        rollback_checkpoint=checkpoint,
        rationale="Rollback",
    )

    # Simulate 3 consecutive repair failures
    temp_engine.state_store.record_repair_failure(service, max_threshold=3)
    temp_engine.state_store.record_repair_failure(service, max_threshold=3)
    temp_engine.state_store.record_repair_failure(service, max_threshold=3)

    res = temp_engine.validate_repair_action(action, confidence_score=0.95)
    assert res.circuit_breaker_tripped is True
    assert res.is_allowed is False
    assert res.requires_human_approval is True


def test_policy_emergency_stop(temp_engine):
    checkpoint = RollbackCheckpoint(
        service_name="payments-service",
        known_good_version="v2.0.0",
        known_good_config={},
    )
    action = RepairAction(
        action_type=ActionType.ROLLBACK_DEPLOYMENT,
        service_name="payments-service",
        rollback_checkpoint=checkpoint,
        rationale="Rollback",
    )

    temp_engine.set_emergency_stop(True)
    res = temp_engine.validate_repair_action(action, confidence_score=0.95)
    assert res.is_allowed is False
    assert "EMERGENCY_STOP" in res.reasons[0]
