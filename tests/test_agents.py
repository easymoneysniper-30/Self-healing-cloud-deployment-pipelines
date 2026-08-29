"""Unit tests for Diagnostic Agent, Repair Agent, and Chaos Agent."""

import pytest
from src.agents.chaos_agent import ChaosAgent
from src.agents.diagnostic_agent import DiagnosticAgent
from src.agents.repair_agent import RepairAgent
from src.core.models import (
    ActionType,
    DeploymentEvent,
    DeploymentLifecycleEvent,
    FailureRecord,
    Incident,
    IncidentStatus,
    IncidentType,
    generate_correlation_id,
)
from src.core.policy_engine import PolicyEngine
from src.core.state_store import StateStore
from src.target_env.mock_deploy_target import MockDeploymentTarget


@pytest.fixture
def env_setup(tmp_path):
    db_file = tmp_path / "test_agents.db"
    store = StateStore(str(db_file))
    policy = PolicyEngine(state_store=store)
    target = MockDeploymentTarget()
    diag = DiagnosticAgent(state_store=store)
    repair = RepairAgent(policy_engine=policy, state_store=store, target_env=target)
    chaos = ChaosAgent(target_env=target, policy_engine=policy, state_store=store)
    return store, policy, target, diag, repair, chaos


def test_diagnostic_agent_crash_diagnosis(env_setup):
    store, policy, target, diag, repair, chaos = env_setup
    cid = generate_correlation_id()
    incident = Incident(
        correlation_id=cid,
        service_name="payments-service",
        incident_type=IncidentType.DEPLOYMENT_FAILURE,
        summary="Rollout crashed",
    )
    fail_rec = FailureRecord(
        correlation_id=cid,
        service_name="payments-service",
        version="v2.2.0-broken",
        error_type="CrashLoopBackOff",
        error_message="Pod failed readiness probe",
        logs_snippet="CrashLoopBackOff: exited with code 137",
    )
    evidence = diag.collect_evidence(
        incident=incident,
        failure_records=[fail_rec],
        logs_snippet=fail_rec.logs_snippet,
    )

    hypothesis = diag.diagnose(evidence, incident)
    assert hypothesis.confidence_score >= 0.90
    assert hypothesis.recommended_action == ActionType.ROLLBACK_DEPLOYMENT
    assert len(hypothesis.reasoning_trace) >= 4


def test_repair_agent_rollback_execution(env_setup):
    store, policy, target, diag, repair, chaos = env_setup
    cid = generate_correlation_id()
    incident = Incident(
        correlation_id=cid,
        service_name="payments-service",
        incident_type=IncidentType.DEPLOYMENT_FAILURE,
        summary="Rollout crashed",
    )

    # Set target into broken state
    target.deploy_new_version("v2.2.0-broken", is_defective=True)
    assert target.is_healthy is False

    evidence = diag.collect_evidence(incident, logs_snippet=target.get_recent_logs())
    hypothesis = diag.diagnose(evidence, incident)
    plan = repair.create_repair_plan(incident, hypothesis)

    assert plan.status == "AUTO_APPROVED"
    assert plan.policy_validation.is_allowed is True

    result = repair.execute_repair(incident, plan)
    assert result.success is True
    assert result.post_verification_passed is True
    assert target.is_healthy is True
    assert target.current_version == "v2.0.0"


def test_chaos_agent_injection_and_abort(env_setup):
    store, policy, target, diag, repair, chaos = env_setup

    exp = chaos.create_experiment(
        name="Test Latency Fault",
        fault_type="LATENCY_SPIKE",
        params={"latency_ms": 900.0, "error_rate_pct": 15.0},
    )
    assert exp.status == "CREATED"

    injected = chaos.inject_fault(exp)
    assert injected is True
    assert exp.status == "RUNNING"
    assert target.metrics["latency_p95_ms"] == 900.0

    # Terminate experiment safely
    terminated = chaos.terminate_experiment(exp.experiment_id, reason="TEST_COMPLETE")
    assert terminated.status == "TEST_COMPLETE"
    assert target.metrics["latency_p95_ms"] == 45.0  # Restored to baseline nominal
