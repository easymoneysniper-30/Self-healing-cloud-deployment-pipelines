"""FastAPI Server for Self-Healing Cloud Deployment Pipelines.

Exposes REST APIs, Webhook receivers, HITL approval endpoints,
Chaos injection triggers, Audit trail explorer, LLM config, and WebSocket real-time event streaming.
"""

from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.agents.llm_provider import LLMDiagnosticProvider
from src.core.models import (
    ChaosExperiment,
    Incident,
    IncidentStatus,
    utc_now,
)
from src.core.orchestrator import Orchestrator
from src.core.policy_engine import PolicyEngine
from src.core.state_store import StateStore
from src.target_env.mock_deploy_target import MockDeploymentTarget


# Global singleton instances
state_store = StateStore()
policy_engine = PolicyEngine(state_store=state_store)
target_env = MockDeploymentTarget()
orchestrator = Orchestrator(
    state_store=state_store, policy_engine=policy_engine, target_env=target_env
)

app = FastAPI(
    title="Self-Healing Cloud Deployment Pipelines",
    description="Agentic, closed-loop CI/CD deployment failure detection, diagnosis, and policy-constrained repair system.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


# --- Request Body Models ---

class CIWebhookPayload(BaseModel):
    service_name: str = "payments-service"
    version: str = "v2.1.0"
    pipeline_id: Optional[str] = None
    commit_sha: str = "f7c9e12"
    event_type: str = "FAILURE"  # START, SUCCESS, FAILURE
    error_type: Optional[str] = "DeploymentRolloutFailed"
    error_message: Optional[str] = "Container crashed on startup (Exit Code 137 / OOM)."
    logs_snippet: Optional[str] = "[ERROR] CrashLoopBackOff: failed health check on :8080/health"
    details: Dict[str, Any] = {}


class AnomalyPayload(BaseModel):
    service_name: str = "payments-service"
    metrics: Dict[str, float]
    recent_deployment_time: Optional[float] = None


class DriftCheckPayload(BaseModel):
    service_name: str = "payments-service"


class HumanApprovalPayload(BaseModel):
    operator_name: str = "DevOpsOperator"
    comment: str = "Approved by operator"


class ChaosInjectPayload(BaseModel):
    name: str = "Simulated Deployment Crash"
    fault_type: str = "DEPLOYMENT_CRASH"
    target_service: str = "payments-service"
    duration_seconds: int = 30
    params: Dict[str, Any] = {}


class EmergencyStopPayload(BaseModel):
    active: bool
    operator_name: str = "DevOpsOperator"


class LLMConfigPayload(BaseModel):
    provider: str = "gemini"  # gemini, openai, heuristic
    api_key: Optional[str] = ""
    model: Optional[str] = ""


# --- WebSocket Manager ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


ws_manager = ConnectionManager()


# Register orchestrator broadcast listener
async def _ws_broadcast_adapter(payload: Dict[str, Any]):
    await ws_manager.broadcast(payload)


orchestrator.subscribe(_ws_broadcast_adapter)


# --- REST API Endpoints ---

@app.get("/api/status")
async def get_system_status():
    """Returns overall framework, LLM, and target environment status."""
    health = target_env.get_health_status()
    cb = state_store.get_circuit_breaker(target_env.service_name)
    integrity_ok, integrity_err = state_store.verify_audit_log_integrity()
    incidents = state_store.list_incidents(limit=5)
    active_chaos = [
        exp
        for exp in state_store.list_chaos_experiments(limit=10)
        if exp.status == "RUNNING"
    ]
    llm_info = orchestrator.diagnostic_agent.llm_provider.get_status_info()

    return {
        "framework": "Self-Healing Cloud Deployment Pipelines v1.0",
        "emergency_stop_active": policy_engine.is_emergency_stopped(),
        "dry_run": policy_engine.policy.get("dry_run", False),
        "confidence_threshold": policy_engine.policy.get("confidence_threshold", 0.80),
        "target_service": health,
        "circuit_breaker": cb,
        "audit_integrity": {
            "verified": integrity_ok,
            "error": integrity_err,
        },
        "llm_diagnostics": llm_info,
        "active_chaos_count": len(active_chaos),
        "recent_incidents": len(incidents),
        "server_time": utc_now().isoformat(),
    }


@app.get("/api/llm/status")
async def get_llm_status():
    """Returns diagnostic LLM provider status."""
    return orchestrator.diagnostic_agent.llm_provider.get_status_info()


@app.post("/api/llm/config")
async def configure_llm(payload: LLMConfigPayload):
    """Updates runtime LLM Diagnostic Provider credentials and model."""
    model = payload.model
    if (
        not model
        or model == "heuristic-rules"
        or (payload.provider == "gemini" and "gemini" not in model.lower())
        or (payload.provider == "openai" and "gpt" not in model.lower())
    ):
        if payload.provider == "gemini":
            model = "gemini-3-flash-preview"
        elif payload.provider == "openai":
            model = "gpt-4o-mini"
        else:
            model = "heuristic-rules"

    provider = LLMDiagnosticProvider(
        provider=payload.provider,
        api_key=payload.api_key,
        model=model,
    )
    orchestrator.diagnostic_agent.llm_provider = provider
    status_info = provider.get_status_info()

    await ws_manager.broadcast({"type": "LLM_CONFIG_UPDATED", "data": status_info})
    return {"status": "LLM_PROVIDER_UPDATED", "config": status_info}


@app.post("/api/webhook/ci")
async def ingest_ci_webhook(payload: CIWebhookPayload):
    """Receives CI/CD webhook event, creates incident if failure, and triggers diagnosis."""
    dep_event, incident = orchestrator.ingestion_engine.ingest_ci_event(payload.model_dump())
    if incident:
        asyncio.create_task(orchestrator.process_incident(incident))
        return {
            "status": "INCIDENT_TRIGGERED",
            "correlation_id": incident.correlation_id,
            "incident_id": incident.incident_id,
            "event": dep_event.model_dump(),
        }
    return {
        "status": "DEPLOYMENT_RECORDED",
        "correlation_id": dep_event.correlation_id,
        "event": dep_event.model_dump(),
    }


@app.post("/api/telemetry/drift-check")
async def run_drift_check(payload: DriftCheckPayload):
    """Triggers GitOps configuration drift comparison against live target."""
    live_cfg = target_env.get_live_config()
    ref_cfg = target_env.reference_config

    finding, incident = orchestrator.drift_detector.compare_configurations(
        service_name=payload.service_name,
        live_config=live_cfg,
        reference_config=ref_cfg,
    )

    if incident and finding:
        evidence = orchestrator.diagnostic_agent.collect_evidence(
            incident=incident,
            drift_findings=[finding],
            logs_snippet=target_env.get_recent_logs(),
        )
        asyncio.create_task(orchestrator.process_incident(incident, evidence_bundle=evidence))
        return {
            "status": "DRIFT_DETECTED_AND_PROCESSING",
            "incident_id": incident.incident_id,
            "correlation_id": incident.correlation_id,
            "severity": finding.overall_severity.value,
            "diff_items": [d.model_dump() for d in finding.diff_items],
        }

    return {"status": "NO_DRIFT_DETECTED", "service_name": payload.service_name}


@app.post("/api/telemetry/metrics")
async def ingest_metrics(payload: AnomalyPayload):
    """Ingests runtime metrics and triggers anomaly detection."""
    anomalies, incident = orchestrator.anomaly_detector.analyze_metrics(
        service_name=payload.service_name,
        metrics=payload.metrics,
        recent_deployment_time=payload.recent_deployment_time,
    )

    if incident and anomalies:
        evidence = orchestrator.diagnostic_agent.collect_evidence(
            incident=incident,
            anomaly_findings=anomalies,
            logs_snippet=target_env.get_recent_logs(),
            metrics_summary=payload.metrics,
        )
        asyncio.create_task(orchestrator.process_incident(incident, evidence_bundle=evidence))
        return {
            "status": "ANOMALY_DETECTED_AND_PROCESSING",
            "incident_id": incident.incident_id,
            "correlation_id": incident.correlation_id,
            "anomalies": [a.model_dump() for a in anomalies],
        }

    return {"status": "METRICS_HEALTHY", "service_name": payload.service_name}


@app.get("/api/incidents")
async def list_incidents(status: Optional[str] = None, limit: int = 50):
    return state_store.list_incidents(status=status, limit=limit)


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    incident = state_store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.post("/api/incidents/{incident_id}/approve")
async def approve_incident(incident_id: str, payload: HumanApprovalPayload):
    incident = await orchestrator.human_approve_repair(
        incident_id=incident_id,
        operator_name=payload.operator_name,
        comment=payload.comment,
    )
    if not incident:
        raise HTTPException(
            status_code=400,
            detail="Incident not found or not in AWAITING_APPROVAL status.",
        )
    return {"status": "REPAIR_APPROVED_AND_EXECUTED", "incident": incident}


@app.post("/api/incidents/{incident_id}/reject")
async def reject_incident(incident_id: str, payload: HumanApprovalPayload):
    incident = await orchestrator.human_reject_repair(
        incident_id=incident_id,
        operator_name=payload.operator_name,
        comment=payload.comment,
    )
    if not incident:
        raise HTTPException(status_code=400, detail="Incident not found.")
    return {"status": "REPAIR_REJECTED", "incident": incident}


@app.post("/api/chaos/inject")
async def inject_chaos(payload: ChaosInjectPayload):
    try:
        exp = orchestrator.chaos_agent.create_experiment(
            name=payload.name,
            fault_type=payload.fault_type,
            target_service=payload.target_service,
            duration_seconds=payload.duration_seconds,
            params=payload.params,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    success = orchestrator.chaos_agent.inject_fault(exp)
    if not success:
        raise HTTPException(
            status_code=403,
            detail=f"Fault injection blocked: status is {exp.status} (Check Emergency Stop or Blast Radius).",
        )

    if exp.fault_type == "DEPLOYMENT_CRASH":
        _, incident = orchestrator.ingestion_engine.ingest_ci_event({
            "service_name": exp.target_service,
            "version": "v2.2.0-broken",
            "event_type": "FAILURE",
            "error_type": "DeploymentCrashLoop",
            "error_message": "Pod failed to reach Ready state: CrashLoopBackOff",
            "logs_snippet": "[CRITICAL] Application startup failed: invalid memory reference",
            "details": {"chaos_experiment_id": exp.experiment_id},
        })
        if incident:
            incident.is_chaos_injected = True
            incident.chaos_experiment_id = exp.experiment_id
            asyncio.create_task(orchestrator.process_incident(incident))

    elif exp.fault_type == "CONFIG_DRIFT":
        finding, incident = orchestrator.drift_detector.compare_configurations(
            service_name=exp.target_service,
            live_config=target_env.get_live_config(),
            reference_config=target_env.reference_config,
        )
        if incident and finding:
            incident.is_chaos_injected = True
            incident.chaos_experiment_id = exp.experiment_id
            evidence = orchestrator.diagnostic_agent.collect_evidence(
                incident=incident,
                drift_findings=[finding],
                logs_snippet=target_env.get_recent_logs(),
            )
            asyncio.create_task(orchestrator.process_incident(incident, evidence_bundle=evidence))

    elif exp.fault_type in ["LATENCY_SPIKE", "RESOURCE_EXHAUSTION"]:
        anomalies, incident = orchestrator.anomaly_detector.analyze_metrics(
            service_name=exp.target_service,
            metrics=target_env.metrics,
            recent_deployment_time=120.0,
        )
        if incident and anomalies:
            incident.is_chaos_injected = True
            incident.chaos_experiment_id = exp.experiment_id
            evidence = orchestrator.diagnostic_agent.collect_evidence(
                incident=incident,
                anomaly_findings=anomalies,
                logs_snippet=target_env.get_recent_logs(),
                metrics_summary=target_env.metrics,
            )
            asyncio.create_task(orchestrator.process_incident(incident, evidence_bundle=evidence))

    return {"status": "CHAOS_FAULT_INJECTED", "experiment": exp.model_dump()}


@app.post("/api/chaos/abort/{experiment_id}")
async def abort_chaos(experiment_id: str):
    exp = orchestrator.chaos_agent.terminate_experiment(
        experiment_id=experiment_id, reason="OPERATOR_ABORTED"
    )
    if not exp:
        raise HTTPException(status_code=404, detail="Chaos experiment not found.")
    return {"status": "CHAOS_ABORTED", "experiment": exp.model_dump()}


@app.get("/api/chaos/experiments")
async def list_chaos_experiments(limit: int = 50):
    return state_store.list_chaos_experiments(limit=limit)


@app.post("/api/emergency-stop")
async def toggle_emergency_stop(payload: EmergencyStopPayload):
    if payload.active:
        orchestrator.trigger_emergency_stop(operator=payload.operator_name)
        msg = "EMERGENCY_STOP_ACTIVATED"
    else:
        orchestrator.release_emergency_stop(operator=payload.operator_name)
        msg = "EMERGENCY_STOP_RELEASED"

    await ws_manager.broadcast({"type": msg, "operator": payload.operator_name})
    return {
        "status": msg,
        "emergency_stop_active": policy_engine.is_emergency_stopped(),
    }


@app.get("/api/audit-trail")
async def get_audit_trail(correlation_id: Optional[str] = None, limit: int = 100):
    events = state_store.list_audit_events(correlation_id=correlation_id, limit=limit)
    integrity_ok, integrity_err = state_store.verify_audit_log_integrity()
    return {
        "integrity_verified": integrity_ok,
        "integrity_error": integrity_err,
        "total_events_returned": len(events),
        "events": [e.model_dump() for e in events],
    }


@app.get("/api/target/state")
async def get_target_state():
    return {
        "health": target_env.get_health_status(),
        "live_config": target_env.get_live_config(),
        "reference_config": target_env.reference_config,
        "recent_logs": target_env.get_recent_logs(lines=25),
        "deployment_history": target_env.deployment_history,
    }


@app.get("/api/benchmark/summary")
async def get_benchmark_summary():
    incidents = state_store.list_incidents(limit=200)
    if not incidents:
        return {
            "total_incidents": 0,
            "mttr_seconds": 0.0,
            "diagnosis_accuracy_pct": 100.0,
            "repair_success_rate_pct": 100.0,
            "human_intervention_rate_pct": 0.0,
        }

    resolved = [i for i in incidents if i.status == IncidentStatus.RESOLVED and i.recovery_duration_seconds]
    total_count = len(incidents)
    resolved_count = len(resolved)

    mttr = sum(i.recovery_duration_seconds for i in resolved) / resolved_count if resolved_count else 0.0
    hitl_count = len([i for i in incidents if i.human_approved is not None or i.status == IncidentStatus.ESCALATED])
    auto_repaired_count = len([i for i in resolved if i.human_approved is None])

    return {
        "total_incidents": total_count,
        "resolved_incidents": resolved_count,
        "mean_time_to_recovery_seconds": round(mttr, 2),
        "repair_success_rate_pct": round((resolved_count / total_count) * 100, 1) if total_count else 100.0,
        "human_intervention_rate_pct": round((hitl_count / total_count) * 100, 1) if total_count else 0.0,
        "autonomous_resolution_rate_pct": round((auto_repaired_count / total_count) * 100, 1) if total_count else 100.0,
    }


@app.post("/api/clear-all")
async def clear_all_data():
    """Purges all incidents, audit records, and chaos experiments, restoring target state."""
    state_store.clear_all_records()
    target_env.clear_faults()
    target_env.rollback_to_version("v2.0.0")
    await ws_manager.broadcast({"type": "ALL_RECORDS_CLEARED"})
    return {"status": "ALL_RECORDS_CLEARED", "message": "All incident history, audit logs, and chaos records cleared."}



# --- WebSocket Endpoint ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "INITIAL_SNAPSHOT",
            "data": {
                "emergency_stop": policy_engine.is_emergency_stopped(),
                "target_health": target_env.get_health_status(),
                "llm_info": orchestrator.diagnostic_agent.llm_provider.get_status_info(),
            },
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# Mount static directory and UI root
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Self-Healing Cloud Deployment Pipelines API Server is running."}
