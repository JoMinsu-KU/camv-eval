# Manuscript and numerical evidence versions

| Manuscript | Numerical evidence |
|---|---|
| v8 | [v8-repro-1](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v8-repro-1): original results and previous numerical audits |
| v9–v10 | Condensation and two-column appendix formatting; original numerical results retained |
| v11 | Declaration wording; original numerical results retained |
| v12 | [v12-repro-1](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v12-repro-1): fixed-operating-point J, development/evaluation decomposition, seed-output audit, and three targeted simulation conditions |
| v13–v13.1 | The same [v8-repro-1](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v8-repro-1) base and [v12-repro-1](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v12-repro-1) additions. Interpretation, declarations, labels, and presentation were revised; Table 3B consolidates existing decomposition results. The N02/FSR variance ratio is displayed as 0.908 from 0.9084945668118725. No new simulations or model inference. |
| v13.2 | The same two numerical releases; first-use BCa definitions, a practical Discussion summary, a version-pinned Guardian bibliography link, and a shorter appendix evidence guide. Numerical results and reference numbering are retained. |
| v13.3–v13.4.4 | The same v8 and v12 numerical releases. Official IEEE Access template, four-author metadata, integrated main.tex, float placement and navigation, and final terminology and evidence-label edits. Scientific results, frozen artifacts, and reference order are retained. |
| v13.4.5 | The same v8 and v12 numerical releases. Adds Hoansuk Choi as the fourth of five manuscript authors, with confirmed affiliation, email, IEEE membership, and CRediT roles. Updates biographies and public author metadata; scientific results and reference order remain unchanged. |
| v14 | Retains v8/v12 evidence and adds [v14-repro-1](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v14-repro-1): fixed empirical group-population laws, reference targets, 4,000 paired-scorer records, frozen arrays/code and empirical/statistical audit snapshots. New manuscript title begins “Threshold Calibration”. |
| v14.1–v14.3 | Same v14 numerical evidence. Nineteen-page manuscript layout; monochrome editable Figure 1; Figure 2 legends moved below their respective panels. No additional experiment after v14. |

The numerical transport export omits four internal prose review-response reports while retaining scientific code, inputs, arrays and CSVs byte for byte. Public metadata/manifests are regenerated; the included public-export provenance explains the differences. [v14 replay instructions](REPRODUCIBILITY-v14.md) separate E1 replay from A1–A7 snapshots.

## Legacy table numbering

The original entries of Tables 1–8 and the four original FSR tests are retained. V12 adds J to Table 4, clarifies the composite transfer labels in Table 5, and adds Table 9. The original display-table exports remain in results/tables; the new unrounded diagnostic results are in results/v12. They are different artifact types, not conflicting replacements.

The v12 archive contains all 3,000 new outer datasets with 999 paired bootstrap draws each, 32,768 reference development datasets, frozen simulation source and profiles, and portable inputs for the saved-result diagnostics. The latter project the required fields of 16,000 older outer datasets while retaining original source hashes. The v8 assets remain unchanged. These software and data releases provide numerical evidence for the manuscript, Calibration and Bootstrap Inference for Multi-View Grasp Verification.

See [EDITORIAL_HISTORY.md](EDITORIAL_HISTORY.md) for the editorial changes kept separate from the scientific analysis chronology.
