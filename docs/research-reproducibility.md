# Research Reproducibility

ThreadMind's primary contribution is an experimental claim (RQ3, RQ4). A claim that cannot be re-run
is an anecdote, so reproducibility is treated as an engineering requirement with tests behind it, not
as a note in a methodology chapter.

---

## 1. What is reproducible today

| Mechanism | Implementation | Proof |
|---|---|---|
| Deterministic telemetry | `SimulationConfig(seed=…)` → identical bytes | `test_same_config_produces_identical_output` |
| Config fingerprint | `config_hash()` = SHA-256 of the full config, 16 hex chars | `test_config_hash_is_stable_and_sensitive` |
| Ground-truth labels | `ground_truth()` records scenario, fault window, seed, window bounds | `test_fault_window_is_labelled` |
| Dataset artifacts | `write_dataset()` emits `readings.jsonl`, `ground_truth.json`, `simulation_config.json` | `test_write_dataset_produces_reproducible_artifacts` |
| Corruption provenance | each reading carries `corruptions[]` | `test_corruptions_are_injected` |
| Honest labelling of synthetic data | every truth file carries a "not evidence of predictive performance" note | asserted in the test |

A run is identified by its `config_hash`. Any result table in the thesis should cite the hash and the
seed, which together reproduce the input exactly.

---

## 2. Dataset manifests

Every dataset used in an experiment gets a manifest before it is used:

```yaml
dataset: mvtec-ad
version: "1.0"
license: non-commercial-research
acquired: 2026-11-10
source: https://www.mvtec.com/research-teaching/datasets/mvtec-ad
sha256: <archive hash>
categories_used: [carpet, grid, leather, tile, wood]
split_strategy: group-by-image
split_counts: {train: 0, val: 0, test: 0}
leakage_controls: [group_by_original_image, no_crop_overlap]
preprocessing: {resize: 512x512, normalization: imagenet}
notes: |
  Non-commercial. May not be redistributed. Check before any commercial training run.
```

Rules, all of which cost a minute now and a re-run later:

- The manifest lives beside the data and is committed; the data itself is not.
- `split_strategy` is recorded because "we split randomly" is not reproducible.
- `sha256` is recorded because a dataset URL is not a version.
- `license` is recorded because MVTec AD is non-commercial and that constraint propagates to any
  model trained on it.

**Status:** the schema above is specified; no manifest exists yet because no public dataset has been
downloaded. This is honest debt, tracked in #2 and #17.

---

## 3. Leakage controls

The failure this prevents: fabric images cropped from one original roll appearing in both train and
test. The model memorises the roll's texture and reports excellent metrics that vanish in a real mill.

| Data | Grouping key | Why |
|---|---|---|
| Fabric images | original image / roll / acquisition session | patches from one roll are near-duplicates |
| Telemetry | machine + session | a fault period must not straddle the split |
| Root cause cases | investigation id | evidence for one case leaks the answer for another |

Reporting rule: **cross-dataset and cross-factory results are reported separately from in-dataset
results.** A model trained and tested on AITEX tells you about AITEX.

---

## 4. Metric definitions (fixed before any experiment runs)

### Vision (E1)

`precision`, `recall`, `F1` per class and macro; `mAP@50`; `mAP@50:95`; mean IoU for localisation;
pixel AUROC for segmentation and anomaly maps; latency (ms/image) at declared batch size and
hardware; model size (MB).

Reported with confidence intervals from ≥3 seeds. The BRD target (`mAP@50 ≥ 0.85`) is a **proposal**
until E1 produces a number, at which point the document is corrected to the measured value.

### Predictive maintenance (E2)

`AUROC`, `AUPRC`, false alarms per operating hour, detection lead time (minutes from first alarm to
fault start). RUL is **not reported** unless a separately validated prognostic model and
run-to-failure data exist; an anomaly score is never labelled a failure probability.

### Root cause (E3)

Expert-rated on a rubric fixed in advance: correctness (1-5), evidence relevance (1-5), completeness
(1-5), unsupported-claim count (integer, lower is better), recommendation usefulness (1-5). Two
independent raters, inter-rater agreement reported (Cohen's κ). Unsupported-claim count is the
headline metric, because it is the one the evidence-grounded design is meant to move.

### System (E5)

End-to-end p50/p95 latency, agent success rate, traceability rate (share of recommendations whose
evidence references resolve), cross-tenant access attempts observed (must be zero).

---

## 5. Baselines that must be run

An architecture claim without a baseline is marketing. Each experiment includes:

1. **Trivial baseline** — threshold rule or majority class.
2. **Standard ML baseline** — the strongest conventional model for the task.
3. **The proposed component** — e.g. evidence-grounded multi-agent investigation.
4. **Ablation** — the proposal minus its distinguishing feature (multi-agent → single agent;
   evidence-grounded → LLM-only).

E3's expected shape: LLM-only produces fluent, confident, occasionally fabricated explanations;
evidence-grounded produces fewer hypotheses with higher support. If the ablation does not separate,
the research contribution is not supported and the thesis should say so.

---

## 6. Artifact layout per experiment

```text
research/experiments/E3-root-cause/
├── manifest.yaml            # config, dataset manifests, seeds, code commit
├── cases/                   # input cases (ids only, not data)
├── runs/
│   ├── run-01/              # one per seed
│   │   ├── outputs.jsonl
│   │   ├── metrics.json
│   │   └── logs/
├── aggregate/
│   ├── metrics.csv          # mean ± CI per configuration
│   └── failure-cases.md     # every failure, described
└── README.md                # how to reproduce, exact commands
```

`manifest.yaml` records the **git commit** of the code that produced the run. Without it, a result is
attached to a repository, not to a version of it.

---

## 7. What may never be reported

Stated as prohibitions because these are the tempting shortcuts:

- Synthetic-data detection performance as evidence about real looms. The simulator validates a
  pipeline.
- A metric from a single seed as a result.
- In-dataset performance as generalisation.
- An anomaly score as a failure probability.
- Correlation presented as causation; SHAP values presented as physical causes.
- A BRD target presented as an achieved result.
- Any number produced by an LLM. Numbers come from models or deterministic computation, and the
  evidence validator enforces it.

---

## 8. Blockers

| Blocker | Effect on research | Owner |
|---|---|---|
| No real factory data | Cannot claim local generalisation (REAL-03) | Factory partnership |
| Dataset licences unconfirmed (DME, Lusitano) | Cannot train commercially | User review |
| No GPU host | E1 latency benchmarks unrepresentative | Infra |
| No IdP | Multi-user E5 evaluation limited | User decision |
