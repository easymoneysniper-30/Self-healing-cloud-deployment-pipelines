"""Data models and schemas for Self-Healing Cloud Deployment Pipelines.

Implements data specifications per PRD Sections 8, 11, 12, and 15.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_correlation_id() -> str:
    return f"corr-{uuid4().hex[:12]}"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    DIAGNOSING = "DIAGNOSING"
    POLICY_EVALUATION = "POLICY_EVALUATION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REPAIRING = "REPAIRING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"
    FAILED = "FAILED"


class IncidentType(str, Enum):
    DEPLOYMENT_FAILURE = "DEPLOYMENT_FAILURE"
    CONFIGURATION_DRIFT = "CONFIGURATION_DRIFT"
    PERFORMANCE_ANOMALY = "PERFORMANCE_ANOMALY"
    CHAOS_EXPERIMENT = "CHAOS_EXPERIMENT"


class ActionType(str, Enum):
    ROLLBACK_DEPLOYMENT = "ROLLBACK_DEPLOYMENT"
    PATCH_CONFIG = "PATCH_CONFIG"
    RESTART_POD_OR_SERVICE = "RESTART_POD_OR_SERVICE"
    MANUAL_ESCALATION = "MANUAL_ESCALATION"


class DriftSeverity(str, Enum):
    COSMETIC = "COSMETIC"
    FUNCTIONAL = "FUNCTIONAL"
    CRITICAL_SECURITY = "CRITICAL_SECURITY"


class DeploymentLifecycleEvent(str, Enum):
    START = "START"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    ROLLBACK = "ROLLBACK"


class DeploymentEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"dep-{uuid4().hex[:8]}")
    correlation_id: str = Field(default_factory=generate_correlation_id)
    pipeline_id: str
    service_name: str
    version: str
    commit_sha: str
    event_type: DeploymentLifecycleEvent
    timestamp: datetime = Field(default_factory=utc_now)
    details: Dict[str, Any] = Field(default_factory=dict)


class FailureRecord(BaseModel):
    failure_id: str = Field(default_factory=lambda: f"fail-{uuid4().hex[:8]}")
    correlation_id: str
    service_name: str
    version: str
    error_type: str
    error_message: str
    exit_code: Optional[int] = None
    logs_snippet: str = ""
    timestamp: datetime = Field(default_factory=utc_now)


class DriftDiffItem(BaseModel):
    key_path: str
    declared_value: Any
    live_value: Any
    severity: DriftSeverity


class DriftFinding(BaseModel):
    finding_id: str = Field(default_factory=lambda: f"drift-{uuid4().hex[:8]}")
    correlation_id: str
    service_name: str
    live_snapshot: Dict[str, Any]
    reference_snapshot: Dict[str, Any]
    diff_items: List[DriftDiffItem] = Field(default_factory=list)
    overall_severity: DriftSeverity = DriftSeverity.FUNCTIONAL
    timestamp: datetime = Field(default_factory=utc_now)


class AnomalyFinding(BaseModel):
    finding_id: str = Field(default_factory=lambda: f"anom-{uuid4().hex[:8]}")
    correlation_id: str
    service_name: str
    metric_name: str  # e.g., "latency_p95_ms", "error_rate_pct", "cpu_util_pct"
    observed_value: float
    baseline_value: float
    threshold_value: float
    z_score: Optional[float] = None
    correlated_recent_deploy: bool = False
    timestamp: datetime = Field(default_factory=utc_now)


class EvidenceBundle(BaseModel):
    correlation_id: str
    service_name: str
    deployment_events: List[DeploymentEvent] = Field(default_factory=list)
    failure_records: List[FailureRecord] = Field(default_factory=list)
    drift_findings: List[DriftFinding] = Field(default_factory=list)
    anomaly_findings: List[AnomalyFinding] = Field(default_factory=list)
    logs_snippet: str = ""
    metrics_summary: Dict[str, Any] = Field(default_factory=dict)
    collected_at: datetime = Field(default_factory=utc_now)


class RootCauseHypothesis(BaseModel):
    hypothesis_id: str = Field(default_factory=lambda: f"rca-{uuid4().hex[:8]}")
    correlation_id: str
    service_name: str
    primary_cause: str
    explanation: str
    confidence_score: float = Field(ge=0.0, le=1.0)  # 0.0 to 1.0 (0-100%)
    recommended_action: ActionType
    evidence_ids: List[str] = Field(default_factory=list)
    reasoning_trace: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class RollbackCheckpoint(BaseModel):
    service_name: str
    known_good_version: str
    known_good_config: Dict[str, Any]
    captured_at: datetime = Field(default_factory=utc_now)


class RepairAction(BaseModel):
    action_id: str = Field(default_factory=lambda: f"act-{uuid4().hex[:8]}")
    action_type: ActionType
    service_name: str
    target_version: Optional[str] = None
    target_config_patch: Optional[Dict[str, Any]] = None
    rollback_checkpoint: Optional[RollbackCheckpoint] = None
    rationale: str
    is_reversible: bool = True


class PolicyValidationResult(BaseModel):
    is_allowed: bool
    requires_human_approval: bool
    reasons: List[str] = Field(default_factory=list)
    violates_blast_radius: bool = False
    confidence_met: bool = True
    circuit_breaker_tripped: bool = False
    rate_limit_exceeded: bool = False
    dry_run: bool = False
    evaluated_at: datetime = Field(default_factory=utc_now)


class RepairPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"plan-{uuid4().hex[:8]}")
    correlation_id: str
    proposed_actions: List[RepairAction] = Field(default_factory=list)
    policy_validation: Optional[PolicyValidationResult] = None
    status: str = "PROPOSED"
    approved_by: Optional[str] = None
    approval_timestamp: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)


class RepairExecutionResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: f"exec-{uuid4().hex[:8]}")
    plan_id: str
    correlation_id: str
    action_type: ActionType
    success: bool
    details: str
    duration_seconds: float
    post_verification_passed: bool
    health_metrics: Dict[str, Any] = Field(default_factory=dict)
    executed_at: datetime = Field(default_factory=utc_now)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"audit-{uuid4().hex[:8]}")
    correlation_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    actor: str  # "DiagnosticAgent", "RepairAgent", "ChaosAgent", "PolicyEngine", "HumanOperator:<name>"
    action_name: str
    details: Dict[str, Any] = Field(default_factory=dict)
    prev_hash: str = "0000000000000000000000000000000000000000000000000000000000000000"
    current_hash: str = ""


class ChaosExperiment(BaseModel):
    experiment_id: str = Field(default_factory=lambda: f"chaos-{uuid4().hex[:8]}")
    correlation_id: str = Field(default_factory=generate_correlation_id)
    name: str
    fault_type: str  # "DEPLOYMENT_CRASH", "CONFIG_DRIFT", "LATENCY_SPIKE", "RESOURCE_EXHAUSTION"
    target_service: str
    duration_seconds: int = 30
    params: Dict[str, Any] = Field(default_factory=dict)
    status: str = "CREATED"  # "RUNNING", "TERMINATED", "SAFETY_ABORTED", "COMPLETED"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    detected_by_system: bool = False
    detection_latency_seconds: Optional[float] = None
    repaired_by_system: bool = False
    recovery_time_seconds: Optional[float] = None
    audit_notes: str = ""


class Incident(BaseModel):
    incident_id: str = Field(default_factory=lambda: f"inc-{uuid4().hex[:8]}")
    correlation_id: str
    service_name: str
    incident_type: IncidentType
    status: IncidentStatus = IncidentStatus.DETECTED
    summary: str
    detection_timestamp: datetime = Field(default_factory=utc_now)
    resolution_timestamp: Optional[datetime] = None
    recovery_duration_seconds: Optional[float] = None

    # Step-by-step artifact attachments
    evidence_bundle: Optional[EvidenceBundle] = None
    hypothesis: Optional[RootCauseHypothesis] = None
    repair_plan: Optional[RepairPlan] = None
    execution_result: Optional[RepairExecutionResult] = None
    is_chaos_injected: bool = False
    chaos_experiment_id: Optional[str] = None
    human_approved: Optional[bool] = None
    operator_comment: Optional[str] = None
