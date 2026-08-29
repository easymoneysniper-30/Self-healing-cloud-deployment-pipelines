# Project Requirements Document (PRD/SRS)
## Self-Healing Cloud Deployment Pipelines

---

## 1. Document Control

| Field | Value |
|---|---|
| Project Title | Self-Healing Cloud Deployment Pipelines |
| Document Title | Project Requirements Document (PRD/SRS) |
| Document Type | M.Tech Project — Requirements Specification |
| Version | 1.0 (Draft) |
| Author | *[Student Name — placeholder]* |
| Supervisor | *[Supervisor Name — placeholder]* |
| Date | *[Date — placeholder]* |
| Status | Draft — pending supervisor review |

### Revision History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| 0.1 | *[placeholder]* | *[Student Name]* | Initial draft generated from project brief |
| 1.0 | *[placeholder]* | *[Student Name]* | First complete version for supervisor review |

> **Note on assumptions:** Throughout this document, statements directly traceable to the supplied project brief are presented as firm requirements. Statements introduced to make the project implementable — but not explicitly present in the brief — are labeled **[ASSUMPTION]**. Numerical thresholds not sourced from the brief are labeled **[PROPOSED — requires supervisor approval]**. These should be reviewed and either confirmed, adjusted, or rejected by the student and supervisor before implementation begins.

---

## 2. Executive Summary

Modern cloud deployment pipelines fail in ways that are difficult to diagnose quickly: deployments break due to misconfiguration, infrastructure drifts silently away from its intended state, and running services degrade under load in ways that standard alerting catches too late or not at all. Diagnosing and recovering from these failures today largely depends on manual, on-call engineering effort — which is slow, inconsistent, and does not scale with deployment frequency.

This project proposes an **agentic, self-healing CI/CD framework** that observes a deployment pipeline and its runtime environment, automatically detects failures, configuration drift, and performance anomalies, and responds using a coordinated set of software agents. A **diagnostic agent** investigates the evidence and estimates a root cause with a confidence score. A **chaos agent** can inject controlled failure scenarios into an isolated environment to validate the system's resilience and the effectiveness of its own repair logic. A **repair agent** executes a constrained set of recovery actions — primarily rollback, and secondarily configuration patching — under explicit policy controls, safety limits, and human-approval gates for uncertain or high-impact cases.

The expected value of the project is a working demonstrator, evaluated against a conventional (non-self-healing) pipeline baseline, showing measurable improvement in detection latency, mean time to recovery (MTTR), and reduction in required human intervention — while keeping every automated action auditable, reversible, and bounded by explicit safety policy.

The final outcome is an implementation-ready specification and, following implementation, a working prototype plus an evaluation report suitable for academic assessment.

---

## 3. Background and Problem Statement

### 3.1 Deployment Reliability Challenges
Cloud-native deployment pipelines are exposed to several recurring classes of failure:
- **Deployment failures** — a release fails to roll out correctly (bad build, failed health check, resource exhaustion, incompatible configuration).
- **Configuration drift** — the live environment silently diverges from the configuration declared in source control or the last known-good state, often due to manual out-of-band changes.
- **Runtime performance anomalies** — a deployment succeeds technically but causes latency spikes, error-rate increases, or resource saturation under real traffic.

### 3.2 Limitations of Manual Diagnosis and Recovery
Manual response to these failure classes has well-known limitations:
- Diagnosis depends on the availability and expertise of on-call engineers.
- Root-cause investigation is slow relative to the speed at which a bad deployment can cause damage.
- Recovery actions (rollback, config fixes) are performed ad hoc, with inconsistent safety checks.
- There is limited systematic testing of *whether* the recovery process itself works, since resilience testing (chaos engineering) is often treated as a separate, disconnected practice from day-to-day operations.

### 3.3 Motivation for Self-Healing DevOps
Combining automated failure detection, evidence-based diagnosis, controlled chaos testing, and policy-constrained automated repair into a single closed-loop system can reduce mean time to recovery, reduce the operational burden on engineers, and provide a continuously-exercised, empirically validated resilience mechanism rather than a rarely-tested manual runbook.

---

## 4. Project Objectives and Success Criteria

| ID | Objective | Success Criteria |
|---|---|---|
| OBJ-1 | Automatically detect deployment failures, configuration drift, and runtime performance anomalies from pipeline and monitoring signals. | System correctly flags injected/simulated failures of each of the three classes during evaluation, with detection latency and false-positive rate recorded. **[PROPOSED thresholds, Section 15]** |
| OBJ-2 | Perform evidence-based root-cause diagnosis with an explicit confidence score. | Diagnostic agent produces a root-cause hypothesis, supporting evidence, and a confidence score for each detected incident. |
| OBJ-3 | Validate system resilience via controlled chaos injection in an isolated environment. | Chaos agent can define, schedule, execute, and safely terminate at least the fault types listed in Section 8.6, with no impact outside the designated test environment. |
| OBJ-4 | Enable autonomous, policy-constrained repair (rollback and configuration patching). | Repair agent executes allowlisted repair actions only after policy validation; all actions are reversible or have a defined checkpoint; unsafe/uncertain cases escalate to a human. |
| OBJ-5 | Provide full auditability of automated decisions and actions. | Every detection, diagnosis, chaos experiment, and repair action is logged with a correlation ID, timestamp, actor (agent/human), and outcome, retrievable via an audit trail. |
| OBJ-6 | Demonstrate measurable improvement over a non-self-healing baseline. | Evaluation report compares MTTR, detection latency, and human-intervention rate between the self-healing pipeline and a conventional baseline pipeline. |

