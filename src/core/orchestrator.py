"""Agent Orchestrator Subsystem.

Coordinates closed-loop incident lifecycle across Ingestion, Diagnostic Agent,
Policy Engine, Repair Agent, Chaos Agent, and Human-in-the-Loop gates.
"""

from __future__ import annotations
import asyncio
import time
from typing import Any, Callable, Dict, List, Optional
from src.agents.chaos_agent import ChaosAgent
from src.agents.diagnostic_agent import DiagnosticAgent
from src.agents.repair_agent import RepairAgent
from src.core.models import (
    ActionType,
    EvidenceBundle,
    Incident,
    IncidentStatus,
    IncidentType,
    RepairExecutionResult,
    RepairPlan,
    utc_now,
)
from src.core.policy_engine import PolicyEngine
from src.core.state_store import StateStore
from src.target_env.mock_deploy_target import MockDeploymentTarget
from src.telemetry.anomaly_detector import AnomalyDetector
from src.telemetry.drift_detector import DriftDetector
from src.telemetry.ingestion import EventIngestionEngine


class Orchestrator:
    """Central state machine coordinating agent workflows and safety boundaries."""

    def __init__(
        self,
        state_store: Optional[StateStore] = None,
        policy_engine: Optional[PolicyEngine] = None,
        target_env: Optional[MockDeploymentTarget] = None,
    ):
        self.state_store = state_store or StateStore()
        self.policy_engine = policy_engine or PolicyEngine(state_store=self.state_store)
        self.target_env = target_env or MockDeploymentTarget()

        self.ingestion_engine = EventIngestionEngine(state_store=self.state_store)
        self.drift_detector = DriftDetector(state_store=self.state_store)
        self.anomaly_detector = AnomalyDetector(state_store=self.state_store)

        self.diagnostic_agent = DiagnosticAgent(state_store=self.state_store)
        self.repair_agent = RepairAgent(
            policy_engine=self.policy_engine,
            state_store=self.state_store,
            target_env=self.target_env,
        )
        self.chaos_agent = ChaosAgent(
            target_env=self.target_env,
            policy_engine=self.policy_engine,
            state_store=self.state_store,
        )

        # Real-time event subscriber callbacks (for WebSocket streaming to Dashboard)
        self._subscribers: List[Callable[[Dict[str, Any]], Any]] = []

    def subscribe(self, callback: Callable[[Dict[str, Any]], Any]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Dict[str, Any]], Any]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcasts events to registered WebSocket clients."""
        payload = {
            "type": event_type,
            "timestamp": utc_now().isoformat(),
            "data": data,
        }
        for sub in list(self._subscribers):
            try:
                res = sub(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    # --- Core Incident Lifecycle State Machine ---

    async def process_incident(
        self,
        incident: Incident,
        evidence_bundle: Optional[EvidenceBundle] = None,
    ) -> Incident:
        """Runs the closed-loop self-healing workflow for an incident."""
        start_time = time.time()
        correlation_id = incident.correlation_id

        # 1. Transition: DIAGNOSING
        incident.status = IncidentStatus.DIAGNOSING
        self.state_store.save_incident(incident)
        await self.broadcast_event("INCIDENT_STATUS_CHANGED", incident.model_dump())

        # Collect evidence if not provided
        if not evidence_bundle:
            evidence_bundle = self.diagnostic_agent.collect_evidence(
                incident=incident,
                logs_snippet=self.target_env.get_recent_logs(),
                metrics_summary=self.target_env.metrics,
            )
        incident.evidence_bundle = evidence_bundle

        # 2. Diagnostic Investigation & RCA
        hypothesis = self.diagnostic_agent.diagnose(evidence_bundle, incident)
        incident.hypothesis = hypothesis
        self.state_store.save_incident(incident)
        await self.broadcast_event("DIAGNOSIS_COMPLETED", hypothesis.model_dump())

        # 3. Transition: POLICY_EVALUATION & Repair Planning
        incident.status = IncidentStatus.POLICY_EVALUATION
        repair_plan = self.repair_agent.create_repair_plan(
            incident=incident,
            hypothesis=hypothesis,
            known_good_version=self.target_env.known_good_version,
            reference_config=self.target_env.reference_config,
        )
        incident.repair_plan = repair_plan
        self.state_store.save_incident(incident)
        await self.broadcast_event("REPAIR_PLAN_CREATED", repair_plan.model_dump())

        # 4. Check if Human Approval is required (SR-3, SR-11)
        val = repair_plan.policy_validation
        if val and val.requires_human_approval:
            incident.status = IncidentStatus.AWAITING_APPROVAL
            self.state_store.save_incident(incident)
            await self.broadcast_event("AWAITING_HUMAN_APPROVAL", {
                "incident_id": incident.incident_id,
                "correlation_id": correlation_id,
                "reasons": val.reasons,
                "plan": repair_plan.model_dump(),
            })
            return incident

        # 5. Autonomous Execution (if policy validation allows)
        if val and val.is_allowed and not self.policy_engine.is_emergency_stopped():
            incident.status = IncidentStatus.REPAIRING
            self.state_store.save_incident(incident)
            await self.broadcast_event("REPAIR_STARTED", {"incident_id": incident.incident_id})

            exec_result = self.repair_agent.execute_repair(
                incident=incident,
                plan=repair_plan,
                actor="RepairAgent:Autonomous",
            )
            incident.execution_result = exec_result

            # 6. Post-Repair Verification & Resolution (FR-7.6)
            if exec_result.post_verification_passed:
                incident.status = IncidentStatus.RESOLVED
                incident.resolution_timestamp = utc_now()
                incident.recovery_duration_seconds = round(time.time() - start_time, 2)
                
                # Auto-terminate linked chaos experiment as SELF_HEALED
                if incident.chaos_experiment_id:
                    self.chaos_agent.terminate_experiment(
                        incident.chaos_experiment_id, reason="SELF_HEALED"
                    )
            else:
                incident.status = IncidentStatus.ESCALATED
                incident.summary += " [Post-repair health check failed. Escalated to on-call engineer.]"

            self.state_store.save_incident(incident)
            await self.broadcast_event("INCIDENT_RESOLVED" if incident.status == IncidentStatus.RESOLVED else "INCIDENT_ESCALATED", incident.model_dump())

        return incident

    async def human_approve_repair(
        self,
        incident_id: str,
        operator_name: str = "DevOpsEngineer",
        comment: str = "Approved by operator",
    ) -> Optional[Incident]:
        """Operator human approval endpoint (FR-7.5, EI-6, UC-5)."""
        incident = self.state_store.get_incident(incident_id)
        if not incident or incident.status != IncidentStatus.AWAITING_APPROVAL:
            return None

        incident.human_approved = True
        incident.operator_comment = comment
        incident.status = IncidentStatus.REPAIRING
        self.state_store.save_incident(incident)

        self.state_store.append_audit_event(
            correlation_id=incident.correlation_id,
            actor=f"HumanOperator:{operator_name}",
            action_name="OPERATOR_APPROVED_REPAIR",
            details={"comment": comment, "incident_id": incident_id},
        )

        if incident.repair_plan:
            exec_result = self.repair_agent.execute_repair(
                incident=incident,
                plan=incident.repair_plan,
                actor=f"HumanOperator:{operator_name}",
            )
            incident.execution_result = exec_result

            if exec_result.post_verification_passed:
                incident.status = IncidentStatus.RESOLVED
                incident.resolution_timestamp = utc_now()
                incident.recovery_duration_seconds = round(
                    (incident.resolution_timestamp - incident.detection_timestamp).total_seconds(), 2
                )
                if incident.chaos_experiment_id:
                    self.chaos_agent.terminate_experiment(
                        incident.chaos_experiment_id, reason="SELF_HEALED"
                    )
            else:
                incident.status = IncidentStatus.ESCALATED

        self.state_store.save_incident(incident)
        await self.broadcast_event("INCIDENT_RESOLVED", incident.model_dump())
        return incident

    async def human_reject_repair(
        self,
        incident_id: str,
        operator_name: str = "DevOpsEngineer",
        comment: str = "Rejected by operator",
    ) -> Optional[Incident]:
        """Operator rejects automated repair plan; escalates incident."""
        incident = self.state_store.get_incident(incident_id)
        if not incident:
            return None

        incident.human_approved = False
        incident.operator_comment = comment
        incident.status = IncidentStatus.ESCALATED
        self.state_store.save_incident(incident)

        self.state_store.append_audit_event(
            correlation_id=incident.correlation_id,
            actor=f"HumanOperator:{operator_name}",
            action_name="OPERATOR_REJECTED_REPAIR",
            details={"comment": comment, "incident_id": incident_id},
        )
        await self.broadcast_event("INCIDENT_ESCALATED", incident.model_dump())
        return incident

    def trigger_emergency_stop(self, operator: str = "DevOpsEngineer") -> None:
        """Global Emergency Stop (Kill-Switch) per Section 7.2 & UC-5."""
        self.policy_engine.set_emergency_stop(True)
        # Abort running chaos experiments and restore baseline target
        self.chaos_agent.abort_all_experiments()

        self.state_store.append_audit_event(
            correlation_id="EMERGENCY-STOP",
            actor=f"HumanOperator:{operator}",
            action_name="GLOBAL_EMERGENCY_STOP_ACTIVATED",
            details={"action": "All agent actions halted, chaos experiments terminated."},
        )

    def release_emergency_stop(self, operator: str = "DevOpsEngineer") -> None:
        """Releases the emergency stop."""
        self.policy_engine.set_emergency_stop(False)
        self.state_store.append_audit_event(
            correlation_id="EMERGENCY-STOP",
            actor=f"HumanOperator:{operator}",
            action_name="GLOBAL_EMERGENCY_STOP_RELEASED",
            details={"action": "Normal autonomous policy resumed."},
        )
