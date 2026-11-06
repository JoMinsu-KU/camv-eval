# Reproduce the v14 numerical additions

Download `CAMV-Eval_v14_Reproduction.zip` from [v14-repro-1](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v14-repro-1). Its SHA-256 and size are pinned in [v14-assets.json](../v14-assets.json). The release also supplies `SHA256SUMS-v14.txt`. Existing v8/v12 releases are unchanged.

```text
gh release download v14-repro-1 --repo JoMinsu-KU/camv-eval --pattern CAMV-Eval_v14_Reproduction.zip --dir ../v14-assets
python -m pip install -r requirements-v14.txt
python reproduce_v14.py --asset ../v14-assets/CAMV-Eval_v14_Reproduction.zip --output ../v14-replay --fresh-first
```

The output must be a new path outside this checkout. The wrapper checks the exact asset hash before extracting. The extracted portable entry point then verifies every package file and all ten frozen protocol pins before calculating results. A failed check raises an error. Expected final status in `completion.json` and `replay-report.json` is `PASS`.

Tested locally with Python 3.11.16, NumPy 2.2.6 and SciPy 1.16.2 on Windows, using E: SATA HDD storage. Numerical replay is offline after dependencies and the asset have been downloaded; it needs no GPU, image files, model weights or API credentials. A new dependency installation and other operating systems are not claimed to have been tested.

## Recalculation and bounded regeneration

The four conditions EP-RL-bare, EP-RL-space, EP-RE-bare and EP-RE-space share their outer datasets across scoring variants. There are 2,000 independent outer datasets and 4,000 scorer-specific records, each with 999 bootstrap draws. For every record, the entry point recomputes the five interval constructions, 80,000 endpoints and 28,000 summary fields; it reaggregates 80 coverage/availability/width rows and eight independent reference summaries. `--fresh-first` additionally regenerates outer indices 0, 17 and 999 for each of the two source populations: six datasets and twelve paired-scorer records. Omitting that option checks saved records only. It does not rerun all model inference or every original Monte Carlo dataset.

Conditional percentile and sandwich intervals are assessed against fitted-policy truth; full-refit percentile/basic/BCa are assessed against procedure-average truth. Fixed empirical group-population laws and their target validity conditioning are specified in the frozen protocol. A numerical replay PASS is not a nominal-coverage guarantee for unknown real-world populations.

## Audit snapshots and public export

The A1–A7 CSVs are scientific audit-result snapshots, accompanied by retained validation receipts. This package does not include all 89,052 original raw model-response records, source images, original HDF5 recordings, independent human outcome annotations, or all older-law raw arrays. It does not claim to re-execute those audits in full. Older numerical evidence remains in the separate v8/v12 assets.

The public v14 ZIP is a versioned transport export of the submission numerical supplement. Scientific code, frozen inputs/protocols, saved arrays and CSVs retain their exact bytes. Four internal prose review-response reports are excluded; public documentation and transport manifests are updated. The included `PUBLIC-EXPORT-PROVENANCE.json` records this correspondence. Historical paths in frozen scientific files are provenance; `PORTABLE_MAP.json` maps them to packaged inputs. Use the public `replay.py` entry point rather than legacy production runners with original absolute-path pins.

Small browsable results in [results/v14](../results/v14) are byte-identical CSV copies, not independent new calculations. Source snapshots in `code/v14` are for inspection; replay executes the complete verified archive. Author-owned code uses MIT; external source terms remain in the asset notices and LICENSE_SCOPE.md.