---

## 5. Scope Definition

### 5.1 In Scope
- Integration with a CI/CD pipeline to receive deployment/build events.
- Failure detection across deployment failures, configuration drift, and runtime performance anomalies.
- Diagnostic workflow: evidence collection, root-cause analysis, confidence scoring.
- Controlled chaos experiment definition, scheduling, execution, and safe termination in an isolated environment.
- Repair actions limited to rollback and configuration patching, gated by policy validation.
- Human approval and emergency-stop controls for automated actions.
- Auditability: logging of all agent decisions and actions.
- Reporting/dashboarding of incidents, repairs, and chaos experiment outcomes.

### 5.2 Out of Scope
- Unrestricted autonomous action in production environments **[ASSUMPTION: production use excluded by default; see Section 17]**.
- Arbitrary code modification by agents (e.g., automatically rewriting application source code beyond declared configuration).
- Multi-cloud cost/performance optimization.
- Business-level decision-making (e.g., autonomous scaling decisions tied to business KPIs) unless explicitly approved later.
- Support for deployment targets or CI/CD platforms beyond the ones selected for the demonstrator **[ASSUMPTION — technology stack not specified in brief; see Section 14]**.

---

## 6. Stakeholders and User Roles

| Role | Description | Responsibilities | Permissions |
|---|---|---|---|
| Student / Developer | Designs, builds, and evaluates the system. | Implements agents, configures policies, runs evaluation experiments. | Full administrative access to the demonstrator environment. |
| DevOps / Platform Operator | Represents the operational user of the system in a realistic deployment scenario. | Monitors dashboards, approves or rejects escalated repair actions, triggers emergency stop. | Approve/reject repair actions; trigger emergency stop; view audit log. |
| Project Supervisor | Provides academic oversight and approves scope/assumption decisions. | Reviews requirements, approves autonomy boundaries and proposed thresholds, evaluates final deliverable. | Read access to documentation, evaluation results, and audit trail. |
| System Administrator | **[ASSUMPTION]** Manages underlying infrastructure, credentials, and access control for the demonstrator environment. | Provisions environment, manages secrets, manages access control. | Infrastructure-level administrative access. |
| Application Owner (optional) | **[ASSUMPTION]** Represents the owner of the application being deployed, if distinct from the student. | Defines acceptable blast radius and approval policy for their application. | Configure policy for their application's repair permissions. |

---

## 7. System Context and High-Level Architecture

### 7.1 Logical Components
- **CI/CD Platform** — source of deployment/build events; triggers the pipeline.
- **Deployment Target** — the environment(s) where the application is deployed (e.g., a container orchestration cluster) **[ASSUMPTION — specific technology to be finalized, Section 14]**.
- **Monitoring / Logging Sources** — metrics, logs, and traces describing pipeline and runtime behavior.
- **Event Trigger** — component that ingests CI/CD and monitoring events and forwards them into the framework.
- **Agent Orchestrator** — coordinates the sequence of agent invocations (diagnostic → chaos [optional/scheduled] → repair), manages retries, timeouts, and escalation.
- **Diagnostic Agent** — investigates failure evidence, produces root-cause hypothesis and confidence score.
- **Chaos Agent** — defines and executes controlled fault-injection experiments in an isolated environment.
- **Repair Agent** — proposes and, if approved by policy, executes repair actions (rollback, configuration patch).
- **Policy Engine** — evaluates proposed repair/chaos actions against allowlists, confidence thresholds, and blast-radius limits; determines whether human approval is required.
- **State Store** — persists incident state, agent state, rollback checkpoints, and configuration snapshots.
- **Notification Channel** — delivers alerts and approval requests to human operators.
- **Audit Log** — immutable record of all detections, diagnoses, decisions, and actions.

### 7.2 Human-in-the-Loop Boundary
The architecture maintains an explicit, visible separation between:
1. **Fully automated actions** — allowlisted, low-risk, high-confidence, reversible actions the Repair Agent may execute without waiting for a human.
2. **Human-approval-gated actions** — actions that exceed confidence, blast-radius, or risk thresholds and require explicit operator approval before execution.
3. **Emergency stop** — a control available to the DevOps/Platform Operator (and Student/Developer) at all times, which immediately halts all agent-initiated actions in progress.

---

## 8. Functional Requirements

Each functional requirement is uniquely identified, prioritized (Must/Should/Could, per MoSCoW), and includes rationale, input/output, and verification method.

### 8.1 Pipeline Event Ingestion and Failure Detection

