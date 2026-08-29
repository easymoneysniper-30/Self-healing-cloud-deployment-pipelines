"""Policy Engine and Safety Envelope Enforcer.

Enforces Safety Requirements SR-1 through SR-11 (PRD Section 12 & Section 8.7).
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from src.core.models import (
    ActionType,
    PolicyValidationResult,
    RepairAction,
    utc_now,
)
from src.core.state_store import StateStore


class PolicyEngine:
    """Evaluates proposed repair and chaos actions against safety policies."""

    def __init__(
        self,
        config_path: str = "config/default_policy.yaml",
        state_store: Optional[StateStore] = None,
    ):
        self.config_path = Path(config_path)
        self.state_store = state_store or StateStore()
        self.policy = self._load_policy()
        # In-memory execution timestamps for rate limiting: {service_name: [dt1, dt2]}
        self._action_timestamps: Dict[str, List[datetime]] = {}
        self._emergency_stop: bool = False

    def _load_policy(self) -> Dict[str, Any]:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        # Fallback default policy
        return {
            "allowlisted_actions": [
                ActionType.ROLLBACK_DEPLOYMENT.value,
                ActionType.PATCH_CONFIG.value,
                ActionType.RESTART_POD_OR_SERVICE.value,
            ],
            "confidence_threshold": 0.80,
            "allowed_namespaces": [
                "demo-payments-service",
                "demo-checkout-service",
                "demo-auth-service",
                "payments-service",
                "checkout-service",
                "auth-service",
            ],
            "rate_limit": {"max_actions_per_window": 3, "window_seconds": 120},
            "circuit_breaker": {
                "consecutive_failure_threshold": 3,
                "cooldown_seconds": 300,
            },
            "dry_run": False,
            "emergency_stop_active": False,
        }

    def reload_policy(self) -> None:
        self.policy = self._load_policy()

    def set_emergency_stop(self, active: bool) -> None:
        self._emergency_stop = active

    def is_emergency_stopped(self) -> bool:
        return self._emergency_stop or self.policy.get("emergency_stop_active", False)

    def validate_repair_action(
        self,
        action: RepairAction,
        confidence_score: float,
        dry_run_override: Optional[bool] = None,
    ) -> PolicyValidationResult:
        """Validates a proposed repair action against all safety rules (SR-1 to SR-11)."""
        reasons: List[str] = []
        is_allowed = True
        requires_human_approval = False
        violates_blast_radius = False
        circuit_breaker_tripped = False
        rate_limit_exceeded = False

        dry_run = (
            dry_run_override
            if dry_run_override is not None
            else self.policy.get("dry_run", False)
        )

        # 1. Emergency Stop Check (Section 7.2)
        if self.is_emergency_stopped():
            reasons.append("EMERGENCY_STOP is currently ACTIVE. All actions are blocked.")
            return PolicyValidationResult(
                is_allowed=False,
                requires_human_approval=True,
                reasons=reasons,
                dry_run=dry_run,
            )

        # 2. Allowlist Check (SR-4)
        allowlisted = self.policy.get("allowlisted_actions", [])
        if action.action_type.value not in allowlisted:
            is_allowed = False
            requires_human_approval = True
            reasons.append(
                f"Action '{action.action_type.value}' is not in the allowlist ({allowlisted}). Escalating to human."
            )

        # 3. Blast Radius Check (SR-7)
        allowed_targets = self.policy.get("allowed_namespaces", [])
        if action.service_name not in allowed_targets:
            violates_blast_radius = True
            is_allowed = False
            requires_human_approval = True
            reasons.append(
                f"Target '{action.service_name}' is outside authorized namespaces ({allowed_targets}). Blast radius violation."
            )

        # 4. Rollback Checkpoint Requirement (SR-6)
        if action.action_type in [
            ActionType.ROLLBACK_DEPLOYMENT,
            ActionType.PATCH_CONFIG,
        ]:
            if not action.rollback_checkpoint:
                # If no checkpoint provided, require human approval or deny
                requires_human_approval = True
                reasons.append(
                    "No rollback checkpoint attached to repair action. Human approval required to ensure reversibility."
                )

        # 5. Circuit Breaker Check (SR-9)
        cb_state = self.state_store.get_circuit_breaker(action.service_name)
        if cb_state.get("is_tripped"):
            circuit_breaker_tripped = True
            is_allowed = False
            requires_human_approval = True
            reasons.append(
                f"Circuit breaker tripped for '{action.service_name}' ({cb_state.get('consecutive_failures')} consecutive failures). Manual intervention required."
            )

        # 6. Rate Limit Check (SR-10)
        rate_limit_cfg = self.policy.get(
            "rate_limit", {"max_actions_per_window": 3, "window_seconds": 120}
        )
        max_actions = rate_limit_cfg.get("max_actions_per_window", 3)
        window_sec = rate_limit_cfg.get("window_seconds", 120)

        now = utc_now()
        timestamps = self._action_timestamps.get(action.service_name, [])
        valid_window_start = now - timedelta(seconds=window_sec)
        # Purge old timestamps
        recent_timestamps = [t for t in timestamps if t >= valid_window_start]
        self._action_timestamps[action.service_name] = recent_timestamps

        if len(recent_timestamps) >= max_actions:
            rate_limit_exceeded = True
            is_allowed = False
            requires_human_approval = True
            reasons.append(
                f"Rate limit exceeded for '{action.service_name}' ({len(recent_timestamps)} actions in {window_sec}s). Human approval required."
            )

        # 7. Confidence Score Threshold Check (SR-3, SR-11)
        conf_threshold = self.policy.get("confidence_threshold", 0.80)
        confidence_met = confidence_score >= conf_threshold
        if not confidence_met:
            requires_human_approval = True
            reasons.append(
                f"Diagnostic confidence ({confidence_score * 100:.1f}%) is below autonomy threshold ({conf_threshold * 100:.1f}%). Escalated to operator approval."
            )

        if not reasons:
            reasons.append(
                f"Action '{action.action_type.value}' validated successfully. Confidence {confidence_score * 100:.1f}% >= {conf_threshold * 100:.1f}%."
            )

        return PolicyValidationResult(
            is_allowed=is_allowed and not (circuit_breaker_tripped or rate_limit_exceeded or violates_blast_radius),
            requires_human_approval=requires_human_approval,
            reasons=reasons,
            violates_blast_radius=violates_blast_radius,
            confidence_met=confidence_met,
            circuit_breaker_tripped=circuit_breaker_tripped,
            rate_limit_exceeded=rate_limit_exceeded,
            dry_run=dry_run,
        )

    def record_action_executed(self, service_name: str) -> None:
        """Records an action timestamp for rate limiting."""
        now = utc_now()
        if service_name not in self._action_timestamps:
            self._action_timestamps[service_name] = []
        self._action_timestamps[service_name].append(now)
