"""Automated Benchmark Suite Runner.

Executes comparative resilience test suite across standard failure classes
(Deployment Crash, Config Drift, Latency Anomaly, and HITL Escalation)
evaluating the Self-Healing system against a conventional baseline (PRD Section 15).
"""

from __future__ import annotations
import asyncio
import time
from typing import Dict, Optional
from src.core.models import (
    ActionType,
    DeploymentLifecycleEvent,
    IncidentStatus,
    utc_now,
)
from src.core.orchestrator import Orchestrator
from src.core.policy_engine import PolicyEngine
from src.core.state_store import StateStore
from src.evaluation.metrics_collector import MetricsCollector, ScenarioResult
from src.target_env.mock_deploy_target import MockDeploymentTarget


class BenchmarkRunner:
    """Automates end-to-end benchmark evaluation test suite."""

    def __init__(
        self,
        orchestrator: Optional[Orchestrator] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        self.state_store = StateStore("benchmark_test.db")
        self.policy_engine = PolicyEngine(state_store=self.state_store)
        self.target_env = MockDeploymentTarget()
        self.orchestrator = orchestrator or Orchestrator(
            state_store=self.state_store,
            policy_engine=self.policy_engine,
            target_env=self.target_env,
        )
        self.collector = metrics_collector or MetricsCollector()

    async def run_scenario_1_deployment_crash(self) -> ScenarioResult:
        """Scenario 1: Defective Deployment Rollout & Autonomous Rollback (UC-1)."""
        t0 = time.time()
        # Ingest defective deployment event
        dep_event, incident = self.orchestrator.ingestion_engine.ingest_ci_event({
            "service_name": "payments-service",
            "version": "v2.2.0-broken",
            "event_type": "FAILURE",
            "error_type": "DeploymentCrashLoop",
            "error_message": "Container startup failure (CrashLoopBackOff).",
            "logs_snippet": "[FATAL] Container exited with code 137. Health probe timed out.",
        })
        det_latency = time.time() - t0

        # Process incident through orchestrator
        resolved_inc = await self.orchestrator.process_incident(incident)
        total_time = time.time() - t0

        is_correct = (
            resolved_inc.hypothesis is not None
            and resolved_inc.hypothesis.recommended_action == ActionType.ROLLBACK_DEPLOYMENT
        )

        return ScenarioResult(
            scenario_id="SCN-01",
            name="Defective Deployment Rollout (CrashLoopBackOff)",
            fault_type="DEPLOYMENT_FAILURE",
            injected_root_cause="Defective deployment artifact v2.2.0-broken",
            diagnosed_root_cause=resolved_inc.hypothesis.primary_cause if resolved_inc.hypothesis else "Unknown",
            is_diagnosis_correct=is_correct,
            detection_latency_seconds=round(det_latency, 3),
            recovery_time_seconds=round(total_time, 3),
            repair_success=resolved_inc.status == IncidentStatus.RESOLVED,
            human_intervention_required=False,
            baseline_recovery_time_seconds=480.0,  # 8 min on-call manual triage
        )

    async def run_scenario_2_config_drift(self) -> ScenarioResult:
        """Scenario 2: Out-of-band Configuration Drift & Reversible Patching (UC-2)."""
        t0 = time.time()
        # Inject drift into target
        self.target_env.inject_fault(
            "CONFIG_DRIFT",
            {"key": "ALLOW_PRIVILEGED_ACCESS", "value": "true", "add_bad_db_url": True},
        )

        finding, incident = self.orchestrator.drift_detector.compare_configurations(
            service_name="payments-service",
            live_config=self.target_env.get_live_config(),
            reference_config=self.target_env.reference_config,
        )
        det_latency = time.time() - t0

        evidence = self.orchestrator.diagnostic_agent.collect_evidence(
            incident=incident,
            drift_findings=[finding],
            logs_snippet=self.target_env.get_recent_logs(),
        )

        resolved_inc = await self.orchestrator.process_incident(incident, evidence_bundle=evidence)
        total_time = time.time() - t0

        is_correct = (
            resolved_inc.hypothesis is not None
            and resolved_inc.hypothesis.recommended_action == ActionType.PATCH_CONFIG
        )

        return ScenarioResult(
            scenario_id="SCN-02",
            name="Out-of-band Configuration Drift Reversion",
            fault_type="CONFIGURATION_DRIFT",
            injected_root_cause="Out-of-band runtime parameter modification",
            diagnosed_root_cause=resolved_inc.hypothesis.primary_cause if resolved_inc.hypothesis else "Unknown",
            is_diagnosis_correct=is_correct,
            detection_latency_seconds=round(det_latency, 3),
            recovery_time_seconds=round(total_time, 3),
            repair_success=resolved_inc.status == IncidentStatus.RESOLVED,
            human_intervention_required=False,
            baseline_recovery_time_seconds=360.0,  # 6 min manual git diff & redeploy
        )

    async def run_scenario_3_performance_regression(self) -> ScenarioResult:
        """Scenario 3: Post-Deployment Performance Regression Anomaly (UC-3)."""
        t0 = time.time()
        # Ingest metrics correlated with recent deployment
        anomalies, incident = self.orchestrator.anomaly_detector.analyze_metrics(
            service_name="payments-service",
            metrics={"latency_p95_ms": 820.0, "error_rate_pct": 9.2},
            recent_deployment_time=90.0,
        )
        det_latency = time.time() - t0

        evidence = self.orchestrator.diagnostic_agent.collect_evidence(
            incident=incident,
            anomaly_findings=anomalies,
            logs_snippet=self.target_env.get_recent_logs(),
            metrics_summary={"latency_p95_ms": 820.0, "error_rate_pct": 9.2},
        )

        resolved_inc = await self.orchestrator.process_incident(incident, evidence_bundle=evidence)
        total_time = time.time() - t0

        is_correct = (
            resolved_inc.hypothesis is not None
            and resolved_inc.hypothesis.recommended_action == ActionType.ROLLBACK_DEPLOYMENT
        )

        return ScenarioResult(
            scenario_id="SCN-03",
            name="Post-Deployment Latency & Error Regression",
            fault_type="PERFORMANCE_ANOMALY",
            injected_root_cause="Post-deployment performance regression",
            diagnosed_root_cause=resolved_inc.hypothesis.primary_cause if resolved_inc.hypothesis else "Unknown",
            is_diagnosis_correct=is_correct,
            detection_latency_seconds=round(det_latency, 3),
            recovery_time_seconds=round(total_time, 3),
            repair_success=resolved_inc.status == IncidentStatus.RESOLVED,
            human_intervention_required=False,
            baseline_recovery_time_seconds=540.0,  # 9 min APM inspection & rollback
        )

    async def run_scenario_4_ambiguous_external_spike(self) -> ScenarioResult:
        """Scenario 4: Ambiguous External Spike Gated by Policy Engine (SR-3, SR-11, UC-5)."""
        t0 = time.time()
        # Ingest metrics with NO recent deployment (external spike)
        anomalies, incident = self.orchestrator.anomaly_detector.analyze_metrics(
            service_name="payments-service",
            metrics={"latency_p95_ms": 680.0, "error_rate_pct": 4.5},
            recent_deployment_time=None,  # No recent deploy
        )
        det_latency = time.time() - t0

        evidence = self.orchestrator.diagnostic_agent.collect_evidence(
            incident=incident,
            anomaly_findings=anomalies,
            logs_snippet=self.target_env.get_recent_logs(),
        )

        # Process incident: should transition to AWAITING_APPROVAL because confidence < 80%
        gated_inc = await self.orchestrator.process_incident(incident, evidence_bundle=evidence)

        # Operator evaluates and approves
        operator_approved_inc = await self.orchestrator.human_approve_repair(
            incident_id=gated_inc.incident_id,
            operator_name="DevOpsLead",
            comment="Operator reviewed APM traces: external upstream gateway throttling.",
        )
        total_time = time.time() - t0

        is_correct = (
            gated_inc.hypothesis is not None
            and gated_inc.hypothesis.recommended_action == ActionType.MANUAL_ESCALATION
            and gated_inc.hypothesis.confidence_score < 0.80
        )

        return ScenarioResult(
            scenario_id="SCN-04",
            name="Ambiguous External Spike (HITL Approval Gate)",
            fault_type="PERFORMANCE_ANOMALY",
            injected_root_cause="External upstream load surge (No recent deploy)",
            diagnosed_root_cause=gated_inc.hypothesis.primary_cause if gated_inc.hypothesis else "Unknown",
            is_diagnosis_correct=is_correct,
            detection_latency_seconds=round(det_latency, 3),
            recovery_time_seconds=round(total_time, 3),
            repair_success=operator_approved_inc is not None,
            human_intervention_required=True,
            baseline_recovery_time_seconds=300.0,
        )

    async def execute_all(self) -> Dict[str, Any]:
        """Executes full benchmark suite and records results."""
        self.collector.results.clear()

        r1 = await self.run_scenario_1_deployment_crash()
        self.collector.record_scenario(r1)

        r2 = await self.run_scenario_2_config_drift()
        self.collector.record_scenario(r2)

        r3 = await self.run_scenario_3_performance_regression()
        self.collector.record_scenario(r3)

        r4 = await self.run_scenario_4_ambiguous_external_spike()
        self.collector.record_scenario(r4)

        summary = self.collector.compute_summary()
        return summary.model_dump()