| ID | Requirement | Priority | Rationale | Input → Output | Verification |
|---|---|---|---|---|---|
| FR-1.1 | The system shall ingest deployment lifecycle events (start, success, failure) from the CI/CD platform. | Must | Core trigger for the entire detection pipeline. | CI/CD webhook/event → normalized internal event | Integration test with simulated pipeline events |
| FR-1.2 | The system shall detect a failed deployment based on pipeline status and/or post-deployment health checks. | Must | Deployment failure is the primary failure class in the brief. | Pipeline event + health check result → Failure Record | Fault-injection test (forced failed deployment) |
| FR-1.3 | The system shall detect configuration drift by comparing live configuration state against the last declared/known-good state. | Must | Explicitly named in the brief as a target failure class. | Live config snapshot + reference config → Drift Finding | Test with manually introduced drift |
| FR-1.4 | The system shall detect runtime performance anomalies using monitoring metrics (e.g., latency, error rate, resource utilization). | Must | Explicitly named in the brief. | Metrics stream → Anomaly Finding | Test with injected load/performance degradation |
| FR-1.5 | The system shall assign a unique correlation ID to every detected incident, linking all subsequent diagnostic and repair activity to it. | Must | Required for auditability and traceability (Section 16). | Incident detection → Correlation ID | Trace an incident end-to-end in audit log |

### 8.2 Diagnostic Workflow

| ID | Requirement | Priority | Rationale | Input → Output | Verification |
|---|---|---|---|---|---|
| FR-2.1 | On detection of an incident, the system shall automatically initiate the Diagnostic Agent workflow. | Must | Automates what is currently a manual triage step. | Failure/Drift/Anomaly Record → Diagnostic session | Integration test |
| FR-2.2 | The Diagnostic Agent shall collect relevant evidence (logs, metrics, traces, configuration diffs) associated with the incident's correlation ID. | Must | Diagnosis must be evidence-based, not speculative (Section 12). | Correlation ID → Evidence bundle | Verify evidence bundle completeness against known test scenario |
| FR-2.3 | The Diagnostic Agent shall produce a root-cause hypothesis with a numeric confidence score. | Must | Required by OBJ-2; confidence score drives policy decisions. | Evidence bundle → Root-cause hypothesis + confidence score | Compare hypothesis against known injected root cause |
| FR-2.4 | The Diagnostic Agent shall record its reasoning trace (evidence considered, hypothesis, confidence) for later audit and explainability review. | Must | Supports explainability (NFR, Section 9) and academic evaluation. | Diagnostic session → Reasoning trace (stored) | Manual review of stored trace |

### 8.3 Configuration Drift Handling

| ID | Requirement | Priority | Rationale |
|---|---|---|---|
| FR-3.1 | The system shall periodically or event-triggered compare live configuration against the declared reference state. | Must | Core drift-detection mechanism. |
| FR-3.2 | The system shall classify detected drift by severity/impact (e.g., cosmetic vs. functional vs. security-relevant). **[ASSUMPTION — not explicit in brief]** | Should | Enables policy to distinguish auto-fixable drift from cases needing approval. |
| FR-3.3 | The system shall record a configuration snapshot at the time drift is detected, for use in patching and rollback. | Must | Needed for safe, reversible patching (Section 12). |

### 8.4 Runtime Performance Anomaly Detection

| ID | Requirement | Priority | Rationale |
|---|---|---|---|
| FR-4.1 | The system shall monitor defined performance indicators (latency, error rate, throughput, resource utilization) continuously. | Must | Direct requirement from brief. |
| FR-4.2 | The system shall flag an anomaly when a metric crosses a configurable threshold or exhibits a statistically significant deviation from baseline. **[PROPOSED — exact detection method to be finalized]** | Must | Detection mechanism must be concrete to be implementable. |
| FR-4.3 | The system shall distinguish, where possible, between anomalies caused by a recent deployment and anomalies caused by external factors (e.g., traffic spike). **[ASSUMPTION]** | Should | Improves diagnostic accuracy but is not guaranteed to be fully solvable; treated as best-effort. |

### 8.5 Root-Cause Analysis and Confidence Scoring
(See FR-2.3, FR-2.4.) Additional requirement:

| ID | Requirement | Priority | Rationale |
|---|---|---|---|
| FR-5.1 | The confidence score shall use a defined, documented scale (e.g., 0–1 or 0–100%) consistent across all incident types. | Must | Enables consistent policy thresholds across incident types. |

### 8.6 Chaos Experiment Definition, Scheduling, Execution, and Termination

| ID | Requirement | Priority | Rationale | Verification |
|---|---|---|---|---|
| FR-6.1 | The system shall allow definition of chaos experiments specifying fault type, target scope, and duration. | Must | Required for OBJ-3. | Review experiment definition schema |
| FR-6.2 | Supported fault types shall include, at minimum: simulated deployment failure, simulated configuration drift, and simulated resource/latency degradation. **[ASSUMPTION — exact fault catalog to be finalized]** | Must | Must exercise all three detection classes (Section 8.1). | Execute each fault type and confirm detection |
| FR-6.3 | Chaos experiments shall execute only within an explicitly designated, isolated test environment. | Must | Safety requirement — prevents unintended production impact. | Verify environment scoping/allowlist enforcement |
| FR-6.4 | The system shall support scheduled (time-based) and on-demand (manually triggered) chaos experiments. | Should | Supports both automated regression testing and ad hoc validation. | Trigger both modes |
| FR-6.5 | The system shall support safe, immediate termination of any running chaos experiment (manual or automatic on safety-limit breach). | Must | Core safety control. | Trigger termination mid-experiment; verify state restored |
| FR-6.6 | The system shall record the outcome of each chaos experiment, including whether the incident was correctly detected and whether repair succeeded. | Must | Needed to evaluate OBJ-3 and feed the evaluation report (Section 15). | Review chaos experiment record after run |

