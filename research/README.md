# Research Harness

This directory holds the parts of the project that make results reproducible and auditable rather
than merely claimed.

- `literature-review/` — source notes and the gap analysis that justifies the architecture.
- `experiments/` — one directory per experiment (E1–E5), each with config, command, logs, results.
- `evaluation/` — metrics definitions, scoring rubrics, and the scripts that compute them.
- `reports/` — generated tables and figures consumed by the final write-up.

## Experiment record format

Every run writes a result record containing:

```json
{
  "experiment": "E1",
  "dataset_version": "aitex-afid@v1",
  "split": "group-by-fabric-roll",
  "model_version_id": "<uuid in model_versions>",
  "config": {"epochs": 100, "imgsz": 640, "seed": 42},
  "hardware": "GPU model / CPU, RAM",
  "metrics": {"map50": null, "map50_95": null, "precision": null, "recall": null, "latency_ms_p95": null},
  "failure_cases": []
}
```

Metrics left `null` are unruns, not unknown successes. A result without dataset version, split and
hardware is not a result.

See [`../docs/research.md`](../docs/research.md) for the questions and design.
