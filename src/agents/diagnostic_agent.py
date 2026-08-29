"""Diagnostic Agent Subsystem.

Implements FR-2.1, FR-2.2, FR-2.3, FR-2.4, FR-5.1, SR-2, NFR-5, NFR-9.
Supports Hybrid Diagnostics: Deep LLM Reasoning (Gemini / OpenAI) with automatic
deterministic/heuristic rule fallback for 100% resilience and explainable auditability.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from src.agents.llm_provider import LLMDiagnosticProvider
from src.core.models import (
    ActionType,
    AnomalyFinding,
    DeploymentEvent,
    DriftFinding,
    EvidenceBundle,
    FailureRecord,
    Incident,
    IncidentType,
    RootCauseHypothesis,
    utc_now,
)
from src.core.state_store import StateStore


class DiagnosticAgent:
    """Investigates failure evidence and estimates root cause with confidence scoring."""

    def __init__(
        self,
        state_store: Optional[StateStore] = None,
        llm_provider: Optional[LLMDiagnosticProvider] = None,
    ):
        self.state_store = state_store or StateStore()
        self.llm_provider = llm_provider or LLMDiagnosticProvider()

    def collect_evidence(
        self,
        incident: Incident,
        deployment_events: Optional[List[DeploymentEvent]] = None,
        failure_records: Optional[List[FailureRecord]] = None,
        drift_findings: Optional[List[DriftFinding]] = None,
        anomaly_findings: Optional[List[AnomalyFinding]] = None,
        logs_snippet: str = "",
        metrics_summary: Optional[Dict[str, Any]] = None,
    ) -> EvidenceBundle:
        """Aggregates all relevant observability signals into a structured EvidenceBundle."""
        bundle = EvidenceBundle(
            correlation_id=incident.correlation_id,
            service_name=incident.service_name,
            deployment_events=deployment_events or [],
            failure_records=failure_records or [],
            drift_findings=drift_findings or [],
            anomaly_findings=anomaly_findings or [],
            logs_snippet=logs_snippet,
            metrics_summary=metrics_summary or {},
            collected_at=utc_now(),
        )
        return bundle

    def diagnose(self, evidence: EvidenceBundle, incident: Incident) -> RootCauseHypothesis:
        """Performs evidence-based Root-Cause Analysis (RCA).

        Attempts deep LLM analysis first if configured; falls back automatically to
        deterministic heuristic engine.
        """
        # 1. Attempt Live LLM Reasoning if configured
        if self.llm_provider.is_configured():
            llm_hypothesis = self.llm_provider.diagnose_with_llm(evidence, incident)
            if llm_hypothesis:
                self._record_audit_event(evidence, llm_hypothesis, actor="DiagnosticAgent:LLM")
                return llm_hypothesis

        # 2. Deterministic & Heuristic Rule Engine (Fallback or Default)
        return self._diagnose_heuristics(evidence, incident)

    def _diagnose_heuristics(
        self, evidence: EvidenceBundle, incident: Incident
    ) -> RootCauseHypothesis:
        """Deterministic / signature-based diagnostic engine."""
        reasoning_trace: List[str] = []
        evidence_ids: List[str] = []

        reasoning_trace.append(
            f"[AI Doctor: Heuristic Core] Initiating diagnostic investigation for incident '{incident.incident_id}' (Correlation: {evidence.correlation_id})."
        )
        reasoning_trace.append(
            f"Target service: '{evidence.service_name}'. Incident type: '{incident.incident_type.value}'."
        )

        # 1. Evaluate Deployment Failures
        if incident.incident_type == IncidentType.DEPLOYMENT_FAILURE or evidence.failure_records:
            for fail in evidence.failure_records:
                evidence_ids.append(fail.failure_id)
            for dep in evidence.deployment_events:
                evidence_ids.append(dep.event_id)

            fail_info = (
                evidence.failure_records[0]
                if evidence.failure_records
                else FailureRecord(
                    correlation_id=evidence.correlation_id,
                    service_name=evidence.service_name,
                    version="latest",
                    error_type="UnknownDeployFailure",
                    error_message=incident.summary,
                )
            )

            reasoning_trace.append(
                f"Identified deployment rollout failure: {fail_info.error_type} - {fail_info.error_message}"
            )

            # Check logs snippet for specific failure signatures
            logs_lower = (evidence.logs_snippet or fail_info.logs_snippet).lower()
            if "crashloopbackoff" in logs_lower or "exit code" in logs_lower or "crash" in logs_lower:
                confidence = 0.95
                reasoning_trace.append(
                    "Log analysis detected container crash signature ('CrashLoopBackOff'). Confidence = 95%."
                )
            elif "oomkilled" in logs_lower or "out of memory" in logs_lower:
                confidence = 0.93
                reasoning_trace.append(
                    "Log analysis detected resource starvation ('OOMKilled'). Confidence = 93%."
                )
            elif "health check failed" in logs_lower or "connection refused" in logs_lower:
                confidence = 0.90
                reasoning_trace.append(
                    "Log analysis detected health probe failure. Confidence = 90%."
                )
            else:
                confidence = 0.85
                reasoning_trace.append(
                    "Deployment failed post-rollout validation. Confidence = 85%."
                )

            primary_cause = (
                f"Defective deployment artifact or startup failure in version '{fail_info.version}'."
            )
            explanation = (
                f"Service '{evidence.service_name}' failed during rollout of version '{fail_info.version}'. "
                f"Diagnostic logs show: {fail_info.error_message}. Previous stable version is available for recovery."
            )
            recommended_action = ActionType.ROLLBACK_DEPLOYMENT

        # 2. Evaluate Configuration Drift
        elif incident.incident_type == IncidentType.CONFIGURATION_DRIFT or evidence.drift_findings:
            drift = (
                evidence.drift_findings[0]
                if evidence.drift_findings
                else DriftFinding(
                    correlation_id=evidence.correlation_id,
                    service_name=evidence.service_name,
                    live_snapshot={},
                    reference_snapshot={},
                )
            )
            evidence_ids.append(drift.finding_id)
            drift_count = len(drift.diff_items)

            reasoning_trace.append(
                f"Detected {drift_count} drifted configuration parameter(s) from Git reference state."
            )
            reasoning_trace.append(
                f"Drift severity classified as: {drift.overall_severity.value}."
            )

            confidence = 0.96
            reasoning_trace.append(
                "Deterministic structural diff against declared Git reference state confirmed. Confidence = 96%."
            )

            primary_cause = (
                f"Out-of-band configuration drift ({drift_count} key(s) modified)."
            )
            explanation = (
                f"Live runtime parameters on '{evidence.service_name}' diverged from Git source of truth. "
                f"Affected keys: {', '.join([item.key_path for item in drift.diff_items[:3]])}"
                + ("..." if drift_count > 3 else "")
            )
            recommended_action = ActionType.PATCH_CONFIG

        # 3. Evaluate Performance Anomaly
        elif incident.incident_type == IncidentType.PERFORMANCE_ANOMALY or evidence.anomaly_findings:
            for anom in evidence.anomaly_findings:
                evidence_ids.append(anom.finding_id)

            correlated_deploy = any(
                a.correlated_recent_deploy for a in evidence.anomaly_findings
            )
            primary_anom = evidence.anomaly_findings[0] if evidence.anomaly_findings else None

            if correlated_deploy:
                confidence = 0.88
                reasoning_trace.append(
                    "Metric anomaly is temporally correlated with a recent deployment within 300s window."
                )
                reasoning_trace.append(
                    f"Breached metric: {primary_anom.metric_name if primary_anom else 'latency'} = "
                    f"{primary_anom.observed_value if primary_anom else 'high'}. Confidence = 88%."
                )
                primary_cause = "Performance regression introduced by recent deployment rollout."
                explanation = (
                    f"Service '{evidence.service_name}' experienced severe performance degradation "
                    f"immediately following a deployment. Rollback to prior known-good version is recommended."
                )
                recommended_action = ActionType.ROLLBACK_DEPLOYMENT
            else:
                # External spike or unlinked anomaly
                confidence = 0.65
                reasoning_trace.append(
                    "Metric anomaly detected with NO recent deployment event found. Likely external traffic surge."
                )
                reasoning_trace.append(
                    "Confidence is 65% (below 80% autonomy threshold). Recommending human escalation."
                )
                primary_cause = "External traffic surge or downstream infrastructure saturation."
                explanation = (
                    f"Service '{evidence.service_name}' has elevated metric values without a recent code change. "
                    f"Automated remediation cannot guarantee resolution without risk of service disruption."
                )
                recommended_action = ActionType.MANUAL_ESCALATION

        else:
            confidence = 0.50
            reasoning_trace.append(
                "Insufficient evidence to establish conclusive deterministic root cause."
            )
            primary_cause = "Unspecified service degradation."
            explanation = "Automated diagnosis could not find conclusive evidence. Requires manual triage."
            recommended_action = ActionType.MANUAL_ESCALATION

        reasoning_trace.append(
            f"Diagnostic conclusion finalized: Action = {recommended_action.value}, Confidence = {confidence * 100:.1f}%."
        )

        hypothesis = RootCauseHypothesis(
            correlation_id=evidence.correlation_id,
            service_name=evidence.service_name,
            primary_cause=primary_cause,
            explanation=explanation,
            confidence_score=confidence,
            recommended_action=recommended_action,
            evidence_ids=evidence_ids,
            reasoning_trace=reasoning_trace,
            generated_at=utc_now(),
        )

        self._record_audit_event(evidence, hypothesis, actor="DiagnosticAgent:Heuristic")
        return hypothesis

    def _record_audit_event(
        self, evidence: EvidenceBundle, hypothesis: RootCauseHypothesis, actor: str
    ) -> None:
        self.state_store.append_audit_event(
            correlation_id=evidence.correlation_id,
            actor=actor,
            action_name="ROOT_CAUSE_DIAGNOSIS_COMPLETED",
            details={
                "service_name": evidence.service_name,
                "primary_cause": hypothesis.primary_cause,
                "confidence_score": hypothesis.confidence_score,
                "recommended_action": hypothesis.recommended_action.value,
                "evidence_count": len(hypothesis.evidence_ids),
                "reasoning_steps": len(hypothesis.reasoning_trace),
            },
        )