### 8.7 Repair Planning, Policy Validation, Rollback, and Configuration Patching

| ID | Requirement | Priority | Rationale | Verification |
|---|---|---|---|---|
| FR-7.1 | On completion of diagnosis, the Repair Agent shall propose one or more candidate repair actions. | Must | Required for OBJ-4. | Review repair proposal against known scenario |
| FR-7.2 | Every proposed repair action shall be validated against the Policy Engine before execution. | Must | Core safety requirement (Section 12). | Attempt a disallowed action; confirm blocked |
| FR-7.3 | The Repair Agent shall support rollback to the last known-good deployment as the primary recovery mechanism. | Must | Explicit requirement from brief. | Force a failure; verify rollback restores service |
| FR-7.4 | The Repair Agent shall support configuration patching (reverting drifted configuration to reference state) as a secondary, controlled mechanism. | Must | Explicit requirement from brief. | Introduce drift; verify patch restores reference config |
| FR-7.5 | Repair actions exceeding the confidence, blast-radius, or risk threshold defined by policy shall require explicit human approval before execution. | Must | Core safety requirement (Section 12). | Trigger a low-confidence scenario; verify approval gate is invoked |
| FR-7.6 | After executing a repair action, the system shall verify the outcome (e.g., re-check health status / re-compare configuration) before marking the incident resolved. | Must | Prevents false "resolved" status; supports MTTR accuracy. | Verify post-repair health check runs and gates resolution |
| FR-7.7 | Repair attempts shall be subject to a configurable retry limit; exceeding the limit shall trigger escalation to a human operator rather than indefinite retries. | Must | Prevents repair loops; safety requirement. | Force repeated repair failure; confirm escalation after limit |

### 8.8 Notifications, Dashboards, Audit Trails, and Recovery History

| ID | Requirement | Priority | Rationale | Verification |
|---|---|---|---|---|
| FR-8.1 | The system shall notify designated operators when an incident is detected, when human approval is required, and when an incident is resolved. | Must | Keeps human operators informed per the human-in-the-loop model (Section 7.2). | Trigger each event type; confirm notification delivery |
| FR-8.2 | The system shall provide a dashboard or report view showing active incidents, their diagnostic status, and repair status. | Should | Needed for operator usability (NFR, Section 9). | Manual UI/report review |
| FR-8.3 | The system shall maintain an immutable audit log of every detection, diagnostic decision, chaos experiment, repair proposal, policy decision, and human approval/rejection, each linked by correlation ID. | Must | Required for OBJ-5 and academic evaluation traceability. | Trace a full incident lifecycle through the audit log |
| FR-8.4 | The system shall maintain a queryable recovery history, allowing review of past incidents and their resolutions. | Should | Supports evaluation (Section 15) and operational learning. | Query recovery history for a completed test scenario |

---

## 9. Non-Functional Requirements

| ID | Category | Requirement | Notes |
|---|---|---|---|
| NFR-1 | Reliability | The core detection and orchestration path shall not lose or silently drop incident events under normal operating conditions. | **[PROPOSED]** exact reliability target (e.g., 99.x%) to be defined once infrastructure is finalized. |
| NFR-2 | Availability | The monitoring/detection component shall be available continuously during evaluation periods. | **[PROPOSED]** specific uptime target for the demonstrator environment. |
| NFR-3 | Response Time | Failure detection shall complete within a defined latency budget after the triggering event. | **[PROPOSED]** target value (e.g., seconds to low minutes) — to be calibrated during implementation and stated in the evaluation baseline. |
| NFR-4 | Scalability | The framework shall handle at least a defined minimum number of concurrent pipelines/incidents in the demonstrator. | **[PROPOSED]** — scale target to be defined based on available infrastructure; not a primary evaluation axis for an academic prototype. |
| NFR-5 | Observability | All agent actions and decisions shall be logged with sufficient detail to reconstruct the reasoning path (see FR-2.4, FR-8.3). | Directly supports explainability and audit requirements. |
| NFR-6 | Security | Access to repair-triggering functions and configuration secrets shall be authenticated and authorized. | See Section 10.7. |
| NFR-7 | Least Privilege | Each agent shall operate with the minimum set of permissions required for its allowlisted actions. | Core safety principle (Section 12). |
| NFR-8 | Safety | No automated action shall be irreversible without an explicit human approval step. | Core safety principle (Section 12). |
| NFR-9 | Explainability | Every automated diagnostic and repair decision shall be accompanied by a human-readable rationale. | Supports both operator trust and academic evaluation. |
| NFR-10 | Maintainability | The system shall be structured so individual agents (diagnostic, chaos, repair) can be modified or replaced independently. | Supports iterative academic development. |
| NFR-11 | Portability | Core logic shall avoid hard dependencies on a single cloud provider where reasonably possible. | **[ASSUMPTION]** — full cloud-portability is not treated as a strict requirement since the brief does not mandate a specific provider; documented as a design goal. |
| NFR-12 | Usability | Operator-facing interfaces (dashboard, notifications, approval prompts) shall present enough context for a human to make an approval decision without leaving the interface. | Supports human-in-the-loop workflows (Section 7.2). |
| NFR-13 | Reproducibility | Chaos experiments and evaluation scenarios shall be repeatable with consistent configuration, to support fair before/after comparison. | Required for the evaluation methodology (Section 15). |

