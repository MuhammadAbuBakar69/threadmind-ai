# Fabric Vision Service

Detects and localizes defects in fabric images. Returns classifications with confidence and
bounding boxes or masks (FR-015 → FR-017). This is the only component permitted to assert that a
defect exists; the agents interpret its output, they do not invent it.

## Target classes (provisional — final set depends on data and expert agreement)

hole · stain · broken thread · missing yarn · knot · tear · weaving irregularity · normal

## Candidate models

| Model | Role | Why |
|---|---|---|
| YOLO | Baseline detector | Real-time capable, box output, practical deployment |
| U-Net | Pixel-level segmentation | Available where mask annotations exist |
| PatchCore | Industrial anomaly detection | Works with few or no defect labels |
| Transformer detector | Optional research comparison | Tests whether attention helps on periodic fabric texture |

## Evaluation

Precision, recall, F1, mAP@50, mAP@50:95, IoU, pixel-level AUROC (segmentation/anomaly), inference
latency, model size.

## The mistake that invalidates the whole experiment

Fabric images are often tiled into patches. Splitting patches randomly puts crops of the *same*
roll into both train and test, and the model memorizes texture instead of learning defects. Split
by original image, roll, acquisition session or fabric source. Group-based splitting is declared in
`configs/` and asserted in `evaluation/`, not left to whoever writes the loader.
