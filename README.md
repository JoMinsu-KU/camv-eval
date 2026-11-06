# CAMV-Eval

Numerical reproduction package for **Threshold Calibration and Bootstrap Inference for Multi-View Grasp Verification**, manuscript v14.3 (v14 additions plus the preserved v8/v12 numerical evidence), by Minsu Jo, Namhyun Yoo, Beomseok Kim, Hoansuk Choi, and Jinhong Yang.

This package evaluates how calibration choices and uncertainty targets affect comparisons of multi-view grasp verifiers. It provides the original analysis functions, saved numerical inputs, reference results, and reproducible verification commands. A GPU, model weights, source images, and API credentials are not needed for the numerical replay.

[Authors and contributions](docs/AUTHORS.md) · [한국어 안내](README.ko.md) · [Reproduction scope](REPRODUCIBILITY.md) · [Original v8 display tables](docs/ALL_TABLES.md) · [Data sources](docs/DATA_SOURCES.md)

## Manuscript versions

Versions v13–v13.4.5 retain the numerical evidence in the v8 and v12 releases. See the [version map](docs/MANUSCRIPT_VERSION_MAP.md) and [editorial history](docs/EDITORIAL_HISTORY.md). No new model inference or simulation release was required for those editorial revisions. Manuscript v14 adds the separate numerical experiment and audits described below; v14.1–v14.3 adjust manuscript layout and Figures 1–2 without changing its numerical results.

## V14 additions and replay

The [v14-repro-1 release](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v14-repro-1) supplies the empirical-group-population experiment and supporting empirical/statistical audit snapshots. Download the ZIP and checksum using [the v14 instructions](docs/REPRODUCIBILITY-v14.md). Small result CSVs are browsable in [results/v14](results/v14). Original v8 and v12 releases are preserved.

```text
gh release download v14-repro-1 --repo JoMinsu-KU/camv-eval --pattern CAMV-Eval_v14_Reproduction.zip --dir ../v14-assets
python -m pip install -r requirements-v14.txt
python reproduce_v14.py --asset ../v14-assets/CAMV-Eval_v14_Reproduction.zip --output ../v14-replay --fresh-first
```

This independently recalculates all 4,000 paired-scorer saved records, 80,000 interval endpoints and 80 summary rows, and regenerates six selected outer datasets. The number of independent outer datasets is 2,000. Audit snapshots A1–A7 have a distinct scope; these commands do not redo raw image or model-response audits. See the [target and replay limits](docs/REPRODUCIBILITY-v14.md).

## V12 additions

The [v12-repro-1 release](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v12-repro-1) supplies the new targeted simulations and stored-result diagnostics. Download the numerical ZIP and follow [the v12 replay instructions](docs/REPRODUCIBILITY-v12.md). New result CSVs are in [results/v12](results/v12); original v8 tables and reproduction commands below remain available.

## Original v8 quick reproduction

Use Python 3.11. Create an environment and install the small example's dependency:

```sh
python -m venv .venv
# Activate .venv using your operating system's normal command.
python -m pip install -r requirements-quick.txt
python reproduce.py --mode quick --output ../camv-quick
```

On Windows PowerShell, activation is `.\.venv\Scripts\Activate.ps1`; on Linux/macOS it is `source .venv/bin/activate`. An already configured Python 3.11 environment also works.

Quick mode independently reconstructs all eight Table 5 interactions and their conditional/refit limits from the original four-policy, three-seed bootstrap projections. It verifies 64 saved fields and compares the regenerated CSV and Markdown rows exactly. The input projections are included in the Git repository. Choose an output directory that does not exist and is outside the repository.

## Full numerical reproduction

1. Install the full pinned dependencies: `python -m pip install -r requirements.txt`.
2. Download the three ZIP assets named in [assets.json](assets.json) from the preserved [v8-repro-1 release](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v8-repro-1) into a directory outside the checkout.
3. Run:

```sh
python reproduce.py --mode all --assets-dir ../release-assets --output ../camv-full
```

The optional downloader retrieves and verifies the three assets from the public v8 release:

```sh
python fetch_assets.py --repository JoMinsu-KU/camv-eval --tag v8-repro-1 --output ../release-assets
```

The downloader verifies the exact sizes and SHA-256 hashes recorded in `assets.json`; the numerical replay itself performs no network access.

