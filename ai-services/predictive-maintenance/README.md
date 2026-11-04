# Predictive Maintenance Service

Scores machine condition from telemetry and estimates failure risk where labelled data supports it
(FR-022 → FR-027).

## Features

Temperature, vibration, rotational speed, torque, motor current, pressure, operating duration,
utilization, maintenance history. Not every factory exposes every signal — the feature contract
records which are present so a model trained with nine inputs is never silently served seven.

## Candidate models

| Model | Role |
|---|---|
| Isolation Forest | Unsupervised anomaly baseline |
| XGBoost | Supervised failure classification when reliable labels exist |
| LSTM | Sequential degradation patterns |
| Autoencoder | Learned normal behaviour, reconstruction-error anomaly |
| Forecasting model | Deviation from expected operating condition |

## Outputs

Anomaly score. Failure probability where a calibrated supervised model supports it. Risk category.
Feature contributions. Recommended inspection priority.

## One thing this is not

A classification probability is **not** Remaining Useful Life. RUL requires a separate validated
prognostic model trained on run-to-failure data. Publishing a classifier's output as "days until
failure" is the single easiest way to lose an engineer's trust permanently, so the field is absent
rather than approximate.
