"""LLM Diagnostic Provider for Self-Healing Cloud Deployment Pipelines.

Supports Google Gemini and OpenAI APIs for deep natural-language Root Cause Analysis (RCA),
with strict JSON schema enforcement and zero-disruption heuristic fallback (PRD SR-2, NFR-9).
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Optional
import httpx
from src.core.models import (
    ActionType,
    EvidenceBundle,
    Incident,
    RootCauseHypothesis,
    utc_now,
)


class LLMDiagnosticProvider:
    """Manages LLM API calls (Gemini / OpenAI) for diagnostic reasoning."""

    SYSTEM_PROMPT = """You are an expert Cloud SRE & Site Reliability Engineering Diagnostic Agent.
Your task is to analyze telemetry evidence (deployment logs, GitOps configuration diffs, performance anomalies, and container status) for a cloud microservice incident.

You MUST produce an evidence-based Root Cause Analysis (RCA) complying with these rules:
1. STRICT GROUNDING: Cite specific error messages, log lines, configuration keys, or metric numbers from the evidence. Never invent unobserved errors.
2. RECOMMENDED ACTION: Must be EXACTLY ONE of the following allowlisted action types:
   - "ROLLBACK_DEPLOYMENT" (if defective build/crash/regression is linked to a deployment)
   - "PATCH_CONFIG" (if runtime configuration diverged from reference state)
   - "RESTART_POD_OR_SERVICE" (if transient container freeze/unresponsiveness)
   - "MANUAL_ESCALATION" (if ambiguous, low confidence, or external traffic surge without clear deploy linkage)
3. CONFIDENCE SCORE: A calibrated float between 0.0 and 1.0 (e.g. 0.95 for deterministic/clear evidence, 0.60 for ambiguous signals).
4. REASONING TRACE: A structured list of concise deduction steps explaining your analysis chain.

