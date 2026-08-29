"""Pipeline Event Ingestion Subsystem.

Implements FR-1.1, FR-1.2, FR-1.5, EI-1.
Ingests CI/CD pipeline lifecycle events and dispatches incidents with correlation IDs.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from src.core.models import (
    DeploymentEvent,
    DeploymentLifecycleEvent,
    FailureRecord,
    Incident,
    IncidentStatus,
    IncidentType,
    generate_correlation_id,
    utc_now,
)
from src.core.state_store import StateStore


class EventIngestionEngine:
    """Ingests CI/CD webhooks and monitoring events, normalizing them into internal models."""

    def __init__(self, state_store: Optional[StateStore] = None):
        self.state_store = state_store or StateStore()

    def ingest_ci_event(self, payload: Dict[str, Any]) -> Tuple[DeploymentEvent, Optional[Incident]]:
        """Processes an incoming CI/CD webhook event."""
        event_type_str = payload.get("event_type", "SUCCESS").upper()
        try:
            event_type = DeploymentLifecycleEvent(event_type_str)
        except ValueError:
            event_type = DeploymentLifecycleEvent.FAILURE

        correlation_id = payload.get("correlation_id") or generate_correlation_id()
        service_name = payload.get("service_name") or "unknown-service"
        version = payload.get("version") or "v1.0.0"
        pipeline_id = payload.get("pipeline_id") or f"pipe-{correlation_id[-6:]}"
        commit_sha = payload.get("commit_sha") or "unknown-sha"

        dep_event = DeploymentEvent(
            correlation_id=correlation_id,
            pipeline_id=pipeline_id,
            service_name=service_name,
            version=version,
            commit_sha=commit_sha,
            event_type=event_type,
            timestamp=utc_now(),
            details=payload.get("details", {}),
        )

        incident: Optional[Incident] = None

        # If the CI/CD pipeline failed or reported a post-deployment crash
        if event_type == DeploymentLifecycleEvent.FAILURE:
            failure_record = FailureRecord(
                correlation_id=correlation_id,
                service_name=service_name,
                version=version,
                error_type=payload.get("error_type", "DeploymentRolloutFailed"),
                error_message=payload.get(
                    "error_message",
                    f"Deployment {version} failed health check or returned non-zero exit code.",
                ),
                exit_code=payload.get("exit_code", 1),
                logs_snippet=payload.get(
                    "logs_snippet",
                    "[ERROR] Container failed to start: CrashLoopBackOff. Health probe timeout.",
                ),
            )

            incident = Incident(
                correlation_id=correlation_id,
                service_name=service_name,
                incident_type=IncidentType.DEPLOYMENT_FAILURE,
                status=IncidentStatus.DETECTED,
                summary=f"Deployment rollout failure detected for '{service_name}' ({version}).",
                detection_timestamp=utc_now(),
            )

            # Record in state store
            self.state_store.save_incident(incident)
            self.state_store.append_audit_event(
                correlation_id=correlation_id,
                actor="EventIngestion",
                action_name="CI_DEPLOYMENT_FAILURE_INGESTED",
                details={
                    "service_name": service_name,
                    "version": version,
                    "pipeline_id": pipeline_id,
                    "error_message": failure_record.error_message,
                },
            )
        else:
            # Successful deployment event logged in audit trail
            self.state_store.append_audit_event(
                correlation_id=correlation_id,
                actor="EventIngestion",
                action_name=f"CI_DEPLOYMENT_{event_type.value}",
                details={
                    "service_name": service_name,
                    "version": version,
                    "pipeline_id": pipeline_id,
                    "commit_sha": commit_sha,
                },
            )

        return dep_event, incident
