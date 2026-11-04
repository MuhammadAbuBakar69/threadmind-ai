# Software Requirements Specification (SRS)

**Project:** ThreadMind AI · **Version:** 1.0 · **Status:** Initial baseline

Requirement IDs are the audit spine of this repository: issues, pull requests, tests and
experiments must cite the ID they satisfy.

## 1. System scope

Multi-tenant cloud platform accepting data from industrial cameras and uploaded fabric images,
IoT sensors and simulated telemetry, machine operating logs, production batch records, quality
inspection records, maintenance history, and technical documentation.

## 2. Roles

| Role | Core permissions |
|---|---|
| Super Administrator | Organizations, tenant configuration, platform services, system settings |
| Factory Administrator | Factories, production lines, machine registration, employee invites, access config |
| Factory Manager | Factory-wide analytics, AI recommendation review, production reports |
| Quality Inspector | Inspection results, confirm/reject/correct defects, quality history |
| Maintenance Engineer | Machine health, anomaly investigation, maintenance recording, recommendation confirmation |
| Production Supervisor | Batch monitoring, efficiency and waste indicators, optimization reports |

## 3. Functional requirements

### Module A — Authentication and organization management

| ID | Requirement |
|---|---|
| FR-001 | Provide secure user registration and authentication |
| FR-002 | Support role-based access control |
| FR-003 | Support multiple organizations |
| FR-004 | Isolate factory, machine, production and inspection data per organization |
| FR-005 | Administrators can invite, disable and manage users |
| FR-006 | Record important administrative actions |

### Module B — Factory and machine management

| ID | Requirement |
|---|---|
| FR-007 | Administrators can create factories |
| FR-008 | Users can register production lines |
| FR-009 | Users can register machines |
| FR-010 | Every machine has a unique identifier within its factory |
| FR-011 | Machine records hold type, manufacturer, model, installation date, operating status |
| FR-012 | Maintain machine operating history |

### Module C — Fabric quality inspection

| ID | Requirement |
|---|---|
| FR-013 | Accept fabric images |
| FR-014 | Support image preprocessing |
| FR-015 | Vision service identifies supported fabric defects |
| FR-016 | Return defect classifications and confidence scores |
| FR-017 | Support localization via bounding boxes or segmentation masks |
| FR-018 | Store inspection results |
| FR-019 | Authorized inspectors can verify or correct AI predictions |
| FR-020 | Associate inspection results with production batches and machines when identifiers exist |
| FR-021 | Generate quality summaries |

### Module D — Predictive maintenance

| ID | Requirement |
|---|---|
| FR-022 | Receive machine sensor readings |
| FR-023 | Validate sensor data |
| FR-024 | Identify abnormal sensor patterns |
| FR-025 | Estimate machine failure risk with a trained model |
| FR-026 | Provide anomaly score and risk category |
| FR-027 | Generate maintenance alerts |
| FR-028 | Authorized engineers can record maintenance activities |
| FR-029 | Maintain machine condition history |

### Module E — Root cause analysis

| ID | Requirement |
|---|---|
| FR-030 | Collect relevant quality events, machine readings, production records, maintenance history |
| FR-031 | Identify temporal relationships between production abnormalities and machine events |
| FR-032 | Retrieve relevant technical documentation |
| FR-033 | Generate ranked possible explanations |
| FR-034 | Each explanation contains supporting evidence and confidence information |
| FR-035 | Distinguish observed facts, statistical associations, and unverified hypotheses |
| FR-036 | Users can review, confirm, reject, or annotate an investigation |

### Module F — Production optimization

| ID | Requirement |
|---|---|
| FR-037 | Calculate production performance indicators |
| FR-038 | Identify production bottlenecks |
| FR-039 | Analyze waste and defect trends |
| FR-040 | Generate optimization recommendations |
| FR-041 | Recommendations include supporting data and expected impact where calculable |

### Module G — AI agent orchestration

| ID | Requirement |
|---|---|
| FR-042 | Provide a central orchestration service |
| FR-043 | Orchestrator delegates tasks to specialized agents |
| FR-044 | Agents exchange structured outputs |
| FR-045 | Maintain agent execution history |
| FR-046 | Support workflow retries and failure handling |
| FR-047 | Support human approval for consequential recommendations |
| FR-048 | Prevent agents from independently executing machine-control commands |

### Module H — Analytics and reporting

| ID | Requirement |
|---|---|
| FR-049 | Dashboard displays factory health indicators |
| FR-050 | Dashboard shows machine health and quality trends |
| FR-051 | Filter by date, machine, factory, production line, batch |
| FR-052 | Generate PDF reports |
| FR-053 | Export analytical data as CSV |
| FR-054 | Provide historical trend visualizations |

### Module I — Notifications

| ID | Requirement |
|---|---|
| FR-055 | Generate alerts for configured quality and machinery events |
| FR-056 | Users can configure notification preferences |
| FR-057 | Record alert delivery status |
| FR-058 | Escalate critical notifications per configurable rules |

## 4. Non-functional requirements

**Performance** — P95 < 500 ms for ordinary database-backed requests excluding AI inference.
Configurable telemetry throughput. Image inference benchmarked against defined dimensions and
hardware. Dashboard charts support pagination and aggregation.

**Scalability** — Multi-organization. Horizontally scalable inference. Online ingestion separated
from offline analytics. Asynchronous queues for long-running AI tasks.

**Reliability** — Retry transient failures. Durable event records. Backups and restoration.
Service health monitoring.

**Security** — TLS externally, encryption at rest, role-based authorization, tenant-level
isolation, upload validation, secrets outside source code, audit logs.

**Maintainability** — Modular services, versioned APIs, documented schema, automated tests,
reproducible training.

**Explainability** — Display predictions with confidence. Preserve evidence used in
investigations. Record model version and data provenance. Never present correlation as causation.

**Availability** — 99.5% pilot target; health checks and monitoring on critical services.

## 5. Boundaries

**Included:** cloud factory intelligence, computer vision, machine anomaly detection, predictive
maintenance, root cause investigation, production analytics, agent workflows, human approval,
enterprise dashboard.

**Excluded from the initial implementation:** autonomous physical machine control, guaranteed
prediction of every failure, replacement of inspectors, replacement of ERP/MES, certified
industrial safety control, unvalidated causal claims.

## 6. Acceptance criteria

The integrated prototype is accepted when users can create factories, register machines, upload
and inspect images, visualize defects, ingest sensor readings, receive model predictions, launch
investigations from quality and maintenance events, obtain evidence-referenced root cause reports,
have the orchestrator coordinate all five agents, review and approve recommendations, use
historical analytics and reports, and run the system in a secured cloud environment with
reproducible documented results.