Return ONLY a valid JSON object matching this schema:
{
  "primary_cause": "Short 1-sentence summary of the root cause",
  "explanation": "Detailed explanation citing the specific evidence",
  "confidence_score": 0.95,
  "recommended_action": "ROLLBACK_DEPLOYMENT",
  "reasoning_trace": [
    "Analyzed container logs and identified CrashLoopBackOff with exit code 137.",
    "Correlated with deployment rollout event v2.2.0.",
    "Calculated 95% confidence based on definitive startup failure.",
    "Selected ROLLBACK_DEPLOYMENT to restore service to known-good version."
  ]
}
"""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "auto")).lower()
        self.gemini_api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        self.openai_api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        self.model = (model or os.getenv("LLM_MODEL", "")).strip()

        # Auto-detect provider if keys exist
        if self.provider == "auto":
            if self.gemini_api_key:
                self.provider = "gemini"
            elif self.openai_api_key:
                self.provider = "openai"
            else:
                self.provider = "heuristic"

        # Set default models per provider
        if (
            not self.model
            or self.model == "heuristic-rules"
            or (self.provider == "gemini" and "gemini" not in self.model.lower())
            or (self.provider == "openai" and "gpt" not in self.model.lower())
        ):
            if self.provider == "gemini":
                self.model = "gemini-3-flash-preview"
            elif self.provider == "openai":
                self.model = "gpt-4o-mini"
            else:
                self.model = "heuristic-rules"

    @staticmethod
    def _clean_json_str(text: str) -> str:
        """Strips markdown code fences (```json ... ```) from LLM output."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def is_configured(self) -> bool:
        """Returns True if a live LLM API provider and key are configured."""
        if self.provider == "gemini" and self.gemini_api_key:
            return True
        if self.provider == "openai" and self.openai_api_key:
            return True
        return False

    def get_status_info(self) -> Dict[str, Any]:
        """Returns LLM provider status for dashboard and APIs."""
        return {
            "provider": self.provider,
            "model": self.model,
            "is_configured": self.is_configured(),
            "active_mode": "Live LLM Engine" if self.is_configured() else "Deterministic Heuristic Engine",
        }

    def _build_user_prompt(self, evidence: EvidenceBundle, incident: Incident) -> str:
        """Formats the EvidenceBundle into a structured prompt."""
        evidence_dict = {
            "incident_id": incident.incident_id,
            "correlation_id": evidence.correlation_id,
            "service_name": evidence.service_name,
            "incident_type": incident.incident_type.value,
            "incident_summary": incident.summary,
            "deployment_events": [d.model_dump() for d in evidence.deployment_events],
            "failure_records": [f.model_dump() for f in evidence.failure_records],
            "drift_findings": [
                {
                    "severity": df.overall_severity.value,
                    "diff_items": [d.model_dump() for d in df.diff_items],
                }
                for df in evidence.drift_findings
            ],
            "anomaly_findings": [
                {
                    "metric": af.metric_name,
                    "observed": af.observed_value,
                    "threshold": af.threshold_value,
                    "z_score": af.z_score,
                    "correlated_recent_deploy": af.correlated_recent_deploy,
                }
                for af in evidence.anomaly_findings
            ],
            "logs_snippet": evidence.logs_snippet,
            "metrics_summary": evidence.metrics_summary,
        }
        return f"Investigate this incident evidence bundle:\n\n{json.dumps(evidence_dict, indent=2, default=str)}"

    def diagnose_with_llm(
        self, evidence: EvidenceBundle, incident: Incident
    ) -> Optional[RootCauseHypothesis]:
        """Calls the configured LLM API. Returns None if unconfigured or on failure."""
        if not self.is_configured():
            return None

        prompt = self._build_user_prompt(evidence, incident)

        try:
            if self.provider == "gemini":
                return self._call_gemini(prompt, evidence, incident)
            elif self.provider == "openai":
                return self._call_openai(prompt, evidence, incident)
        except Exception as e:
            # Safe fallback: Log clean notice and return None so heuristic engine takes over smoothly
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code:
                print(f"[LLMDiagnosticProvider] LLM API returned HTTP {status_code}. Switched to local Heuristic Diagnostic Engine.")
            else:
                print(f"[LLMDiagnosticProvider] LLM API notice ({e}). Switched to local Heuristic Diagnostic Engine.")
            return None

        return None

    def _call_gemini(
        self, prompt: str, evidence: EvidenceBundle, incident: Incident
    ) -> Optional[RootCauseHypothesis]:
        """Executes Google Gemini API call via official google-genai SDK with REST fallback."""
        model_name = self.model
        if not model_name or "gemini" not in model_name.lower() or model_name == "heuristic-rules":
            model_name = "gemini-3-flash-preview"

        # 1. Try official google-genai SDK
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.gemini_api_key)
            full_prompt = f"{self.SYSTEM_PROMPT}\n\n{prompt}"
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            text_content = response.text or ""
            cleaned_json = self._clean_json_str(text_content)
            data = json.loads(cleaned_json)
            return self._parse_hypothesis_data(data, evidence)
        except Exception as sdk_err:
            # Fallback to direct REST call if SDK hits transport edge-cases
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"{self.SYSTEM_PROMPT}\n\n{prompt}"}],
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                },
            }

            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                res_json = resp.json()
                candidates = res_json.get("candidates", [])
                if not candidates:
                    return None
                text_content = (
                    candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
                )
                cleaned_json = self._clean_json_str(text_content)
                data = json.loads(cleaned_json)
                return self._parse_hypothesis_data(data, evidence)

    def _call_openai(
        self, prompt: str, evidence: EvidenceBundle, incident: Incident
    ) -> Optional[RootCauseHypothesis]:
        """Executes OpenAI API call with JSON response format."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            res_json = response.json()
            raw_msg = res_json["choices"][0]["message"]["content"]
            data = json.loads(raw_msg)
            return self._parse_hypothesis_data(data, evidence)

    def _parse_hypothesis_data(
        self, data: Dict[str, Any], evidence: EvidenceBundle
    ) -> RootCauseHypothesis:
        """Validates and maps LLM output to RootCauseHypothesis."""
        action_str = data.get("recommended_action", "MANUAL_ESCALATION").upper()
        try:
            recommended_action = ActionType(action_str)
        except ValueError:
            recommended_action = ActionType.MANUAL_ESCALATION

        confidence = float(data.get("confidence_score", 0.85))
        confidence = max(0.0, min(1.0, confidence))

        reasoning_trace = data.get("reasoning_trace", [])
        if not isinstance(reasoning_trace, list):
            reasoning_trace = [str(reasoning_trace)]

        # Tag trace with LLM provider info for transparency
        reasoning_trace.insert(
            0,
            f"[AI Doctor: {self.provider.upper()} ({self.model})] Evidence bundle analyzed with deep neural reasoning.",
        )

        return RootCauseHypothesis(
            correlation_id=evidence.correlation_id,
            service_name=evidence.service_name,
            primary_cause=data.get("primary_cause", "Incident diagnosed via LLM."),
            explanation=data.get(
                "explanation", "Detailed explanation generated from logs and metrics."
            ),
            confidence_score=confidence,
            recommended_action=recommended_action,
            evidence_ids=[
                f.failure_id for f in evidence.failure_records
            ]
            + [d.finding_id for d in evidence.drift_findings]
            + [a.finding_id for a in evidence.anomaly_findings],
            reasoning_trace=reasoning_trace,
            generated_at=utc_now(),
        )
