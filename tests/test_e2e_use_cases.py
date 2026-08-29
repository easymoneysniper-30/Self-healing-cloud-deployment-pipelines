"""End-to-End Use Case Integration Tests (UC-1 to UC-5).

Verifies the complete closed-loop workflows defined in PRD Section 13.
"""

import pytest
from src.core.models import (
    ActionType,
    IncidentStatus,
    IncidentType,
)
from src.core.orchestrator import Orchestrator
from src.core.policy_engine import PolicyEngine
from src.core.state_store import StateStore
from src.target_env.mock_deploy_target import MockDeploymentTarget


@pytest.fixture
def orchestrator_fixture(tmp_path):
    db_file = tmp_path / "test_e2e.db"
    store = StateStore(str(db_file))
    policy = PolicyEngine(state_store=store)
    target = MockDeploymentTarget()
    orch = Orchestrator(state_store=store, policy_engine=policy, target_env=target)
    return orch, store, policy, target


@pytest.mark.asyncio
async def test_uc1_failed_deployment_and_rollback(orchestrator_fixture):
    """UC-1: Failed Deployment Diagnosis and Rollback."""
    orch, store, policy, target = orchestrator_fixture

    # 1. CI/CD platform reports failed deployment
    dep_event, incident = orch.ingestion_engine.ingest_ci_event({
        "service_name": "payments-service",
        "version": "v2.2.0-broken",
        "event_type": "FAILURE",
        "error_type": "CrashLoopBackOff",
        "error_message": "Liveness probe failed",
        "logs_snippet": "CrashLoopBackOff: exit code 137",
    })
    assert incident is not None

    # Set mock target state into crash
    target.deploy_new_version("v2.2.0-broken", is_defective=True)
    assert target.is_healthy is False

    # 2-6. Closed-loop process
    resolved = await orch.process_incident(incident)

    # 7. Verification
    assert resolved.status == IncidentStatus.RESOLVED
    assert resolved.hypothesis.recommended_action == ActionType.ROLLBACK_DEPLOYMENT
    assert resolved.hypothesis.confidence_score >= 0.80
    assert resolved.execution_result.post_verification_passed is True
    assert target.is_healthy is True
    assert target.current_version == "v2.0.0"

    # Audit trail verification
    is_valid, _ = store.verify_audit_log_integrity()
    assert is_valid is True


@pytest.mark.asyncio
async def test_uc2_configuration_drift_and_patching(orchestrator_fixture):
    """UC-2: Configuration-Drift Detection and Patching."""
    orch, store, policy, target = orchestrator_fixture

    # 1. Simulate drift in live environment
    target.inject_fault(
        "CONFIG_DRIFT",
        {"key": "ALLOW_PRIVILEGED_ACCESS", "value": "true", "add_bad_db_url": True},
    )
    assert target.live_config["environment"]["ALLOW_PRIVILEGED_ACCESS"] == "true"

    # 2. Drift detector flags discrepancy
    finding, incident = orch.drift_detector.compare_configurations(
        service_name="payments-service",
        live_config=target.get_live_config(),
        reference_config=target.reference_config,
    )
    assert finding is not None
    assert incident is not None

    evidence = orch.diagnostic_agent.collect_evidence(
        incident=incident,
        drift_findings=[finding],
        logs_snippet=target.get_recent_logs(),
    )

    # 3-6. Closed-loop processing
    resolved = await orch.process_incident(incident, evidence_bundle=evidence)

    # 7. Verification
    assert resolved.status == IncidentStatus.RESOLVED
    assert resolved.hypothesis.recommended_action == ActionType.PATCH_CONFIG
    assert target.live_config["environment"]["ALLOW_PRIVILEGED_ACCESS"] == "false"