---

## 10. External Interface Requirements

| ID | Interface | Description | Requirement |
|---|---|---|---|
| EI-1 | CI/CD Webhook / Event Interface | Receives deployment lifecycle events from the CI/CD platform. | Shall accept incoming events via webhook or equivalent event API; shall validate event authenticity. |
| EI-2 | Cloud / Deployment API Interface | Used by the Repair Agent to execute rollback and configuration patch actions, and by the Chaos Agent to inject faults. | Shall use the deployment target's native API/CLI; all calls shall be logged with correlation ID. |
| EI-3 | Monitoring, Metrics, Logs, and Tracing Interface | Source of evidence for detection and diagnosis. | Shall support querying metrics/logs/traces for a given time window and resource scope. |
| EI-4 | Configuration Repository Interface | Source of the declared/reference configuration state used for drift comparison. | Shall support read access to the reference configuration and, for patching, controlled write/revert access. |
| EI-5 | Notification Interface | Delivers alerts and approval requests to operators. | Shall support at least one notification channel (e.g., email, chat webhook) **[ASSUMPTION — specific channel to be finalized]**. |
| EI-6 | Operator Dashboard / CLI | Human-facing interface for monitoring incidents and approving/rejecting/escalating actions. | Shall present incident status, diagnostic rationale, and pending approvals; shall support approve/reject/emergency-stop actions. |
| EI-7 | Authentication, Authorization, Secrets, and Audit-Log Interfaces | Underpins access control and traceability across all other interfaces. | Shall authenticate all agent and human actions; shall store secrets outside of plaintext logs/config; shall write to an append-only or tamper-evident audit log. |

---

## 11. Data Requirements

### 11.1 Data Entities
- **Deployment Events** — CI/CD lifecycle events (start, success, failure).
- **Failure Records** — structured records of detected deployment failures.
- **Logs, Metrics, and Traces** — raw and derived observability data used as diagnostic evidence.
- **Configuration Snapshots** — point-in-time captures of live and reference configuration.
- **Drift Findings** — structured records of detected configuration drift.
- **Diagnostic Evidence** — the evidence bundle and reasoning trace associated with a diagnosis (FR-2.2–2.4).
- **Repair Plans** — proposed repair actions, including type, target, and policy validation result.
- **Action Results** — outcomes of executed repair or chaos actions.
- **Chaos Experiment Records** — experiment definitions, execution logs, and outcomes.
- **Audit Events** — the full, correlation-ID-linked record of every decision and action in the system.

### 11.2 Data Handling Requirements

| ID | Requirement |
|---|---|
| DR-1 | Every data entity above shall carry the correlation ID of the incident (or experiment) it belongs to. |
| DR-2 | Configuration snapshots and audit events shall be retained for a defined minimum period to support evaluation and post-hoc review. **[PROPOSED — retention period to be defined; suggested minimum: duration of the academic evaluation phase.]** |
| DR-3 | Audit events shall be write-once / tamper-evident (e.g., append-only storage) to preserve trustworthiness of the audit trail. |
| DR-4 | Access to configuration data, secrets, and audit logs shall be restricted by role (Section 6). |
| DR-5 | Where deployment/monitoring data could contain sensitive information (e.g., customer data in logs), the system shall avoid unnecessary duplication or exposure of such data beyond what diagnosis requires. **[ASSUMPTION — no specific data-privacy regime specified in brief; treated as a general good-practice requirement.]** |

---

## 12. Agent Behavior and Safety Requirements

This section defines the safety envelope within which all three agents (Diagnostic, Chaos, Repair) must operate. These requirements take precedence over functional convenience — i.e., in case of conflict, safety requirements shall not be bypassed to achieve faster or more "autonomous" behavior.

