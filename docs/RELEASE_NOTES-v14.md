# CAMV-Eval v14 numerical reproduction

This release supports **Threshold Calibration and Bootstrap Inference for Multi-View Grasp Verification**, manuscript v14–v14.3, by Minsu Jo, Namhyun Yoo, Beomseok Kim, Hoansuk Choi, and Jinhong Yang.

It adds four empirical-group-population conditions with 2,000 independent outer datasets, 4,000 paired-scorer records, 999 bootstrap draws per record, independent reference targets, and supporting empirical/statistical audit snapshots. The separate v8 and v12 releases are preserved.

Download both assets. The ZIP is a public transport export: frozen scientific inputs, code, arrays and CSVs are unchanged; four internal prose review-response reports are omitted, and public documentation/manifests are updated with explicit provenance. It contains no manuscript submission PDF, response-to-reviewers document, source images, model weights, author photos or API credentials.

See `docs/REPRODUCIBILITY-v14.md`, `v14-assets.json` and `results/v14`. The verified portable entry point recalculates saved intervals and summaries; its optional bounded regeneration checks six selected outer datasets. A1–A7 audit tables are labeled snapshots rather than fully replayed raw audits. Reproduction does not establish uniform nominal confidence coverage or general verifier performance.

Author-owned software uses MIT; third-party materials retain their original terms. No journal publication or acceptance is asserted.
