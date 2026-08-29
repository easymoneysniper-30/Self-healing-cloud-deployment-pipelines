"""Chaos Agent Subsystem.

Implements FR-6.1, FR-6.2, FR-6.3, FR-6.4, FR-6.5, FR-6.6, OBJ-3, SR-3, SR-7.
Defines, schedules, executes, and safely aborts controlled resilience experiments.
"""

from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional
from src.core.models import (
    ChaosExperiment,
    generate_correlation_id,
    utc_now,
)
from src.core.policy_engine import PolicyEngine
from src.core.state_store import StateStore
from src.target_env.mock_deploy_target import MockDeploymentTarget


class ChaosAgent:
    """Injects controlled failure scenarios to validate resilience and repair logic."""

    SUPPORTED_FAULTS = [
        "DEPLOYMENT_CRASH",
        "CONFIG_DRIFT",
        "LATENCY_SPIKE",
        "RESOURCE_EXHAUSTION",
    ]

    def __init__(
        self,
        target_env: Optional[MockDeploymentTarget] = None,
        policy_engine: Optional[PolicyEngine] = None,
        state_store: Optional[StateStore] = None,
    ):
        self.target_env = target_env or MockDeploymentTarget()
        self.state_store = state_store or StateStore()
        self.policy_engine = policy_engine or PolicyEngine(state_store=self.state_store)
        self.active_experiments: Dict[str, ChaosExperiment] = {}

    def create_experiment(
        self,
        name: str,
        fault_type: str,
        target_service: Optional[str] = None,
        duration_seconds: int = 30,
        params: Optional[Dict[str, Any]] = None,
    ) -> ChaosExperiment:
        """Defines a new controlled chaos experiment."""
        target = target_service or self.target_env.service_name
        if fault_type not in self.SUPPORTED_FAULTS:
            raise ValueError(
                f"Unsupported fault type '{fault_type}'. Must be one of {self.SUPPORTED_FAULTS}."
            )

        correlation_id = generate_correlation_id()
        experiment = ChaosExperiment(
            correlation_id=correlation_id,
            name=name,
            fault_type=fault_type,
            target_service=target,
            duration_seconds=duration_seconds,
            params=params or {},
            status="CREATED",
        )

        self.state_store.save_chaos_experiment(experiment)
        self.state_store.append_audit_event(
            correlation_id=correlation_id,
            actor="ChaosAgent",
            action_name="CHAOS_EXPERIMENT_CREATED",
            details={
                "experiment_id": experiment.experiment_id,
                "name": name,
                "fault_type": fault_type,
                "target_service": target,
                "duration_seconds": duration_seconds,
            },
        )
        return experiment

    def inject_fault(self, experiment: ChaosExperiment) -> bool:
        """Executes fault injection after validating blast radius and emergency stop."""
        # 1. Check Emergency Stop
        if self.policy_engine.is_emergency_stopped():
            experiment.status = "BLOCKED_EMERGENCY_STOP"
            self.state_store.save_chaos_experiment(experiment)
            return False

        # 2. Check Blast Radius & Target Scoping (FR-6.3, SR-7)
        allowed_targets = self.policy_engine.policy.get("allowed_namespaces", [])
        if experiment.target_service not in allowed_targets:
            experiment.status = "BLOCKED_BLAST_RADIUS"
            self.state_store.save_chaos_experiment(experiment)
            self.state_store.append_audit_event(
                correlation_id=experiment.correlation_id,
                actor="ChaosAgent",
                action_name="CHAOS_EXPERIMENT_BLOCKED",
                details={"reason": "Blast radius violation", "target": experiment.target_service},
            )
            return False

        experiment.status = "RUNNING"
        experiment.started_at = utc_now()
        self.active_experiments[experiment.experiment_id] = experiment

        # Inject into target environment
        self.target_env.inject_fault(
            fault_type=experiment.fault_type, params=experiment.params
        )

        self.state_store.save_chaos_experiment(experiment)
        self.state_store.append_audit_event(
            correlation_id=experiment.correlation_id,
            actor="ChaosAgent",
            action_name="CHAOS_FAULT_INJECTED",
            details={
                "experiment_id": experiment.experiment_id,
                "fault_type": experiment.fault_type,
                "target_service": experiment.target_service,
            },
        )
        return True

    def terminate_experiment(
        self, experiment_id: str, reason: str = "COMPLETED"
    ) -> Optional[ChaosExperiment]:
        """Safely terminates a running chaos experiment and restores nominal state (FR-6.5)."""
        experiment = self.active_experiments.get(
            experiment_id
        ) or self.state_store.get_chaos_experiment(experiment_id)
        if not experiment:
            return None

        # Revert faults in target environment
        self.target_env.clear_faults()

        experiment.status = reason
        experiment.ended_at = utc_now()
        experiment.repaired_by_system = (reason == "SELF_HEALED")
        if experiment.started_at and not experiment.recovery_time_seconds:
            experiment.recovery_time_seconds = round(
                (experiment.ended_at - experiment.started_at).total_seconds(), 2
            )

        self.active_experiments.pop(experiment_id, None)
        self.state_store.save_chaos_experiment(experiment)

        self.state_store.append_audit_event(
            correlation_id=experiment.correlation_id,
            actor="ChaosAgent",
            action_name="CHAOS_EXPERIMENT_TERMINATED",
            details={
                "experiment_id": experiment.experiment_id,
                "reason": reason,
                "recovery_time_seconds": experiment.recovery_time_seconds,
            },
        )
        return experiment

    def abort_all_experiments(self) -> int:
        """Emergency stop: terminates all active experiments immediately."""
        aborted_count = 0
        exp_ids = list(self.active_experiments.keys())
        for exp_id in exp_ids:
            self.terminate_experiment(exp_id, reason="SAFETY_ABORTED")
            aborted_count += 1
        self.target_env.clear_faults()
        return aborted_count