| ID | Requirement | Rationale |
|---|---|---|
| SR-1 | Agent responsibilities and action boundaries shall be explicitly defined and enforced by the Policy Engine — no agent shall perform an action outside its declared responsibility. | Prevents scope creep (e.g., Diagnostic Agent taking repair actions directly). |
| SR-2 | All diagnostic conclusions shall be evidence-based; the Diagnostic Agent shall not propose a root cause without a linked evidence bundle (FR-2.2). | Supports explainability and prevents unfounded automated conclusions. |
| SR-3 | Every repair or chaos action shall have an associated confidence threshold; actions below the threshold shall require human approval. | Core control linking diagnostic uncertainty to autonomy level. |
| SR-4 | Repair and chaos actions shall be restricted to an explicit allowlist of action types (e.g., rollback, config patch, defined fault-injection types). No open-ended or dynamically-generated actions shall be permitted. | Prevents unbounded/unsafe automated behavior. |
| SR-5 | The system shall support a dry-run mode in which proposed repair actions are generated and logged but not executed. | Enables safe testing and demonstration of diagnostic/planning logic without risk. |
| SR-6 | Every repair action shall have a corresponding rollback checkpoint (e.g., prior deployment version, prior configuration snapshot) captured before execution. | Ensures actions are reversible (NFR-8). |
| SR-7 | Repair and chaos actions shall be constrained by a defined blast-radius limit (e.g., scope of resources/environments affected). | Limits worst-case impact of an incorrect automated decision. |
| SR-8 | Repair actions shall be idempotent or explicitly checked for prior execution, to avoid duplicate or conflicting repairs for the same incident. | Prevents repair loops and inconsistent state. |
| SR-9 | The system shall implement circuit breakers that halt further automated action on a given target after a defined number of consecutive failures. | Prevents cascading failures from a malfunctioning repair loop. |
| SR-10 | Automated actions shall be subject to a rate limit per target/environment. | Limits potential damage from rapid repeated automated actions. |
| SR-11 | Any incident where diagnostic confidence is below threshold, or where the proposed action falls outside the allowlist, shall be escalated to a human operator rather than defaulted to inaction or forced action. | Ensures uncertain/high-risk cases are never silently resolved either way. |

---

## 13. Use Cases and Workflows

### UC-1: Failed Deployment Diagnosis and Rollback
1. CI/CD platform reports a failed deployment (or failed post-deploy health check).
2. System creates an incident with a correlation ID (FR-1.5).
3. Diagnostic Agent collects evidence and produces a root-cause hypothesis with confidence score (FR-2.1–2.4).
4. Repair Agent proposes rollback to last known-good version (FR-7.3).
5. Policy Engine validates the action (FR-7.2); if confidence/blast-radius is within allowlisted bounds, rollback executes automatically; otherwise, operator approval is requested (FR-7.5).
6. Post-repair verification confirms service health (FR-7.6).
7. Incident marked resolved; audit trail updated (FR-8.3).

### UC-2: Configuration-Drift Detection and Patching
1. Scheduled or event-triggered comparison detects drift between live and reference configuration (FR-3.1).
2. Drift severity is classified (FR-3.2); a configuration snapshot is recorded (FR-3.3).
3. Diagnostic Agent confirms the drift and its likely cause/impact.
4. Repair Agent proposes a configuration patch reverting to reference state (FR-7.4).
5. Policy Engine validates; auto-executes if within policy, else requests approval.
6. Post-patch verification confirms configuration matches reference; incident resolved.

### UC-3: Runtime Performance Degradation Response
1. Monitoring detects a performance anomaly (FR-4.1–4.2).
2. System attempts to correlate the anomaly with a recent deployment or configuration change (FR-4.3).
3. Diagnostic Agent produces a hypothesis (e.g., "regression introduced by deployment X") with confidence score.
4. If linked to a specific deployment, Repair Agent proposes rollback; otherwise, incident is escalated for human investigation (since automated repair for externally-caused anomalies is out of scope, Section 5.2).

### UC-4: Controlled Chaos Injection and Resilience Assessment
1. Operator or scheduler defines a chaos experiment (fault type, scope, duration) (FR-6.1).
2. System confirms the experiment is scoped to the isolated test environment (FR-6.3).
3. Chaos Agent executes the fault injection.
4. Detection, diagnosis, and repair workflows are exercised exactly as in UC-1/UC-2/UC-3, but against the injected fault.
5. Chaos Agent safely terminates the experiment at the defined duration or on manual/automatic trigger (FR-6.5).
6. Outcome (detected? diagnosed correctly? repaired successfully? within time budget?) is recorded (FR-6.6) for use in evaluation (Section 15).

### UC-5: Human Review, Override, Emergency Stop, and Post-Repair Verification
1. At any point, an operator may open the dashboard to review active incidents and pending approvals (FR-8.2).
2. For an action requiring approval, the operator reviews the diagnostic rationale and either approves, rejects, or requests more information.
3. At any point, an operator may trigger an emergency stop, halting all in-progress automated actions (Section 7.2).
4. After any repair (human-approved or automated), the system performs post-repair verification (FR-7.6) before closing the incident.

---

## 14. Technology and Implementation Constraints

The source brief does not mandate a specific technology stack. The requirements above are written to be technology-neutral. The table below lists candidate implementation choices per component; all are **[ASSUMPTION / candidate — final selection pending student/supervisor decision]**.

