# Root Cause Engine

The research centre of ThreadMind. It connects visual defects, machine condition, production
history, and maintenance records to investigate *why* an operational problem occurred (FR-030 →
FR-036).

## Pipeline

1. Detect a quality abnormality.
2. Resolve its production batch and machine.
3. Retrieve sensor measurements around the event.
4. Compare against the historical normal range for that machine and fabric type.
5. Retrieve related maintenance records.
6. Analyze defect frequency over time.
7. Generate candidate explanations.
8. Rank them with an explicit evidence-scoring function.
9. Present uncertainty and alternative hypotheses.
10. Request human verification.

## Methods

Temporal correlation, change-point detection, feature importance (SHAP), anomaly analysis,
rule-based reasoning, historical retrieval, LLM-generated explanation prose.

## Two limits that are built into the code

**SHAP explains model contributions, not physics.** A high feature attribution for vibration means
the model leaned on vibration; it does not mean vibration caused the defect.

**Correlation is not causation.** Every hypothesis carries `claim_kind`
(`observed_fact` / `association` / `hypothesis`), and a confidence score that is computed by the
ranking function rather than narrated by a language model. Causal claims require data and
assumptions this project does not yet have, and are listed as future work, not results.

## Why this is the contribution

Defect detection and predictive maintenance are established. The open question is whether
correlating them, with evidence and traceability, produces materially better diagnosis than
inspecting either source alone. Experiment E3 exists to answer that honestly — including the
possibility that it does not.
