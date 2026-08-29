"""Unit tests for Kubernetes Deployment Target Adapter."""

import pytest
from src.target_env.k8s_deploy_target import K8sDeploymentTarget


def test_k8s_adapter_dual_mode_fallback():
    # When no cluster is running, the adapter initializes cleanly in Simulated Dual-Mode
    k8s_target = K8sDeploymentTarget(
        service_name="payments-service",
        namespace="demo-payments-service",
        kubeconfig_path="/nonexistent/kubeconfig",
    )
    assert k8s_target.is_live_k8s() is False
    health = k8s_target.get_health_status()
    assert health["target_mode"] == "SIMULATED_MOCK"
    assert health["current_version"] == "v2.0.0"


def test_k8s_adapter_rollback():
    k8s_target = K8sDeploymentTarget(service_name="payments-service", namespace="demo-payments-service")
    res = k8s_target.rollback_to_version("v1.9.0")
    assert res is True
    assert k8s_target.current_version == "v1.9.0"


def test_k8s_adapter_config_patch():
    k8s_target = K8sDeploymentTarget(service_name="payments-service", namespace="demo-payments-service")
    patch = {"environment": {"ALLOW_PRIVILEGED_ACCESS": "false"}}
    res = k8s_target.apply_config_patch(patch)
    assert res is True
    live_cfg = k8s_target.get_live_config()
    assert live_cfg["environment"]["ALLOW_PRIVILEGED_ACCESS"] == "false"
