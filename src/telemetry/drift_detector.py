"""Configuration Drift Detector Subsystem.

Implements FR-1.3, FR-3.1, FR-3.2, FR-3.3, EI-4.
Compares live configuration against Git reference state, classifies drift severity,
and captures snapshots for reversible patching.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from deepdiff import DeepDiff
from src.core.models import (
    DriftDiffItem,
    DriftFinding,
    DriftSeverity,
    Incident,
    IncidentStatus,
    IncidentType,
    generate_correlation_id,
    utc_now,
)
from src.core.state_store import StateStore


class DriftDetector:
    """Detects and classifies discrepancies between live configuration and GitOps reference."""

    # Key patterns associated with security sensitivity
    SECURITY_SENSITIVE_KEYS = {
        "allow_privileged_access",
        "privileged",
        "database_url",
        "secret",
        "password",
        "auth",
        "port",
        "tls",
        "ssl",
        "api_key",
    }

    # Key patterns associated with cosmetic metadata
    COSMETIC_KEYS = {"metadata", "labels", "annotations", "description", "comment"}

    def __init__(self, state_store: Optional[StateStore] = None):
        self.state_store = state_store or StateStore()

    def classify_key_severity(self, key_path: str) -> DriftSeverity:
        path_lower = key_path.lower()
        for sec_key in self.SECURITY_SENSITIVE_KEYS:
            if sec_key in path_lower:
                return DriftSeverity.CRITICAL_SECURITY
        for cos_key in self.COSMETIC_KEYS:
            if cos_key in path_lower:
                return DriftSeverity.COSMETIC
        return DriftSeverity.FUNCTIONAL

    def compare_configurations(
        self,
        service_name: str,
        live_config: Dict[str, Any],
        reference_config: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> Tuple[Optional[DriftFinding], Optional[Incident]]:
        """Deeply compares live config vs reference config, producing a DriftFinding if drift exists."""
        diff = DeepDiff(reference_config, live_config, ignore_order=True)

        if not diff:
            return None, None

        cid = correlation_id or generate_correlation_id()
        diff_items: List[DriftDiffItem] = []
        highest_severity = DriftSeverity.COSMETIC

        # 1. Values changed
        if "values_changed" in diff:
            for path, change in diff["values_changed"].items():
                severity = self.classify_key_severity(path)
                diff_items.append(
                    DriftDiffItem(
                        key_path=path,
                        declared_value=change.get("old_value"),
                        live_value=change.get("new_value"),
                        severity=severity,
                    )
                )
                if severity == DriftSeverity.CRITICAL_SECURITY:
                    highest_severity = DriftSeverity.CRITICAL_SECURITY
                elif (
                    severity == DriftSeverity.FUNCTIONAL
                    and highest_severity != DriftSeverity.CRITICAL_SECURITY
                ):
                    highest_severity = DriftSeverity.FUNCTIONAL

        # 2. Items added (in live but not declared)
        if "dictionary_item_added" in diff:
            for path in diff["dictionary_item_added"]:
                severity = self.classify_key_severity(str(path))
                diff_items.append(
                    DriftDiffItem(
                        key_path=str(path),
                        declared_value=None,
                        live_value="[Added in live]",
                        severity=severity,
                    )
                )
                if severity == DriftSeverity.CRITICAL_SECURITY:
                    highest_severity = DriftSeverity.CRITICAL_SECURITY
                elif (
                    severity == DriftSeverity.FUNCTIONAL
                    and highest_severity != DriftSeverity.CRITICAL_SECURITY
                ):
                    highest_severity = DriftSeverity.FUNCTIONAL

        # 3. Items removed (in declared but missing in live)
        if "dictionary_item_removed" in diff:
            for path in diff["dictionary_item_removed"]:
                severity = self.classify_key_severity(str(path))
                diff_items.append(
                    DriftDiffItem(
                        key_path=str(path),
                        declared_value="[Declared in reference]",
                        live_value=None,
                        severity=severity,
                    )
                )
                if severity == DriftSeverity.CRITICAL_SECURITY:
                    highest_severity = DriftSeverity.CRITICAL_SECURITY
                elif (
                    severity == DriftSeverity.FUNCTIONAL
                    and highest_severity != DriftSeverity.CRITICAL_SECURITY
                ):
                    highest_severity = DriftSeverity.FUNCTIONAL

        finding = DriftFinding(
            correlation_id=cid,
            service_name=service_name,
            live_snapshot=live_config,
            reference_snapshot=reference_config,
            diff_items=diff_items,
            overall_severity=highest_severity,
            timestamp=utc_now(),
        )

        # Save snapshots to state store for reversible rollback/patching (FR-3.3)
        self.state_store.save_config_snapshot(
            service_name=service_name,
            config_data=live_config,
            snapshot_type="LIVE_DRIFTED",
        )
        self.state_store.save_config_snapshot(
            service_name=service_name,
            config_data=reference_config,
            snapshot_type="REFERENCE",
        )

        incident = Incident(
            correlation_id=cid,
            service_name=service_name,
            incident_type=IncidentType.CONFIGURATION_DRIFT,
            status=IncidentStatus.DETECTED,
            summary=f"Configuration drift detected on '{service_name}' ({len(diff_items)} field(s) drifted, severity: {highest_severity.value}).",
            detection_timestamp=utc_now(),
        )

        self.state_store.save_incident(incident)
        self.state_store.append_audit_event(
            correlation_id=cid,
            actor="DriftDetector",
            action_name="CONFIGURATION_DRIFT_DETECTED",
            details={
                "service_name": service_name,
                "overall_severity": highest_severity.value,
                "diff_count": len(diff_items),
                "diff_keys": [item.key_path for item in diff_items],
            },
        )

        return finding, incident
