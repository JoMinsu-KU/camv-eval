# CAMV-Eval v12 numerical reproduction package

This release supplements the unchanged v8 numerical release for *Calibration and Bootstrap Inference for Multi-View Grasp Verification*.

It adds three targeted simulation conditions (3,000 outer datasets; 999 paired bootstrap draws each), 32,768 independent reference development datasets, a development/evaluation decomposition of 16,000 previously saved datasets, a seed-output identity audit, and fixed-operating-point Youden J. Original numerical results and the four FSR tests remain unchanged. Frozen code, numerical arrays, portable projections, SHA-256 receipts and replay commands are included. No new VLM inference is performed.

Download the ZIP and use the pinned dependencies and `reproduce_v12.py` command in docs/REPRODUCIBILITY-v12.md. The archive also has its own replay entry point. MIT applies to author-owned software; external records retain their original terms. Source images, model weights, author photographs, manuscript files, and private author-review documents are outside this release.

The class-profile simulations and structured null are specific generated laws. The results do not establish uniformly valid procedure-average coverage or general null calibration. The associated manuscript remains an author-review draft; no journal acceptance or paper DOI is asserted.
