# CAMV-Eval v8 numerical reproduction package

This release corresponds to manuscript v8 of *Calibration and Bootstrap Inference for Multi-View Grasp Verification* by Minsu Jo, Namhyun Yoo, and Jinhong Yang.

The repository provides a small offline Table 5 reproduction, a single full numerical replay command, byte-preserved scientific code snapshots, MIT licensing for author-owned code, and all 51 manuscript display tables. The three attached ZIPs preserve the original numerical archive and v7/v8 audits. Download all three without renaming them; their SHA-256 hashes and sizes are in `assets.json`.

```sh
python -m pip install -r requirements.txt
python reproduce.py --mode all --assets-dir ../release-assets --output ../camv-full
```

The full command recalculates original empirical analyses from stored scores, summarizes simulation arrays, performs bounded deterministic regeneration, and checks the additional diagnostics. It does not rerun VLM inference or every Monte Carlo replicate. Local full verification passed in a separate input directory using the existing Windows Python 3.11.16 reproduction environment. Exact scope and receipts are in `REPRODUCIBILITY.md` and `provenance/verification.json`.

Source images, model weights, API credentials, and author photographs are not included. Author-owned software uses MIT; external materials retain their original terms. This release does not establish statistical equivalence, general model superiority, uniformly valid procedure-average intervals, or publication acceptance.
