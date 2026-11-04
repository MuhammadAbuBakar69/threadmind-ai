# Research Design

## 1. Questions

- **RQ1** — How effectively can computer vision models detect and localize textile fabric defects
  under different fabric textures and lighting conditions?
- **RQ2** — How accurately can ML models identify abnormal machinery behaviour and estimate
  failure risk from industrial sensor data?
- **RQ3** — Can correlating machine telemetry, production events and visual defects improve root
  cause investigation compared with analyzing these sources independently?
- **RQ4** — Can a coordinated multi-agent architecture produce more useful, evidence-grounded
  manufacturing recommendations than a single general-purpose LLM?
- **RQ5** — How effectively can the proposed cloud architecture support real-time monitoring,
  scalability, reliability and multi-factory isolation?

## 2. Hypotheses (to be tested, not assumed)

- **H1** A properly trained, properly evaluated vision model identifies selected textile defects
  with measurable accuracy and localization performance.
- **H2** ML-based anomaly detection identifies abnormal operating conditions earlier than fixed
  threshold monitoring on the tested datasets.
- **H3** Cross-domain correlation between machine condition and quality events improves root cause
  investigation quality.
- **H4** A specialized multi-agent workflow with deterministic validation and evidence retrieval
  produces more traceable recommendations than an unconstrained LLM workflow.

## 3. Method

Design Science Research: identify the problem, review literature, define requirements, design the
architecture, develop components, integrate agents, run controlled experiments, evaluate, document
limitations.

## 4. Experiments

| # | Experiment | Compare | Primary measures |
|---|---|---|---|
| E1 | Fabric defect detection | YOLO baseline, U-Net, PatchCore, optional transformer | Precision, recall, F1, mAP@50, mAP@50:95, IoU, latency, model size |
| E2 | Machine anomaly detection | Isolation Forest, autoencoder, XGBoost where labels exist | AUROC, AUPRC, false alarms/hour, detection lead time |
| E3 | Root cause investigation | Correlation+rules only, LLM-only, evidence-grounded multi-agent | Expert-reviewed rubric: correctness, evidence relevance, completeness, unsupported claims, recommendation usefulness |
| E4 | Production analytics | Forecasting and bottleneck detection on historical or simulated records | Forecast error, bottleneck agreement with ground truth |
| E5 | Integrated system | End-to-end ingestion → human-reviewed recommendation | End-to-end latency, reliability, consistency, agent success rate, traceability |

## 5. Controls

Fixed seeds. Separate train/validation/test sets. No leakage between splits — split by original
fabric image, roll, acquisition session or source, never by random patch. Recorded model configs.
Preserved experiment logs. Identical evaluation splits across competing models. Confidence
intervals where appropriate. Multi-category evaluation. Failure cases reported, not only wins.

## 6. Threats to validity

Public datasets may not represent local manufacturing. Defect categories may be narrow.
Predictive-maintenance datasets are not weaving or knitting machines. Sensor access may be limited.
Reliable failure labels may not exist. Root cause analysis is constrained by missing history.
Multi-agent reasoning adds latency and cost. A model trained on a non-commercial dataset inherits
its restrictions.

## 7. Reporting rule

Every quantitative claim in the final report names the dataset version, split, model version, and
hardware it was measured on. A number without that provenance is not a result.