Full mode verifies and extracts the frozen assets, then runs the original empirical analyses, subsequent scorer/transfer analyses, simulation summaries and deterministic probes, the translation-equivariance audit, width diagnostics, and the v8 table checks. It stops on a failed stage. See `completion.json` and `logs/` in the output directory for the actual checks and execution scope.

## What is reproduced

| Stage | Executed computation |
|---|---|
| Original and early revision | All 16 original empirical cases with B=2,000 recalibration, four source-pair transfer analyses, stored-scorer diagnostics, original centering summaries, and earlier simulation summaries |
| Candidate scores and ties | All four paired scorer recalibrations at B=2,000; 8,000 saved simulation datasets summarized; one original outer dataset regenerated per condition |
| Weak discrimination and BCa | 8,000 saved outer datasets and 229,376 reference contributions summarized; eight B=999 outer records, 21 reference contributions, and one B=4,999 extension regenerated; empirical cohort/AUROC audits |
| v7/v8 checks | Translation equivariance, width ratios, all Table 5 conditional/refit intervals, and all 16 S43 midpoint-diagnostic rows |

This is a **numerical replay from saved scores and simulation arrays**. It does not rerun all image preprocessing, VLM inference, every Monte Carlo replicate, or all reference integrations. The code and historical provenance for the original computations remain available. [REPRODUCIBILITY.md](REPRODUCIBILITY.md) separates recalculation, saved-array aggregation, and bounded regeneration.

## Repository layout

```text
reproduce.py                 One entry point: quick or all
fetch_assets.py              Optional verified release-asset download
assets.json                 Release filenames, sizes, and SHA-256
code/                       Byte-preserved research source snapshots
examples/table5/            Small offline inputs and independent replay
results/tables/             All 51 displayed manuscript tables as CSV
results/table-index.json     Table captions and row counts
docs/ALL_TABLES.md           All tables and notes in one document
docs/                       Source, upload, and interpretation guidance
provenance/                 Source hashes and verification records
MANIFEST.json               Integrity manifest for the Git tree
```

The result tables are display exports, with the manuscript's rounding; copying them is not counted as numerical reproduction. Recalculated results go into the user-selected output directory. Code snapshots are provided for inspection; the runner executes identical source copies inside the frozen assets so that their original path adapters and manifests remain valid.

## Interpretation and validation

Conditional intervals describe policies fitted on the observed development cohorts; refit constructions include repeated calibration. Non-rejection of the original four FSR tests is not evidence of equivalence. The added simulation grid does not identify a uniformly near-nominal procedure-average interval construction. These scientific qualifications are retained in the tables and reproduction documentation.

The release is checked on Windows using the existing Python 3.11.16 reproduction environment and the pinned packages. Full and quick replay receipts are summarized in [provenance/verification.json](provenance/verification.json). Paths are relative, but Linux/macOS and a fresh dependency installation have not been verified locally; strict numerical and file-access checks may require a separately versioned platform adapter. No external-researcher validation is claimed.

## License and citation

Author-owned software is released under the [MIT License](LICENSE), as confirmed by the author on September 15, 2026. External datasets, metadata, model weights, and third-party notices retain their own terms; see [LICENSE_SCOPE.md](LICENSE_SCOPE.md). Source images, model weights, author photos, and private credentials are not included. Historical archive statements about a local review package are preserved as provenance; the current software licensing statement applies to author-owned code.

Use [CITATION.cff](CITATION.cff) to cite the software. The repository provides the numerical materials supporting the associated manuscript, **Threshold Calibration and Bootstrap Inference for Multi-View Grasp Verification**. The fixed numerical archives are separated into v8-repro-1, v12-repro-1 and v14-repro-1; the latter adds a separate empirical-group-population replay.

## Manuscript version mapping

The v8-repro-1 assets reproduce the original v8 numerical results. Manuscript versions v9 and v10 condense and format those results; v11 changes declarations. Manuscript v12 adds operating-point J, stored-result and seed diagnostics, and three targeted simulation conditions, while retaining the original numerical results and four-test family. See [the version map](docs/MANUSCRIPT_VERSION_MAP.md). The separate v12 numerical archive is attached to the v12-repro-1 release; the frozen v8 assets remain the source for original results.