| Component | Candidate Options |
|---|---|
| CI/CD Platform | GitHub Actions, GitLab CI, Jenkins |
| Container Orchestration / Deployment Target | Kubernetes (self-hosted or managed, e.g., a local cluster via kind/minikube for the demonstrator) |
| Monitoring / Metrics | Prometheus + Grafana |
| Logging / Tracing | Loki or ELK stack; OpenTelemetry for tracing |
| Configuration Repository | Git-based configuration repo (GitOps-style), e.g., paired with Argo CD or Flux |
| Agent Runtime / Orchestration | Custom orchestrator (state machine) implemented in Python/Node.js, optionally using an LLM-based agent framework for the diagnostic reasoning component |
| Chaos Engineering Tooling | Chaos Mesh, LitmusChaos, or custom fault-injection scripts scoped to the demonstrator cluster |
| State Store | A lightweight database (e.g., PostgreSQL or SQLite) for incident/audit state |
| Deployment Environment (for the demonstrator) | Local or single-cloud non-production cluster **[ASSUMPTION — see Section 5.2]** |

### 14.1 Decisions Requiring Finalization Before Implementation
- Exact CI/CD platform and deployment target.
- Whether the Diagnostic Agent's reasoning is implemented via rule-based logic, an LLM-based agent, or a hybrid approach.
- Specific chaos-engineering toolchain and the exact catalog of supported fault types (FR-6.2).
- Notification channel(s) (EI-5).
- Numeric thresholds for detection latency, confidence, and blast-radius limits (flagged as **[PROPOSED]** throughout Sections 8–9).

These are documented here as **open decisions**, not as requirements, so that the requirements document remains valid regardless of which options are ultimately selected.

---

## 15. Testing and Evaluation Requirements

### 15.1 Testing Levels

| Test Level | Scope |
|---|---|
| Unit Testing | Individual agent logic (e.g., drift comparison function, confidence scoring function) tested in isolation. |
| Integration Testing | Interaction between components (e.g., Event Trigger → Orchestrator → Diagnostic Agent). |
| System Testing | End-to-end incident lifecycle (UC-1 through UC-5) in the demonstrator environment. |
| Security Testing | Access control on repair-triggering functions, secrets handling, audit-log tamper resistance (NFR-6, EI-7). |
| Fault-Injection Testing | Use of the Chaos Agent itself as the primary mechanism to test detection/diagnosis/repair (UC-4). |
| Recovery Testing | Verifies rollback and configuration-patch actions correctly restore known-good state. |
| Performance Testing | Measures detection latency and repair execution time under the demonstrator's expected load. |
| Usability Testing | **[ASSUMPTION — informal]** Operator dashboard reviewed for clarity of incident/approval information (NFR-12). |

### 15.2 Evaluation Metrics

| Metric | Definition |
|---|---|
| Detection Latency | Time from fault occurrence/injection to incident creation. |
| Diagnosis Accuracy | Proportion of incidents where the diagnosed root cause matches the actual (injected or known) cause. |
| Repair Success Rate | Proportion of incidents where the executed repair action resolved the incident without further intervention. |
| Rollback Completion Time | Time from repair initiation to verified restoration of known-good state. |
| False-Positive Rate | Proportion of flagged incidents that were not actual faults. |
| Mean Time to Recovery (MTTR) | Average time from fault occurrence to verified resolution. |
| Chaos Experiment Safety | Proportion of chaos experiments that remained within their defined scope/blast-radius with no unintended impact. |
| Human Intervention Rate | Proportion of incidents that required human approval or manual resolution, versus fully automated resolution. |

### 15.3 Baseline Comparison
The evaluation shall compare the above metrics for the self-healing pipeline against a **conventional baseline** — the same fault scenarios run against a pipeline without the self-healing framework (i.e., manual/simulated-manual diagnosis and recovery), to substantiate OBJ-6. Baseline MTTR and human-intervention rate may be estimated from a documented manual procedure if a live manual comparison is impractical within project time constraints **[ASSUMPTION]**.

---

## 16. Acceptance Criteria and Traceability

### 16.1 Acceptance Criteria (Summary)
The project shall be considered to meet its objectives when:
1. All **Must**-priority functional requirements (Section 8) are implemented and pass their associated verification method.
2. All safety requirements (Section 12) are demonstrably enforced (i.e., cannot be bypassed through normal operation).
3. At least one complete run of each use case (UC-1 through UC-5, Section 13) is demonstrated successfully.
4. The evaluation report (Section 15) shows the defined metrics for both the self-healing pipeline and the baseline, with results discussed against OBJ-6.
5. All open assumptions and proposed thresholds (marked **[ASSUMPTION]** / **[PROPOSED]** throughout this document) have been reviewed and either confirmed or revised by the supervisor.

### 16.2 Requirements Traceability Matrix (Structure)

| Objective | Related Requirements | Related Use Case(s) | Test/Evidence | Acceptance Status |
|---|---|---|---|---|
| OBJ-1 | FR-1.1–FR-1.5, FR-3.x, FR-4.x | UC-1, UC-2, UC-3 | Fault-injection tests, detection logs | *[to be completed during evaluation]* |
| OBJ-2 | FR-2.1–FR-2.4, FR-5.1, SR-2 | UC-1, UC-2, UC-3 | Diagnostic session records | *[to be completed]* |
| OBJ-3 | FR-6.1–FR-6.6 | UC-4 | Chaos experiment records | *[to be completed]* |
| OBJ-4 | FR-7.1–FR-7.7, SR-1–SR-11 | UC-1, UC-2, UC-5 | Repair action logs, policy decision logs | *[to be completed]* |
| OBJ-5 | FR-8.3, DR-1–DR-4 | All | Audit log review | *[to be completed]* |
| OBJ-6 | Section 15 metrics | All | Evaluation report | *[to be completed]* |

