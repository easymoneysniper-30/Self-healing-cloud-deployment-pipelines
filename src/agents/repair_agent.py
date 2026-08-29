"""Repair Agent Subsystem.

Implements FR-7.1, FR-7.2, FR-7.3, FR-7.4, FR-7.5, FR-7.6, FR-7.7, SR-1, SR-4, SR-6, SR-8, NFR-8.
Generates policy-constrained repair plans, executes rollbacks and config patches,
runs post-repair health verification, and records tamper-evident audit trails.
"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple
from src.core.models import (
    ActionType,
    Incident,
    IncidentStatus,
    PolicyValidationResult,
    RepairAction,
    RepairExecutionResult,
    RepairPlan,
    RollbackCheckpoint,
    RootCauseHypothesis,
    utc_now,
)
from src.core.policy_engine import PolicyEngine
from src.core.state_store import StateStore
from src.target_env.mock_deploy_target import MockDeploymentTarget


class RepairAgent:
    """Proposes, validates, and executes reversible remediations."""

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        state_store: Optional[StateStore] = None,
        target_env: Optional[MockDeploymentTarget] = None,
    ):
        self.state_store = state_store or StateStore()
        self.policy_engine = policy_engine or PolicyEngine(state_store=self.state_store)
        self.target_env = target_env or MockDeploymentTarget()

    def create_repair_plan(
        self,
        incident: Incident,
        hypothesis: RootCauseHypothesis,
        known_good_version: Optional[str] = None,
        reference_config: Optional[Dict[str, Any]] = None,
    ) -> RepairPlan:
        """Constructs a reversible RepairPlan based on the diagnosed root cause hypothesis."""
        actions: List[RepairAction] = []
        kg_ver = known_good_version or self.target_env.known_good_version
        ref_cfg = reference_config or self.target_env.reference_config

        # 1. Primary Mechanism: Rollback
        if hypothesis.recommended_action == ActionType.ROLLBACK_DEPLOYMENT:
            checkpoint = RollbackCheckpoint(
                service_name=incident.service_name,
                known_good_version=kg_ver,
                known_good_config=ref_cfg,
                captured_at=utc_now(),
            )
            actions.append(
                RepairAction(
                    action_type=ActionType.ROLLBACK_DEPLOYMENT,
                    service_name=incident.service_name,
                    target_version=kg_ver,
                    rollback_checkpoint=checkpoint,
                    rationale=(
                        f"Revert '{incident.service_name}' from degraded state to last verified stable version '{kg_ver}'."
                    ),
                    is_reversible=True,
                )
            )

        # 2. Secondary Mechanism: Configuration Patch
        elif hypothesis.recommended_action == ActionType.PATCH_CONFIG:
            live_snapshot = self.target_env.get_live_config()
            checkpoint = RollbackCheckpoint(
                service_name=incident.service_name,
                known_good_version=self.target_env.current_version,
                known_good_config=live_snapshot,
                captured_at=utc_now(),
            )
            actions.append(
                RepairAction(
                    action_type=ActionType.PATCH_CONFIG,
                    service_name=incident.service_name,
                    target_config_patch=ref_cfg,
                    rollback_checkpoint=checkpoint,
                    rationale=(
                        f"Apply configuration patch to reconcile drifted parameters on '{incident.service_name}' with declared GitOps reference state."
                    ),
                    is_reversible=True,
                )
            )

        # 3. Restart Pod/Service
        elif hypothesis.recommended_action == ActionType.RESTART_POD_OR_SERVICE:
            checkpoint = RollbackCheckpoint(
                service_name=incident.service_name,
                known_good_version=self.target_env.current_version,
                known_good_config=self.target_env.get_live_config(),
                captured_at=utc_now(),
            )
            actions.append(
                RepairAction(
                    action_type=ActionType.RESTART_POD_OR_SERVICE,
                    service_name=incident.service_name,
                    rollback_checkpoint=checkpoint,
                    rationale=f"Restart unresponsive instances of '{incident.service_name}'.",
                    is_reversible=True,
                )
            )

        # 4. Manual Escalation
        else:
            actions.append(
                RepairAction(
                    action_type=ActionType.MANUAL_ESCALATION,
                    service_name=incident.service_name,
                    rationale=hypothesis.explanation,
                    is_reversible=True,
                )
            )

        # Validate first action against Policy Engine (SR-1, SR-3, SR-4, SR-7, SR-9, SR-10)
        primary_action = actions[0]
        validation_result = self.policy_engine.validate_repair_action(
            action=primary_action,
            confidence_score=hypothesis.confidence_score,
        )

        plan = RepairPlan(
            correlation_id=incident.correlation_id,
            proposed_actions=actions,
            policy_validation=validation_result,
            status="AWAITING_APPROVAL" if validation_result.requires_human_approval else "AUTO_APPROVED",
            created_at=utc_now(),
        )

        # Audit record
        self.state_store.append_audit_event(
            correlation_id=incident.correlation_id,
            actor="RepairAgent",
            action_name="REPAIR_PLAN_CREATED",
            details={
                "service_name": incident.service_name,
                "action_type": primary_action.action_type.value,
                "requires_human_approval": validation_result.requires_human_approval,
                "is_allowed": validation_result.is_allowed,
                "reasons": validation_result.reasons,
                "dry_run": validation_result.dry_run,
            },
        )

        return plan

    def execute_repair(
        self,
        incident: Incident,
        plan: RepairPlan,
        actor: str = "RepairAgent",
    ) -> RepairExecutionResult:
        """Executes the approved repair action, runs post-repair verification, and handles circuit breakers."""
        if not plan.proposed_actions:
            return RepairExecutionResult(
                plan_id=plan.plan_id,
                correlation_id=incident.correlation_id,
                action_type=ActionType.MANUAL_ESCALATION,
                success=False,
                details="No actions defined in repair plan.",
                duration_seconds=0.0,
                post_verification_passed=False,
            )

        action = plan.proposed_actions[0]
        start_time = time.time()

        # Handle Dry-Run Mode (SR-5)
        if plan.policy_validation and plan.policy_validation.dry_run:
            duration = time.time() - start_time
            self.state_store.append_audit_event(
                correlation_id=incident.correlation_id,
                actor=actor,
                action_name="REPAIR_EXECUTION_DRY_RUN_SKIPPED",
                details={"action_type": action.action_type.value, "service_name": action.service_name},
            )
            return RepairExecutionResult(
                plan_id=plan.plan_id,
                correlation_id=incident.correlation_id,
                action_type=action.action_type,
                success=True,
                details=f"[DRY RUN] Would have executed {action.action_type.value} on '{action.service_name}'.",
                duration_seconds=duration,
                post_verification_passed=True,
            )

        # Record action in policy engine for rate limiting (SR-10)
        self.policy_engine.record_action_executed(action.service_name)

        # Execute on deployment target
        exec_success = False
        exec_details = ""

        if action.action_type == ActionType.ROLLBACK_DEPLOYMENT:
            target_v = action.target_version or self.target_env.known_good_version
            exec_success = self.target_env.rollback_to_version(target_v)
            exec_details = f"Rolled back service '{action.service_name}' to version '{target_v}'."

        elif action.action_type == ActionType.PATCH_CONFIG:
            patch = action.target_config_patch or self.target_env.reference_config
            exec_success = self.target_env.apply_config_patch(patch)
            exec_details = f"Applied configuration patch reconciling reference state on '{action.service_name}'."

        elif action.action_type == ActionType.RESTART_POD_OR_SERVICE:
            exec_success = self.target_env.restart_service()
            exec_details = f"Restarted service instances for '{action.service_name}'."

        elif action.action_type == ActionType.MANUAL_ESCALATION:
            exec_success = False
            exec_details = f"Escalated to human operator for service '{action.service_name}'."

        # Post-Repair Health Verification (FR-7.6)
        health_status = self.target_env.get_health_status()
        post_verified = exec_success and health_status["is_healthy"]

        duration = time.time() - start_time

        # Update circuit breaker if repair failed (SR-9)
        if not post_verified and action.action_type != ActionType.MANUAL_ESCALATION:
            self.state_store.record_repair_failure(action.service_name)
        else:
            self.state_store.reset_circuit_breaker(action.service_name)

        result = RepairExecutionResult(
            plan_id=plan.plan_id,
            correlation_id=incident.correlation_id,
            action_type=action.action_type,
            success=exec_success,
            details=exec_details,
            duration_seconds=round(duration, 3),
            post_verification_passed=post_verified,
            health_metrics=health_status.get("metrics", {}),
            executed_at=utc_now(),
        )

        # Append audit log
        self.state_store.append_audit_event(
            correlation_id=incident.correlation_id,
            actor=actor,
            action_name="REPAIR_ACTION_EXECUTED",
            details={
                "action_type": action.action_type.value,
                "service_name": action.service_name,
                "execution_success": exec_success,
                "post_verification_passed": post_verified,
                "duration_seconds": result.duration_seconds,
            },
        )

        return result
