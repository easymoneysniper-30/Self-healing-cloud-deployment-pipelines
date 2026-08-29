"""Simulated Cloud Deployment Target & Instrumented Microservice.

Simulates a live Kubernetes/containerized service with health probes, live config state,
metric emissions, and deployment rollback/patch execution.
"""

from __future__ import annotations
import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from src.core.models import utc_now


class MockDeploymentTarget:
    """In-memory instrumented cloud microservice cluster simulator."""

    def __init__(self, service_name: str = "payments-service", namespace: str = "demo-payments-service"):
        self.service_name = service_name
        self.namespace = namespace
        self.current_version = "v2.0.0"
        self.known_good_version = "v2.0.0"
        self.deployment_history: List[Dict[str, Any]] = [
            {
                "version": "v2.0.0",
                "deployed_at": utc_now().isoformat(),
                "status": "HEALTHY",
                "commit_sha": "a1b2c3d",
            }
        ]

        # Reference baseline configuration
        self.reference_config: Dict[str, Any] = {
            "replicas": 3,
            "port": 8080,
            "environment": {
                "ENV_NAME": "production",
                "LOG_LEVEL": "INFO",
                "DATABASE_URL": "postgresql://app_user:secure_pwd@db.internal:5432/payments_db",
                "CONNECTION_POOL_SIZE": "20",
                "REQUEST_TIMEOUT_MS": "3000",
                "ENABLE_DEBUG_MODE": "false",
                "ALLOW_PRIVILEGED_ACCESS": "false",
            },
            "resources": {
                "cpu_limit": "500m",
                "memory_limit": "512Mi",
            },
        }

        # Live mutable configuration
        self.live_config: Dict[str, Any] = copy.deepcopy(self.reference_config)

        # Runtime health and metrics state
        self.is_healthy: bool = True
        self.status_message: str = "Service running nominally"
        self.active_faults: List[str] = []
        self.metrics: Dict[str, float] = {
            "latency_p95_ms": 45.0,
            "error_rate_pct": 0.05,
            "cpu_util_pct": 28.0,
            "memory_util_pct": 42.0,
            "throughput_rps": 350.0,
        }
        self.logs: List[str] = [
            f"[{utc_now().isoformat()}] [INFO] {self.service_name} {self.current_version} initialized successfully."
        ]

    def log(self, message: str, level: str = "INFO") -> None:
        entry = f"[{utc_now().isoformat()}] [{level}] {message}"
        self.logs.append(entry)
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]

    def deploy_new_version(
        self, version: str, commit_sha: str = "new_sha", is_defective: bool = False
    ) -> bool:
        """Simulates deploying a new version to the cluster."""
        self.log(f"Received deployment rollout request for version '{version}' (commit: {commit_sha}).")
        if not is_defective:
            self.known_good_version = self.current_version
            self.current_version = version
            self.is_healthy = True
            self.status_message = f"Version {version} deployed and healthy."
            self.metrics["latency_p95_ms"] = 48.0
            self.metrics["error_rate_pct"] = 0.08
            self.deployment_history.append({
                "version": version,
                "deployed_at": utc_now().isoformat(),
                "status": "HEALTHY",
                "commit_sha": commit_sha,
            })
            self.log(f"Deployment of {version} passed readiness and liveness health checks.")
            return True
        else:
            # Defective deployment rollout
            self.current_version = version
            self.is_healthy = False
            self.status_message = f"CrashLoopBackOff: Container in {version} exited with code 137 (OOM/Startup Error)."
            self.metrics["latency_p95_ms"] = 1200.0
            self.metrics["error_rate_pct"] = 85.0
            self.deployment_history.append({
                "version": version,
                "deployed_at": utc_now().isoformat(),
                "status": "CRASHED",
                "commit_sha": commit_sha,
            })
            self.log(f"CRITICAL: Application startup failed in {version}. Unhandled exception in bootstrap.", "ERROR")
            self.log("Traceback (most recent call last): SystemExit: Invalid connection string / Segfault", "ERROR")
            return False

    def rollback_to_version(self, target_version: str) -> bool:
        """Executes a deployment rollback to a specified target version."""
        self.log(f"Executing automated rollback from '{self.current_version}' to '{target_version}'...")
        self.current_version = target_version
        self.is_healthy = True
        self.status_message = f"Rolled back to {target_version}. Pods healthy."
        self.active_faults.clear()
        self.metrics["latency_p95_ms"] = 45.0
        self.metrics["error_rate_pct"] = 0.05
        self.metrics["cpu_util_pct"] = 30.0
        self.metrics["memory_util_pct"] = 45.0
        self.deployment_history.append({
            "version": target_version,
            "deployed_at": utc_now().isoformat(),
            "status": "ROLLED_BACK_HEALTHY",
            "commit_sha": "rollback_action",
        })
        self.log(f"Rollback to '{target_version}' completed. Health probe verified OK.")
        return True

    def apply_config_patch(self, patch: Dict[str, Any]) -> bool:
        """Applies a configuration patch reverting drifted keys."""
        self.log(f"Applying configuration patch: {list(patch.keys())}")
        for key, value in patch.items():
            if key == "environment" and isinstance(value, dict):
                for env_k, env_v in value.items():
                    self.live_config["environment"][env_k] = env_v
            else:
                self.live_config[key] = value

        self.is_healthy = True
        self.status_message = "Configuration patch applied successfully."
        self.log("Configuration reconciled with reference state.")
        return True

    def restart_service(self) -> bool:
        """Restarts the container / pod instance."""
        self.log(f"Restarting service '{self.service_name}' pods...")
        self.is_healthy = True
        self.status_message = f"Pods restarted for {self.current_version}. Health probes passed."
        self.metrics["latency_p95_ms"] = 45.0
        self.metrics["error_rate_pct"] = 0.05
        self.log("Service restart completed successfully.")
        return True

    def inject_fault(self, fault_type: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Injects a controlled fault (used by Chaos Agent)."""
        params = params or {}
        self.active_faults.append(fault_type)

        if fault_type == "DEPLOYMENT_CRASH":
            bad_version = params.get("version", "v2.2.0-broken")
            self.deploy_new_version(bad_version, is_defective=True)

        elif fault_type == "CONFIG_DRIFT":
            # Simulate silent out-of-band edit to environment variable
            drift_key = params.get("key", "ALLOW_PRIVILEGED_ACCESS")
            drift_val = params.get("value", "true")
            self.live_config["environment"][drift_key] = drift_val
            if params.get("add_bad_db_url"):
                self.live_config["environment"]["DATABASE_URL"] = "postgresql://bad_user:wrong_pwd@unknown.db:5432/db"
            self.log(f"Configuration drift injected: {drift_key}={drift_val}", "WARN")

        elif fault_type == "LATENCY_SPIKE":
            injected_ms = float(params.get("latency_ms", 850.0))
            self.metrics["latency_p95_ms"] = injected_ms
            self.metrics["error_rate_pct"] = float(params.get("error_rate_pct", 12.5))
            self.log(f"Injected synthetic latency spike: p95 = {injected_ms}ms", "WARN")

        elif fault_type == "RESOURCE_EXHAUSTION":
            self.metrics["cpu_util_pct"] = float(params.get("cpu_pct", 98.0))
            self.metrics["memory_util_pct"] = float(params.get("memory_pct", 96.0))
            self.metrics["latency_p95_ms"] = 920.0
            self.metrics["error_rate_pct"] = 18.0
            self.log("Injected synthetic resource saturation: CPU 98%, MEM 96%", "WARN")

    def clear_faults(self) -> None:
        """Safely clears all active synthetic chaos faults."""
        self.active_faults.clear()
        self.live_config = copy.deepcopy(self.reference_config)
        self.is_healthy = True
        self.status_message = "All faults cleared. Nominal state restored."
        self.metrics["latency_p95_ms"] = 45.0
        self.metrics["error_rate_pct"] = 0.05
        self.metrics["cpu_util_pct"] = 28.0
        self.metrics["memory_util_pct"] = 42.0
        self.log("Chaos faults safely terminated. Nominal state restored.")

    def get_health_status(self) -> Dict[str, Any]:
        """Runs health check probe against target service."""
        return {
            "service_name": self.service_name,
            "namespace": self.namespace,
            "current_version": self.current_version,
            "is_healthy": self.is_healthy,
            "status_message": self.status_message,
            "active_faults": list(self.active_faults),
            "metrics": copy.deepcopy(self.metrics),
            "timestamp": utc_now().isoformat(),
        }

    def get_live_config(self) -> Dict[str, Any]:
        return copy.deepcopy(self.live_config)

    def get_recent_logs(self, lines: int = 15) -> str:
        return "\n".join(self.logs[-lines:])
