# Business Requirements Document (BRD)

**Project:** ThreadMind AI · **Version:** 1.0 · **Status:** Initial baseline

## 1. Business vision

Create an intelligent manufacturing platform that helps textile factories understand production
conditions, detect operational problems, and make evidence-based decisions. Initial market:
textile and garment manufacturers in Pakistan.

Target segments: textile mills, weaving factories, knitting factories, garment manufacturers,
fabric processing facilities, textile exporters, industrial production groups.

## 2. Business problem

A factory may already own visual inspection systems, machine sensors, production management
software, and maintenance records — and still lack operational intelligence, because those
systems do not talk to each other. Quality problems and machinery problems are investigated
separately, historical information is fragmented across departments, and recurring defects
resist root-cause analysis.

## 3. Business solution

| Capability | Business value |
|---|---|
| Automated quality inspection | Better defect visibility |
| Predictive maintenance | Earlier maintenance warnings |
| Root cause investigation | Faster problem investigation |
| Production optimization | Better operational decisions |
| Factory intelligence | Centralized manufacturing insights |

## 4. Stakeholders

| Stakeholder | Responsibility |
|---|---|
| Factory owner | Business oversight |
| Factory manager | Production supervision |
| Quality manager | Quality performance |
| Quality inspector | Defect verification |
| Maintenance engineer | Machinery maintenance |
| Production supervisor | Production operations |
| System administrator | Platform configuration |
| Researcher | Model development and evaluation |

## 5. Success criteria

Pilot targets, **not** guaranteed performance claims. All must be revised after baseline
experiments and factory requirements are established.

| Indicator | Initial target |
|---|---|
| Defect detection | mAP@50 ≥ 0.85 on the defined test benchmark |
| Defect localization | Precision, recall and IoU reported |
| Machine anomaly detection | AUROC ≥ 0.85 on a suitable held-out dataset |
| Alert processing | P95 < 5 s for supported online telemetry workflows |
| Dashboard availability | 99.5% monthly pilot target |
| Root cause reports | Every diagnosis contains supporting evidence |
| Report generation | Automated PDF and CSV export |
| Tenant security | Zero cross-tenant data access in security tests |

## 6. Business model

Proposed B2B SaaS, priced only after validating operational value, infrastructure cost, and
willingness to pay with actual textile businesses.

- **Starter** — one production facility, limited machines.
- **Professional** — multiple machines, AI inspection, predictive maintenance.
- **Enterprise** — multi-factory, advanced analytics, custom integrations, dedicated deployment.

## 7. Constraints

Real factory data is hard to obtain. Public datasets may not represent Pakistani factory
conditions. Sensor access may require new hardware. Factory internet connectivity may be
unreliable. Machines expose different data formats. Industrial AI recommendations require human
verification. Commercial deployment requires appropriate dataset and model licensing.
