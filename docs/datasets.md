# Dataset Inventory and Governance

## 1. Position

Three data categories: public datasets for reproducible baselines, synthetic or simulated
industrial data, and real factory data subject to permission. Public datasets establish baselines;
they do **not** establish performance in Pakistani textile factories.

## 2. Fabric defect datasets

| Dataset | Source | Scale | Use | Limitation |
|---|---|---|---|---|
| AITEX AFID | aitex.es/afid | 245 images, 7 fabric types, 140 clean / 105 defective, masks available | Initial classification, segmentation, baseline benchmarking | Small; not sufficient evidence of industrial generalization |
| MVTec AD | mvtec.com/research-teaching/datasets/mvtec-ad | 5,000+ images, 15 categories, pixel-level annotations | Industrial anomaly detection, PatchCore experiments | **Non-commercial license** — check before redistribution or commercial use |
| DME Fabric Defect | data.mendeley.com/datasets/4fcvnr77sb/1 | Multi-category fabric images: stains, damage, broken threads, holes, clean | Fabric-specific training and validation, cross-fabric generalization | Verify exact version, annotations and license before use |
| Lusitano Fabric Defect | kailashhambarde.github.io/Lusitano | Fabric texture variation | Additional variation, normal-vs-defective, cross-dataset evaluation | Distribution and licensing must be checked |

## 3. Predictive maintenance datasets

| Dataset | Source | Characteristics | Use | Limitation |
|---|---|---|---|---|
| UCI AI4I 2020 | archive.ics.uci.edu/dataset/601 | 10,000 observations, failure labels | Failure classification, feature importance, XGBoost baseline | Synthetic; not textile-specific |
| NASA C-MAPSS | data.nasa.gov (C-MAPSS) | Run-to-failure engine trajectories | Sequential degradation, RUL experiments, time-series feature engineering | Aircraft engines differ from textile machinery |
| MIMII DUE | zenodo.org/records/4740355 | Normal/abnormal industrial machine sound, multiple machine types and conditions | Acoustic anomaly detection, domain shift | Not textile-specific recordings |

## 4. Real factory collection

A permission-based textile factory dataset is a primary research contribution.

- **Telemetry** — machine id, timestamp, temperature, vibration, speed, torque, current, operating status.
- **Inspection** — original image, fabric type, defect category, location, severity, expert verification.
- **Production** — batch id, line, machine id, fabric type, quantity, shift, timestamps.
- **Maintenance** — machine id, date, fault description, activity, downtime, resolution.

Collection and research use require factory authorization. Personally identifying employee
information is not collected unless strictly necessary and appropriately authorized.

## 5. Governance

Every dataset records: source and acquisition date, license and usage restrictions, version,
annotation methodology, train/validation/test assignment, preprocessing configuration, quality
report, and reproducibility metadata.

**Leakage rule:** never train and test on overlapping crops of the same original image.

**Licensing rule:** MVTec AD is non-commercial. Any model intended for commercial deployment must
be retrained on appropriately licensed data. This is a product blocker, not a footnote.