*(This table is a structural template; it should be populated with concrete test evidence and pass/fail status during the evaluation phase.)*

---

## 17. Risks, Assumptions, Dependencies, and Open Decisions

### 17.1 Risks

| ID | Risk | Potential Impact | Mitigation |
|---|---|---|---|
| RISK-1 | Cloud/API access or permissions may be restricted or unavailable for the chosen deployment target. | Blocks integration testing. | Use a local/self-hosted demonstrator environment (e.g., local Kubernetes cluster) as a fallback. |
| RISK-2 | Observability data quality/coverage may be insufficient for reliable anomaly detection. | Reduces diagnosis accuracy; increases false positives/negatives. | Scope initial detection to a small, well-instrumented set of metrics; expand iteratively. |
| RISK-3 | Chaos experiments may unintentionally impact resources outside the intended scope. | Safety/reliability risk to the demonstrator environment. | Strict environment isolation (FR-6.3) and blast-radius limits (SR-7); dry-run mode (SR-5) for initial validation. |
| RISK-4 | Diagnostic/repair logic reliability may be lower than expected, especially for a prototype-stage agentic system. | Reduces evaluation metrics; may require more human intervention than targeted. | Report actual measured performance honestly; treat human-intervention rate as a legitimate evaluation metric rather than a failure condition. |
| RISK-5 | Time constraints of an M.Tech project may not allow a full production-grade implementation of all "Should"/"Could" requirements. | Some non-Must requirements may be deferred. | Prioritize Must-priority requirements (Section 8) for the core deliverable; document deferred items explicitly. |

### 17.2 Assumptions
- The project targets a **non-production demonstrator environment**, not a live production system (Section 5.2).
- The technology stack (CI/CD platform, deployment target, monitoring stack, agent runtime) is **not fixed by the brief** and is treated as an open implementation decision (Section 14).
- Numeric thresholds throughout this document (latency budgets, confidence thresholds, retention periods) are **proposed placeholders** pending supervisor input.
- A single supervised demonstrator environment is sufficient for evaluation; multi-tenant or multi-team scenarios are out of scope.

### 17.3 Dependencies
- Availability of a deployment target environment (cloud account or local cluster) with sufficient permissions to simulate deployments, drift, and faults.
- Availability of monitoring/logging tooling compatible with the chosen deployment target.
- Supervisor approval of the autonomy boundaries defined in Section 12, before any automated (non-dry-run) repair actions are enabled.

### 17.4 Open Decisions for Supervisor Confirmation
1. Final technology stack selection (Section 14).
2. Numeric thresholds for detection latency, confidence scores, and blast-radius limits (Sections 8–9).
3. Data retention period for configuration snapshots and audit logs (DR-2).
4. Whether a live manual-baseline comparison is feasible, or whether an estimated/documented baseline is acceptable (Section 15.3).
5. Final catalog of supported chaos fault types (FR-6.2).
6. Notification channel(s) to be used (EI-5).

---

## 18. Glossary and References

### 18.1 Glossary

| Term | Definition |
|---|---|
| CI/CD | Continuous Integration / Continuous Deployment — the automated pipeline that builds, tests, and deploys application changes. |
| Configuration Drift | The divergence of a live system's configuration from its declared or last known-good reference state. |
| Chaos Engineering | The practice of deliberately injecting controlled faults into a system to test its resilience and recovery mechanisms. |
| Rollback | Reverting a deployment to a previous, known-good version. |
| Root-Cause Analysis (RCA) | The process of identifying the underlying cause of an observed failure or anomaly. |
| Observability | The ability to infer the internal state of a system from its external outputs (logs, metrics, traces). |
| Agent | An autonomous or semi-autonomous software component that perceives evidence/state and takes action (diagnostic, chaos, or repair) within defined boundaries. |
| Self-Healing | The capability of a system to automatically detect and recover from certain classes of failure without requiring manual intervention, within defined safety limits. |
| Blast Radius | The scope of systems/resources that could be affected by a given automated action. |
| MTTR | Mean Time to Recovery — the average time taken to restore a system to a working state after a failure. |

### 18.2 References
- Supplied one-page project brief: *"Self-Healing Cloud Deployment Pipelines"* (source document for this PRD; original brief on file with the student/supervisor).
- Additional authoritative external references (e.g., academic literature on chaos engineering, self-healing systems, or agentic AI architectures) may be added in a later revision if external research is requested or required for the final academic submission.

---

*End of document. Sections and items marked* **[ASSUMPTION]** *or* **[PROPOSED]** *throughout should be reviewed with the project supervisor and either confirmed, revised, or removed before finalizing the requirements baseline for implementation.*

