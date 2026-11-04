# Monitoring

Planned signals (Phase 8):

| Signal | Why |
|---|---|
| API P95 latency and error rate | Requirement compliance and early regression detection |
| Queue depth and dead-letter count | Ingestion backpressure before it becomes data loss |
| Inference latency and failure rate | Model service health |
| Model drift (feature distribution shift) | Silent accuracy decay is the dangerous failure |
| Alert delivery status | FR-057 |

Model drift deserves the emphasis: a vision model degrades quietly when a factory switches fabric
supplier. Accuracy monitoring against a frozen reference window is the only way that surfaces
before an operator notices defects the system has stopped seeing.
