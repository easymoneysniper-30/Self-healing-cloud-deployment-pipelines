"""Unit tests for LLM Diagnostic Provider and Hybrid Diagnostic Agent."""

import pytest
from src.agents.diagnostic_agent import DiagnosticAgent
from src.agents.llm_provider import LLMDiagnosticProvider
from src.core.models import (
    ActionType,
    EvidenceBundle,
    FailureRecord,
    Incident,
    IncidentType,
    generate_correlation_id,
    utc_now,
)
from src.core.state_store import StateStore


def test_llm_provider_unconfigured_fallback():
    provider = LLMDiagnosticProvider(provider="heuristic")
    assert provider.is_configured() is False
    status = provider.get_status_info()
    assert "Heuristic" in status["active_mode"]

    # When unconfigured, diagnose_with_llm safely returns None
    cid = generate_correlation_id()
    incident = Incident(
        correlation_id=cid,
        service_name="payments-service",
        incident_type=IncidentType.DEPLOYMENT_FAILURE,
        summary="Rollout failed",
    )
    evidence = EvidenceBundle(correlation_id=cid, service_name="payments-service")
    assert provider.diagnose_with_llm(evidence, incident) is None


def test_llm_provider_prompt_formatting():
    provider = LLMDiagnosticProvider(provider="gemini", api_key="dummy-key")
    assert provider.is_configured() is True

    cid = generate_correlation_id()
    incident = Incident(
        correlation_id=cid,
        service_name="payments-service",
        incident_type=IncidentType.DEPLOYMENT_FAILURE,
        summary="Rollout crashed on startup",
    )
    evidence = EvidenceBundle(
        correlation_id=cid,
        service_name="payments-service",
        failure_records=[
            FailureRecord(
                correlation_id=cid,
                service_name="payments-service",
                version="v2.2.0",
                error_type="CrashLoopBackOff",
                error_message="Exit Code 137",
            )
        ],
        logs_snippet="[FATAL] OOMKilled",
    )

    prompt = provider._build_user_prompt(evidence, incident)
    assert "payments-service" in prompt
    assert "CrashLoopBackOff" in prompt
    assert "OOMKilled" in prompt


def test_llm_provider_hypothesis_parsing():
    provider = LLMDiagnosticProvider(provider="gemini", api_key="dummy-key", model="gemini-1.5-flash")
    cid = generate_correlation_id()
    evidence = EvidenceBundle(correlation_id=cid, service_name="payments-service")

    mock_llm_json = {
        "primary_cause": "Container terminated due to memory exhaustion during initialization.",
        "explanation": "Log analysis reveals SIGKILL (137) issued by kernel OOM killer.",
        "confidence_score": 0.94,
        "recommended_action": "ROLLBACK_DEPLOYMENT",
        "reasoning_trace": [
            "Identified OOMKilled signature in container pod events.",
            "Verified previous stable deployment v2.0.0 allocated within limits.",
        ],
    }

    hypothesis = provider._parse_hypothesis_data(mock_llm_json, evidence)
    assert hypothesis.primary_cause == "Container terminated due to memory exhaustion during initialization."
    assert hypothesis.confidence_score == 0.94
    assert hypothesis.recommended_action == ActionType.ROLLBACK_DEPLOYMENT
    assert len(hypothesis.reasoning_trace) >= 3
    assert "GEMINI" in hypothesis.reasoning_trace[0]


def test_diagnostic_agent_hybrid_flow(tmp_path):
    store = StateStore(str(tmp_path / "hybrid_test.db"))
    # DiagnosticAgent with heuristic fallback
    diag = DiagnosticAgent(state_store=store)

    cid = generate_correlation_id()
    incident = Incident(
        correlation_id=cid,
        service_name="payments-service",
        incident_type=IncidentType.DEPLOYMENT_FAILURE,
        summary="Rollout crashed",
    )
    fail_rec = FailureRecord(
        correlation_id=cid,
        service_name="payments-service",
        version="v2.2.0",
        error_type="CrashLoopBackOff",
        error_message="Readiness probe failed",
        logs_snippet="CrashLoopBackOff on :8080/health",
    )
    evidence = diag.collect_evidence(incident, failure_records=[fail_rec], logs_snippet=fail_rec.logs_snippet)

    hypothesis = diag.diagnose(evidence, incident)
    assert hypothesis is not None
    assert hypothesis.confidence_score >= 0.90
    assert hypothesis.recommended_action == ActionType.ROLLBACK_DEPLOYMENT