@pytest.mark.asyncio
async def test_uc3_runtime_performance_degradation(orchestrator_fixture):
    """UC-3: Runtime Performance Degradation Response."""
    orch, store, policy, target = orchestrator_fixture

    # 1. Monitoring detects anomaly correlated with recent deployment
    anomalies, incident = orch.anomaly_detector.analyze_metrics(
        service_name="payments-service",
        metrics={"latency_p95_ms": 750.0, "error_rate_pct": 11.0},
        recent_deployment_time=100.0,
    )
    assert len(anomalies) >= 1

    evidence = orch.diagnostic_agent.collect_evidence(
        incident=incident,
        anomaly_findings=anomalies,
        logs_snippet=target.get_recent_logs(),
    )

    resolved = await orch.process_incident(incident, evidence_bundle=evidence)
    assert resolved.status == IncidentStatus.RESOLVED
    assert resolved.hypothesis.recommended_action == ActionType.ROLLBACK_DEPLOYMENT


@pytest.mark.asyncio
async def test_uc4_chaos_injection_resilience_assessment(orchestrator_fixture):
    """UC-4: Controlled Chaos Injection and Resilience Assessment."""
    orch, store, policy, target = orchestrator_fixture

    # 1-3. Operator defines and launches chaos experiment
    exp = orch.chaos_agent.create_experiment(
        name="Chaos Experiment 01",
        fault_type="DEPLOYMENT_CRASH",
        target_service="payments-service",
        duration_seconds=30,
        params={"version": "v2.2.0-chaos"},
    )
    injected = orch.chaos_agent.inject_fault(exp)
    assert injected is True
    assert target.is_healthy is False

    # 4. Trigger detection and repair loop
    dep_event, incident = orch.ingestion_engine.ingest_ci_event({
        "service_name": "payments-service",
        "version": "v2.2.0-chaos",
        "event_type": "FAILURE",
        "error_type": "CrashLoopBackOff",
        "error_message": "Chaos injected crash",
    })
    incident.is_chaos_injected = True
    incident.chaos_experiment_id = exp.experiment_id

    resolved = await orch.process_incident(incident)
    assert resolved.status == IncidentStatus.RESOLVED

    # 5-6. Terminate experiment and verify
    term_exp = orch.chaos_agent.terminate_experiment(exp.experiment_id, reason="SELF_HEALED")
    assert term_exp.status == "SELF_HEALED"
    assert target.is_healthy is True


@pytest.mark.asyncio
async def test_uc5_human_review_and_emergency_stop(orchestrator_fixture):
    """UC-5: Human Review, Override, Emergency Stop, and Post-Repair Verification."""
    orch, store, policy, target = orchestrator_fixture

    # 1. Trigger low confidence anomaly (No recent deploy) -> Escalates to Human Gate
    anomalies, incident = orch.anomaly_detector.analyze_metrics(
        service_name="payments-service",
        metrics={"latency_p95_ms": 600.0, "error_rate_pct": 3.5},
        recent_deployment_time=None,
    )
    evidence = orch.diagnostic_agent.collect_evidence(incident, anomaly_findings=anomalies)

    gated = await orch.process_incident(incident, evidence_bundle=evidence)
    assert gated.status == IncidentStatus.AWAITING_APPROVAL

    # 2. Operator approves
    approved = await orch.human_approve_repair(
        incident_id=gated.incident_id,
        operator_name="PrincipalSRE",
        comment="Manual approval after log inspection.",
    )
    assert approved.status in [IncidentStatus.RESOLVED, IncidentStatus.ESCALATED]
    assert approved.human_approved is True

    # 3. Test Global Emergency Stop
    orch.trigger_emergency_stop(operator="PrincipalSRE")
    assert policy.is_emergency_stopped() is True

    # New action must be blocked
    _, new_incident = orch.ingestion_engine.ingest_ci_event({
        "service_name": "payments-service",
        "version": "v2.3.0",
        "event_type": "FAILURE",
        "error_message": "Crash during emergency stop",
    })
    stopped = await orch.process_incident(new_incident)
    assert stopped.status == IncidentStatus.AWAITING_APPROVAL  # Blocked by emergency stop
