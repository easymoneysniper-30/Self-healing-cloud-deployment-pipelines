# Self-Healing Cloud Deployment Pipelines 🚀

An agentic, closed-loop DevOps resilience platform designed according to the **M.Tech Project Requirements Document (PRD/SRS)**.

The framework observes cloud deployment pipelines and running services, detects failure states (defective rollouts, GitOps configuration drift, and runtime performance anomalies), diagnoses root causes using evidence-backed confidence scoring, validates proposed remediations against safety policies, autonomously executes rollbacks and configuration patches, exercises resilience via controlled chaos experiments, and logs all operations into a tamper-evident, SHA-256 chained audit trail.

---

## 🌟 Key Subsystems & Architecture

```
                                  +------------------------------+
                                  |  CI/CD Platform / Monitoring |
                                  +--------------+---------------+
                                                 |
                                                 v
                                  +------------------------------+
                                  |   Telemetry & Drift Engine   |
                                  |    (Correlation ID assign)   |
                                  +--------------+---------------+
                                                 |
                                                 v
                                  +------------------------------+
                                  |       Diagnostic Agent       |
                                  |  (Evidence, RCA, 0-100% Conf)|
                                  +--------------+---------------+
                                                 |
                                                 v
                                  +------------------------------+
                                  |    Policy & Safety Engine    |
                                  |   (SR-1 to SR-11 Enforcer)   |
                                  +-------+--------------+-------+
                                          |              |
                      Confidence >= 80%   |              |  Confidence < 80%
                      & Policy Validated  |              |  or High-Risk Action
                                          v              v
                           +------------------+   +-------------------+
                           |   Repair Agent   |   | Operator HITL Gate|
                           | (Rollback/Patch) |   | (Approve/Reject)  |
                           +--------+---------+   +---------+---------+
                                    |                       |
                                    +-----------+-----------+
                                                |
                                                v
                                  +------------------------------+
                                  |   Post-Repair Verification   |
                                  +--------------+---------------+
                                                 |
                                                 v
                                  +------------------------------+
                                  | Cryptographic SHA-256 Audit  |
                                  +------------------------------+
```

---

## 📋 PRD Requirements Traceability Matrix

| Requirement | Implementation Module | Verification Status |
| :--- | :--- | :--- |
| **FR-1.1–FR-1.5** | `src/telemetry/ingestion.py` | ✅ Webhook ingestion, Failure detection, Correlation ID assignment |
| **FR-2.1–FR-2.4** | `src/agents/diagnostic_agent.py` | ✅ Evidence bundle aggregation, RCA hypothesis, Reasoning trace |
| **FR-3.1–FR-3.3** | `src/telemetry/drift_detector.py` | ✅ GitOps deep diffing, Severity rating (`COSMETIC` / `FUNCTIONAL` / `CRITICAL_SECURITY`), Config snapshots |
| **FR-4.1–FR-4.3** | `src/telemetry/anomaly_detector.py`| ✅ Sliding-window SLAs, Z-Score deviation scoring, Temporal deploy correlation |
| **FR-5.1** | `src/agents/diagnostic_agent.py` | ✅ Calibrated numeric confidence score scale (0.0 to 1.0 / 0–100%) |
| **FR-6.1–FR-6.6** | `src/agents/chaos_agent.py` | ✅ Controlled fault injection catalog, isolated namespace scoping, instant safety abort |
| **FR-7.1–FR-7.7** | `src/agents/repair_agent.py` | ✅ Reversible rollback, GitOps config patch, post-repair health probe verification, circuit breaker |
| **FR-8.1–FR-8.4** | `src/api/server.py` & Dashboard | ✅ Real-time WebSockets, approval queue, timeline, audit explorer |
| **SR-1 to SR-11** | `src/core/policy_engine.py` | ✅ Allowlists, blast radius limits, rate limits, circuit breakers, dry-run mode, emergency stop |
| **DR-3 / EI-7** | `src/core/state_store.py` | ✅ Append-only SQLite with SHA-256 block hash chaining |
| **Section 15** | `src/evaluation/benchmark_runner.py` | ✅ Automated comparative evaluation vs. conventional baseline |

---

## ⚡ Quickstart

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
python -m pytest tests/ -v
```

### 3. Launch Operator Web Dashboard & API Server
```bash
python run_server.py
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser to access the live Control Center:
- **Incident Control Room**: Live incident stream, RCA hypotheses, reasoning traces, and Human-in-the-Loop approval gates.
- **Chaos Engineering Lab**: One-click fault injection (broken rollouts, drift, latency spikes, resource saturation).
- **Live Telemetry & Logs**: Real-time Chart.js latency, error rate, CPU, memory graphs, and pod log streaming.
- **Tamper-Evident Audit Trail**: Cryptographic SHA-256 chained audit logs with verification badge.
- **Academic Evaluation**: Comparative MTTR and autonomy analytics.

### 4. Run Academic Evaluation Benchmark Suite
```bash
python run_benchmark.py
```
This runs the 4 standardized evaluation scenarios and produces:
- `evaluation_report.md` (Markdown format suitable for academic submission)
- `evaluation_report.json` (Structured JSON benchmark output)

---

## 🛡️ Safety Policy Configuration (`config/default_policy.yaml`)

```yaml
version: "1.0"
environment: "demonstrator-isolated"

allowlisted_actions:
  - "ROLLBACK_DEPLOYMENT"
  - "PATCH_CONFIG"
  - "RESTART_POD_OR_SERVICE"

confidence_threshold: 0.80  # Actions below 80% require human operator approval

allowed_namespaces:
  - "demo-payments-service"
  - "payments-service"

rate_limit:
  max_actions_per_window: 3
  window_seconds: 120

circuit_breaker:
  consecutive_failure_threshold: 3
  cooldown_seconds: 300
```
