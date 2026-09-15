# All v8 manuscript tables

These are transcribed display tables, not recomputed outputs. See REPRODUCIBILITY.md for the numerical replay scopes.

## Table 1. Empirical cohorts, class-contributing groups, and failure prevalence. Success/failure group counts overlap when a group contains both outcomes.

| Cohort | Trials (success/failure) | Groups (all/success/failure) | Failure prevalence (%) |
| --- | --- | --- | --- |
| RLBenchFail development | 106 (44/62) | 40 / 31 / 22 | 58.491 |
| RLBenchFail evaluation | 415 (164/251) | 179 / 129 / 95 | 60.482 |
| UR5Fail transfer evaluation | 79 (35/44) | 51 / 29 / 31 | 55.696 |
| REASSEMBLE development | 1716 (1595/121) | 111 / 111 / 70 | 7.051 |
| REASSEMBLE evaluation | 577 (527/50) | 37 / 37 / 21 | 8.666 |

## Table 2. FSR interaction coverage (%). Each entry reports fitted-policy / procedure-average coverage. C: conditional percentile; R: refit percentile; B: refit basic; S: cluster sandwich-t.

| Condition | C | R | B | S |
|---|---:|---:|---:|---:|
| N01 | 93.0 / 51.5 | 99.9 / 100.0 | 99.4 / 88.5 | 94.5 / 52.3 |
| N02 | 94.6 / 52.1 | 100.0 / 100.0 | 99.8 / 90.5 | 95.3 / 52.2 |
| N03 | 95.6 / 53.3 | 100.0 / 100.0 | 100.0 / 91.2 | 95.8 / 53.7 |
| N04 | 94.7 / 48.0 | 100.0 / 100.0 | 99.6 / 90.1 | 95.0 / 48.8 |
| A01 | 93.6 / 47.4 | 100.0 / 100.0 | 99.8 / 87.5 | 94.3 / 48.4 |
| A02 | 94.6 / 50.7 | 100.0 / 100.0 | 99.9 / 90.2 | 95.5 / 52.3 |
| A03 | 95.9 / 48.0 | 100.0 / 99.7 | 100.0 / 89.4 | 96.0 / 49.2 |
| A04 | 95.2 / 51.6 | 100.0 / 99.6 | 99.9 / 90.7 | 95.6 / 52.6 |

Note: Condition key: N01/N02/N03 use development/evaluation groups 20/60, 40/120, and 100/240, respectively; N04 uses 40/120. All N conditions have zero Joint pair offsets; only N04 has common target shifts (failure, success) $(0.25,-0.35)$. A01/A02/A03 use 40/120 and A04 uses 100/240, all with offsets $(-0.75,0,0.75)$. Only A02 has an additional Joint-success target shift $-0.5$, and only A03 has common shifts $(0.25,-0.35)$; other target shifts are zero. Offsets are score units and target shifts are in units of $s=\sqrt{0.75}$.

## Table 3. Bootstrap-centering diagnostics from saved draws; 1,000 outer datasets per row. Complete results appear in Supplementary Appendix H.

| Case / outcome | Point bias / SD (pp) | Mean bootstrap bias (pp) | Mean d (pp) | Corr(T,d) | Percentile/basic center SD (pp) | Shared width (pp) | Procedure-average coverage percentile/basic (%) | Width / (3.92 SD(T)) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| N02 / FSR | +0.113 / 3.082 | -0.113 | -0.114 | -0.893 | 1.417 / 5.948 | 19.587 | 100.0 / 90.5 | 1.621 |
| N02 / Recall | +0.030 / 1.757 | -0.025 | -0.016 | -0.891 | 0.800 / 3.261 | 11.133 | 100.0 / 91.6 | 1.617 |
| A01 / FSR | +0.031 / 5.487 | +0.042 | +0.321 | -0.740 | 3.694 / 8.792 | 26.398 | 100.0 / 87.5 | 1.227 |
| A01 / Recall | +0.033 / 3.015 | -0.309 | -0.593 | -0.712 | 2.116 / 4.771 | 14.990 | 99.9 / 89.2 | 1.268 |
| S02 / FSR | -0.473 / 11.150 | +0.023 | +0.220 | -0.497 | 9.726 / 15.482 | 46.993 | 98.0 / 87.0 | 1.075 |
| S02 / Recall | -0.278 / 6.231 | +0.010 | +0.014 | -0.412 | 5.769 / 8.377 | 27.632 | 98.3 / 90.7 | 1.131 |
| S20 / FSR | +0.806 / 11.391 | +0.067 | +0.066 | -0.502 | 9.887 / 15.768 | 45.200 | 97.2 / 84.7 | 1.012 |
| S20 / Recall | +0.207 / 5.655 | +0.272 | +1.403 | -0.464 | 5.038 / 7.664 | 22.789 | 96.3 / 84.9 | 1.028 |

Note: Condition key: N02 and A01 use 40/120 development/evaluation groups and no target shift, with Joint pair offsets $(0,0,0)$ and $(-0.75,0,0.75)$, respectively. S02/S20 are simple Joint-minus-Late contrasts for one two-camera pair, also with 40/120 groups and no common target shift: S02 has no method shift; S20 shifts the source Joint failure mean by $-0.124485$ score units and target-only Joint success scores by $+0.5\sqrt{0.75}$. The width ratio uses unrounded mean refit width and the outer-estimate sample SD; it is a descriptive Gaussian benchmark.

## Table 4. SmolVLM operating rates, FSR% / success recall%, with the deterministic accept-all reference. Bare is the original scoring rule; space is a post hoc paired sensitivity analysis with separate development calibration.

| Application / scorer | Joint pooled | Joint pair | Late pooled | Late pair |
| --- | --- | --- | --- | --- |
| **Deterministic reference** | | | | |
| Accept all (every application) | 100.000 / 100.000 | 100.000 / 100.000 | 100.000 / 100.000 | 100.000 / 100.000 |
| **Original bare-AB scoring** | | | | |
| RLBench / bare | 89.841 / 87.805 | 84.794 / 83.130 | 89.110 / 89.736 | 85.392 / 86.890 |
| UR5 transfer / bare | 94.697 / 86.667 | 81.818 / 66.667 | 94.697 / 86.667 | 82.576 / 70.476 |
| REASSEMBLE local / bare | 87.333 / 88.678 | 86.667 / 88.931 | 87.333 / 89.500 | 84.667 / 90.006 |
| RLBench-to-REASSEMBLE / bare | 78.000 / 84.124 | 53.333 / 63.567 | 84.000 / 86.907 | 67.333 / 72.802 |
| **Post hoc space-AB sensitivity** | | | | |
| RLBench / space | 92.696 / 92.276 | 82.470 / 84.553 | 84.329 / 85.671 | 80.744 / 84.350 |
| UR5 transfer / space | 90.152 / 83.810 | 34.091 / 20.952 | 43.939 / 27.619 | 12.121 / 11.429 |
| REASSEMBLE local / space | 84.667 / 91.524 | 89.333 / 93.548 | 86.667 / 90.006 | 87.333 / 91.841 |
| RLBench-to-REASSEMBLE / space | 92.667 / 95.699 | 44.000 / 49.273 | 62.667 / 70.588 | 28.000 / 38.836 |

## Table 5. Prospective interactions with refit and conditional intervals. Effects and nominal pointwise 95% limits are in percentage points. The fourth row is a prespecified exploratory transfer analysis.

| Evaluation | FSR estimate [refit CI] | FSR conditional CI | Recall estimate [refit CI] | Recall conditional CI | Approximate p | Holm4 p |
|---|---:|---:|---:|---:|---:|---:|
| RLBench confirmation | -1.328 [-7.946, +5.827] | [-2.759, +0.071] | -1.829 [-8.187, +6.713] | [-3.526, -0.127] | 0.712144 | 1.000 |
| UR5 source transfer | -0.758 [-20.000, +11.907] | [-7.093, +6.307] | -3.810 [-24.144, +16.092] | [-10.256, +3.922] | 0.923538 | 1.000 |
| REASSEMBLE local | +2.000 [-1.678, +11.310] | [-1.149, +6.481] | -0.253 [-1.790, +3.506] | [-2.022, +1.663] | 0.562219 | 1.000 |
| RL-to-REASSEMBLE transfer | -8.000 [-21.932, +14.394] | [-14.200, -0.813] | -6.452 [-18.969, +10.581] | [-8.921, -4.235] | 0.347326 | 1.000 |

Note: Refit intervals repeat development calibration and evaluation resampling; conditional intervals hold the observed development fits fixed and resample evaluation groups. Both use the original paired 2,000 draws and average seeds 17/29/43 before constructing the interaction. The p-values belong only to the original approximate centered refit FSR tests, with Holm adjustment across four comparisons. Conditional limits are descriptive, unadjusted pointwise summaries for the fitted-policy target; their exclusion of zero does not change the original testing family.

## Table 6. Complete-cohort descriptive AUROC, mean within camera pair and then across three seeds. Each cell gives bare / space. These estimates use the original success-positive direction and do not constitute new confirmatory tests.

| Cohort | Joint bare / space | Late bare / space |
| --- | --- | --- |
| RLBenchFail development | 0.5100 / 0.5427 | 0.5481 / 0.5897 |
| RLBenchFail evaluation | 0.4915 / 0.5099 | 0.4936 / 0.5280 |
| UR5Fail transfer evaluation | 0.3843 / 0.3859 | 0.3877 / 0.4053 |
| REASSEMBLE development | 0.6098 / 0.6253 | 0.5812 / 0.6000 |
| REASSEMBLE evaluation | 0.5566 / 0.5643 | 0.5644 / 0.5790 |

## Table 7. New sensitivity experiment: procedure-average FSR inference. C/R/B/A denote conditional percentile / refit percentile / refit basic / refit BCa; targets and widths are in pp. Centered rejection is distinct from interval zero exclusion. H050/H065 identify continuous marginal AUROC 0.50/0.65; C is continuous, Q125/Q500 have steps 0.125/0.5, and S denotes separation 1.5 controls.

| Condition | Target | C/R/B/A coverage (%) | R/A width | BCa available | Refit centered rejection (%) | R/A width ratio |
| --- | --- | --- | --- | --- | --- | ---: |
| H050_C | -0.317 | 58.5 / 100.0 / 89.9 / 89.6 | 14.30 / 14.14 | 1000/1000 | 0.3 | 1.245 / 1.231 |
| H050_Q125 | -0.110 | 56.8 / 100.0 / 86.6 / 86.5 | 13.97 / 13.70 | 1000/1000 | 0.2 | 1.214 / 1.190 |
| H050_Q500 | +0.415 | 38.7 / 100.0 / 79.7 / 78.8 | 16.46 / 15.68 | 1000/1000 | 0.0 | 1.170 / 1.115 |
| H065_C | -3.182 | 52.0 / 99.8 / 89.4 / 89.8 | 21.85 / 21.51 | 1000/1000 | 2.8 | 1.216 / 1.198 |
| H065_Q125 | -2.680 | 49.1 / 99.8 / 85.6 / 86.3 | 21.95 / 21.39 | 1000/1000 | 1.5 | 1.199 / 1.168 |
| H065_Q500 | -1.073 | 30.0 / 100.0 / 73.4 / 74.5 | 28.02 / 25.15 | 1000/1000 | 0.0 | 1.039 / 0.933 |
| S_N_C | +0.000 | 48.7 / 100.0 / 90.5 / 87.6 | 18.98 / 19.16 | 1000/1000 | 0.0 | 1.577 / 1.592 |
| S_H_C | -12.535 | 51.1 / 100.0 / 88.2 / 89.3 | 26.00 / 26.08 | 1000/1000 | 44.4 | 1.244 / 1.248 |

Note: The R/A width ratios divide each mean refit-percentile/BCa width by $3.92\,\mathrm{SD}(T)$ using unrounded outer-estimate SDs. Refit basic has the same width ratio as refit percentile. These are dimensionless Gaussian width benchmarks; all underlying SDs and both outcomes are in Supplementary Table S42. S_N_C and S_H_C correspond to “Strong, null” and “Strong, heterogeneous” in Figure 4; this mapping also applies to Table 8.

## Table 8. New sensitivity experiment: procedure-average recall inference, with the same conventions as Table 7. Coverage is reported among available intervals; all planned intervals are available.

| Condition | Target | C/R/B/A coverage (%) | R/A width | BCa available | Refit centered rejection (%) |
|---|---|---|---|---|---|
| H050_C | -0.317 | 63.0 / 99.8 / 87.8 / 88.0 | 14.95 / 14.86 | 1000/1000 | 0.6 |
| H050_Q125 | -0.110 | 61.4 / 100.0 / 85.8 / 84.1 | 14.61 / 14.35 | 1000/1000 | 0.3 |
| H050_Q500 | +0.415 | 46.1 / 100.0 / 78.8 / 77.3 | 16.89 / 16.15 | 1000/1000 | 0.1 |
| H065_C | -0.317 | 63.0 / 99.8 / 87.8 / 88.0 | 14.95 / 14.86 | 1000/1000 | 0.6 |
| H065_Q125 | -0.115 | 61.6 / 100.0 / 86.2 / 85.5 | 14.59 / 14.37 | 1000/1000 | 0.5 |
| H065_Q500 | +0.463 | 43.2 / 100.0 / 75.8 / 75.4 | 16.90 / 16.05 | 1000/1000 | 0.1 |
| S_N_C | +0.000 | 70.7 / 100.0 / 92.2 / 89.0 | 10.92 / 11.05 | 1000/1000 | 0.0 |
| S_H_C | -0.317 | 63.0 / 99.8 / 87.8 / 88.0 | 14.95 / 14.86 | 1000/1000 | 0.6 |

Note: H050_C, H065_C, and S_H_C share random numbers and differ only in continuous class separation. Adding a constant to every success score shifts its calibrated threshold by the same amount, leaving success acceptance unchanged. Their identical recall summaries follow from this translation equivariance; FSR and the quantized-score conditions need not coincide. Supplementary Appendix Q gives the derivation and stored-array checks.

## Table S1. Research questions, evidence, and scope of inference.

| Question | Evidence | Result addressed | Scope of inference |
|---|---|---|---|
| RQ1: Which estimand does an interval cover, and how do center location, dependence, and calibration sample size affect coverage? | Overlapping-pair simulations with known population values, center diagnostics, dependence/development controls, quantization and unequal groups | Estimand mismatch; reflected centers and their spread; conditions of persistence | Finite-sample behavior under specified continuous and quantized distributions |
| RQ2: How do fixed operating policies and source-pair composition affect transfer performance? | Held-out empirical outcomes and original interaction family; post hoc matched-pool sensitivity | FSR–recall tradeoffs; source-pair composition sensitivity | Original inference family with a separate descriptive sensitivity analysis |
| RQ3: Does a change in candidate tokens preserve ranking and the positive-class calibration tail? | Balanced development analysis plus full recalibration from stored outputs on original evaluation splits | Calibration-tail changes and paired sensitivity of operating points and interactions | Post hoc sensitivity analysis using the original evaluation splits |

## Table S2. Prespecified interaction conditions. Pair offsets are in score units; target shifts are in pair-standard-deviation units.

| Condition | Development/evaluation groups | Joint pair offsets | Common target shift (failure, success) | Joint target shift for successes |
|---|---:|---|---|---:|
| N01 | 20 / 60 | (0, 0, 0) | (0, 0) | 0.0 |
| N02 | 40 / 120 | (0, 0, 0) | (0, 0) | 0.0 |
| N03 | 100 / 240 | (0, 0, 0) | (0, 0) | 0.0 |
| N04 | 40 / 120 | (0, 0, 0) | (0.25, -0.35) | 0.0 |
| A01 | 40 / 120 | (-0.75, 0, 0.75) | (0, 0) | 0.0 |
| A02 | 40 / 120 | (-0.75, 0, 0.75) | (0, 0) | -0.5 |
| A03 | 40 / 120 | (-0.75, 0, 0.75) | (0.25, -0.35) | 0.0 |
| A04 | 100 / 240 | (-0.75, 0, 0.75) | (0, 0) | 0.0 |

## Table S3. Recall interaction coverage (%), using the same fitted-policy / procedure-average convention.

| Condition | C | R | B | S |
|---|---:|---:|---:|---:|
| N01 | 93.8 / 73.0 | 100.0 / 100.0 | 98.9 / 91.4 | 95.7 / 74.8 |
| N02 | 92.9 / 71.6 | 99.9 / 100.0 | 99.4 / 91.6 | 93.9 / 72.4 |
| N03 | 94.2 / 72.3 | 100.0 / 100.0 | 99.1 / 92.6 | 94.9 / 72.6 |
| N04 | 93.8 / 63.8 | 99.8 / 100.0 | 99.3 / 89.7 | 95.0 / 64.8 |
| A01 | 94.8 / 66.9 | 100.0 / 99.9 | 99.5 / 89.2 | 94.9 / 68.4 |
| A02 | 94.0 / 59.9 | 100.0 / 99.9 | 99.6 / 89.4 | 95.0 / 61.2 |
| A03 | 94.3 / 61.7 | 99.9 / 99.8 | 99.5 / 90.9 | 94.6 / 62.3 |
| A04 | 95.1 / 68.7 | 100.0 / 99.7 | 99.1 / 91.1 | 95.3 / 70.8 |

## Table S4. Procedure-average targets and centered-test rejection rates. Targets are in percentage points; rejection rates are percentages. Conditional tests are evaluated against the procedure-average target, although they are constructed for the fitted-policy target.

| Condition | FSR target | Recall target | FSR C / refit | Recall C / refit |
|---|---:|---:|---:|---:|
| N01 | 0.0000 | 0.0000 | 47.9 / 0.0 | 24.9 / 0.0 |
| N02 | 0.0000 | 0.0000 | 47.8 / 0.0 | 27.4 / 0.0 |
| N03 | 0.0000 | 0.0000 | 46.4 / 0.0 | 26.6 / 0.0 |
| N04 | 0.0000 | 0.0000 | 51.0 / 0.0 | 35.1 / 0.0 |
| A01 | -12.5270 | -0.3253 | 95.7 / 41.5 | 31.5 / 0.2 |
| A02 | -12.5106 | -2.8883 | 95.3 / 41.7 | 49.3 / 2.0 |
| A03 | -11.1032 | -1.8749 | 91.8 / 29.4 | 42.7 / 1.1 |
| A04 | -12.6175 | -0.1123 | 99.7 / 86.9 | 29.6 / 0.6 |

## Table S5. Procedure-average coverage and refit rejection rates (%) in the controlled simulation. G denotes the number of development groups and L denotes lambda; evaluation uses 120 groups.

| Condition | FSR C/R/B coverage (%) | Recall C/R/B coverage (%) | Refit FSR rejection (%) | Refit recall rejection (%) |
|---|---:|---:|---:|---:|
| N_G40_L000 | 50.6 / 100.0 / 91.0 | 70.3 / 100.0 / 91.0 | 0.0 | 0.0 |
| N_G40_L050 | 52.5 / 100.0 / 92.6 | 70.2 / 100.0 / 91.3 | 0.0 | 0.0 |
| N_G40_L090 | 53.5 / 100.0 / 90.5 | 71.4 / 100.0 / 91.3 | 0.0 | 0.0 |
| N_G100_L000 | 63.1 / 100.0 / 90.4 | 82.6 / 100.0 / 91.6 | 0.0 | 0.0 |
| N_G100_L050 | 65.7 / 100.0 / 90.5 | 82.4 / 100.0 / 90.5 | 0.0 | 0.0 |
| N_G100_L090 | 67.2 / 100.0 / 91.2 | 83.0 / 100.0 / 91.8 | 0.0 | 0.0 |
| A_G40_L000 | 50.7 / 100.0 / 88.3 | 66.7 / 99.9 / 90.8 | 43.9 | 0.5 |
| A_G40_L050 | 50.3 / 100.0 / 89.4 | 67.8 / 100.0 / 91.3 | 45.0 | 0.2 |
| A_G40_L090 | 51.0 / 99.8 / 87.7 | 67.1 / 99.7 / 88.6 | 48.6 | 0.4 |
| A_G100_L000 | 63.8 / 99.4 / 90.7 | 79.6 / 99.7 / 90.1 | 83.3 | 0.4 |
| A_G100_L050 | 65.1 / 99.6 / 89.7 | 80.1 / 100.0 / 91.6 | 82.1 | 0.3 |
| A_G100_L090 | 68.1 / 99.8 / 91.0 | 80.8 / 99.8 / 90.3 | 83.0 | 0.4 |

## Table S6. Main operating points, FSR% / success recall%. J: Joint; L: Late; GBest: Global BestSingle; PBest: PairBestSingle.

| Model and evaluation | J pooled | J pair | L pooled | L pair | GBest | PBest |
|---|---:|---:|---:|---:|---:|---:|
| SmolVLM / RLBench | 89.841 / 87.805 | 84.794 / 83.130 | 89.110 / 89.736 | 85.392 / 86.890 | 80.478 / 83.537 | 83.201 / 84.756 |
| SmolVLM / UR5 | 94.697 / 86.667 | 81.818 / 66.667 | 94.697 / 86.667 | 82.576 / 70.476 | 72.727 / 48.571 | 79.545 / 62.857 |
| SmolVLM / REASSEMBLE local | 87.333 / 88.678 | 86.667 / 88.931 | 87.333 / 89.500 | 84.667 / 90.006 | 90.000 / 88.235 | 87.333 / 89.247 |
| SmolVLM / RL-to-REASSEMBLE | 78.000 / 84.124 | 53.333 / 63.567 | 84.000 / 86.907 | 67.333 / 72.802 | 60.000 / 67.173 | 61.333 / 67.995 |
| InternVL3.5 / RLBench | 78.884 / 91.463 | 78.021 / 92.276 | 75.166 / 91.057 | 71.580 / 88.618 | 76.892 / 96.341 | 75.232 / 88.008 |
| InternVL3.5 / UR5 | 84.848 / 94.286 | 84.848 / 94.286 | 73.485 / 90.476 | 63.636 / 88.571 | 70.455 / 91.429 | 71.212 / 92.381 |
| Qwen3-VL / RLBench | 72.178 / 89.228 | 72.377 / 88.618 | 75.033 / 90.955 | 73.440 / 90.244 | 54.183 / 90.854 | 68.659 / 88.923 |
| Qwen3-VL / UR5 | 42.424 / 81.905 | 38.636 / 83.810 | 30.303 / 87.619 | 32.576 / 84.762 | 11.364 / 71.429 | 27.273 / 80.000 |

## Table S7. Interactions after restricting source pairs to the target configuration. This post hoc sensitivity analysis is descriptive; effects are in percentage points.

| Transfer case | Outcome | Interaction, six source pairs (pp) | Interaction, three source pairs (pp) | Conditional 95% CI, three pairs | Refit percentile 95% CI, three pairs |
|---|---|---|---|---|---|
| SmolVLM / UR5 | FSR | -0.758 | -11.364 | [-17.886, -4.444] | [-18.605, 15.558] |
| SmolVLM / UR5 | Recall | -3.810 | -14.286 | [-22.857, -6.896] | [-23.810, 21.906] |
| SmolVLM / RL→RE | FSR | -8.000 | -14.000 | [-21.369, -6.989] | [-25.758, 16.667] |
| SmolVLM / RL→RE | Recall | -6.452 | -13.093 | [-15.970, -10.499] | [-21.941, 12.849] |
| InternVL3.5-4B / UR5 | FSR | 9.848 | 4.545 | [-0.926, 9.809] | [-11.111, 12.500] |
| InternVL3.5-4B / UR5 | Recall | 1.905 | 0.952 | [0.000, 3.419] | [-4.167, 5.714] |
| Qwen3-VL-4B / UR5 | FSR | -6.061 | -7.576 | [-15.219, -0.758] | [-20.292, 8.168] |
| Qwen3-VL-4B / UR5 | Recall | 4.762 | 1.905 | [-2.222, 7.144] | [-5.715, 10.753] |

## Table S8. Bare/space AB score association and recalibration on the same observations. Tail overlap is the inclusive intersection/union; FSR and recall are percentages.

| Dataset | Context | Spearman, all | Spearman, success | Kendall tau-b, all | Positive lower-tail intersection/union | Decision disagreement | FSR bare/space (%) | Recall bare/space (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| RLBenchFail | Joint | 0.865 | 0.752 | 0.712 | 2/7 | 6/48 | 79.17/91.67 | 91.67/95.83 |
| RLBenchFail | Single0 | 0.857 | 0.778 | 0.700 | 2/4 | 3/48 | 87.50/87.50 | 91.67/95.83 |
| RLBenchFail | Single1 | 0.850 | 0.748 | 0.694 | 2/9 | 5/48 | 79.17/91.67 | 91.67/91.67 |
| RLBenchFail | Derived Late | 0.833 | 0.714 | 0.645 | 2/4 | 6/48 | 91.67/83.33 | 91.67/91.67 |
| REASSEMBLE | Joint | 0.887 | 0.837 | 0.743 | 2/6 | 7/48 | 83.33/62.50 | 91.67/91.67 |
| REASSEMBLE | Single0 | 0.809 | 0.879 | 0.682 | 3/3 | 3/48 | 95.83/100.00 | 91.67/100.00 |
| REASSEMBLE | Single1 | 0.856 | 0.793 | 0.708 | 0/6 | 7/48 | 70.83/91.67 | 91.67/100.00 |
| REASSEMBLE | Derived Late | 0.890 | 0.870 | 0.734 | 2/5 | 6/48 | 79.17/79.17 | 91.67/91.67 |

## Table S9. Agreement with generated responses. Each row contains 48 contexts. Agreement compares the scorer decision at 0.5 with the class returned by the secondary parser.

| Dataset / context | Valid, strict parser | Generated A / B | Response accuracy (%) | Bare-AB agreement | Space-AB agreement |
|---|---:|---:|---:|---:|---:|
| RLBench / Joint | 2 | 46 / 2 | 54.2 | 19/48 | 48/48 |
| RLBench / Single0 | 5 | 46 / 2 | 54.2 | 15/48 | 48/48 |
| RLBench / Single1 | 2 | 44 / 4 | 50.0 | 13/48 | 48/48 |
| REASSEMBLE / Joint | 0 | 48 / 0 | 50.0 | 21/48 | 48/48 |
| REASSEMBLE / Single0 | 0 | 44 / 4 | 45.8 | 14/48 | 48/48 |
| REASSEMBLE / Single1 | 0 | 40 / 8 | 54.2 | 16/48 | 48/48 |

## Table S10. Development-sample AUROC [95% group-bootstrap CI].

| Dataset / context | Bare AB | Space AB | Bare words | Space words |
|---|---:|---:|---:|---:|
| RLBench / Joint | .500 [.316, .659] | .453 [.264, .626] | .327 [.193, .476] | .320 [.193, .462] |
| RLBench / Late | .459 [.291, .632] | .417 [.233, .589] | .322 [.187, .476] | .345 [.213, .493] |
| REASSEMBLE / Joint | .583 [.418, .736] | .657 [.501, .797] | .494 [.317, .663] | .558 [.380, .723] |
| REASSEMBLE / Late | .540 [.379, .705] | .615 [.455, .766] | .457 [.288, .637] | .510 [.332, .687] |

## Table S11. Space-AB operating points on the original evaluation splits, FSR% / success recall%. Each scorer uses its own development calibration. Original bare-AB outcomes remain in Supplementary Table S6.

| Application | Joint pooled | Joint pair | Late pooled | Late pair |
|---|---|---|---|---|
| RLBench | 92.696 / 92.276 | 82.470 / 84.553 | 84.329 / 85.671 | 80.744 / 84.350 |
| UR5 transfer | 90.152 / 83.810 | 34.091 / 20.952 | 43.939 / 27.619 | 12.121 / 11.429 |
| REASSEMBLE local | 84.667 / 91.524 | 89.333 / 93.548 | 86.667 / 90.006 | 87.333 / 91.841 |
| RLBench→REASSEMBLE | 92.667 / 95.699 | 44.000 / 49.273 | 62.667 / 70.588 | 28.000 / 38.836 |

## Table S12. FSR interactions and paired scorer differences, pp [nominal 95% refit percentile interval]. Development/evaluation group draws are shared across scorers and seeds. The UR5 space upper endpoint is zero to numerical precision.

| Application | Bare interaction | Space interaction | Paired space−bare change |
|---|---|---|---|
| RLBench | -1.328 [-7.946, 5.827] | -6.640 [-15.060, 4.989] | -5.312 [-16.059, 7.463] |
| UR5 transfer | -0.758 [-20.000, 11.907] | -24.242 [-49.339, 0.000] | -23.485 [-51.757, 3.616] |
| REASSEMBLE local | 2.000 [-1.678, 11.310] | 4.000 [-3.270, 10.606] | 2.000 [-8.642, 7.639] |
| RLBench→REASSEMBLE | -8.000 [-21.932, 14.394] | -14.000 [-40.301, 10.081] | -6.000 [-38.600, 16.098] |

## Table S13. FSR results under quantization and unequal group sizes. The target (reference MCSE) and interval width are in pp; coverage/rejection rates are percentages. N/A: null/alternative; C/Q: continuous/quantized; EQ/UQ: equal/unequal groups. Each condition has 1,000 available outer repetitions. Refit rejection estimates Type I error under N and two-sided power under A.

| Condition | Target (MCSE) | Conditional fitted-policy / procedure-average coverage | Refit percentile / basic procedure-average coverage | Refit width | Refit rejection |
|---|---|---|---|---|---|
| N_C_EQ | 0.0000 (0.0000) | 94.9 / 48.0 | 100.0 / 92.6 | 19.242 | 0.0 |
| N_C_UQ | 0.0000 (0.0000) | 94.0 / 50.7 | 100.0 / 90.3 | 19.639 | 0.0 |
| N_Q_EQ | 0.0000 (0.0000) | 95.6 / 35.1 | 100.0 / 80.1 | 37.248 | 0.0 |
| N_Q_UQ | 0.0000 (0.0000) | 95.8 / 34.0 | 100.0 / 77.7 | 37.302 | 0.0 |
| A_C_EQ | -12.5186 (0.0194) | 94.3 / 51.9 | 100.0 / 91.1 | 26.298 | 41.9 |
| A_C_UQ | -12.5261 (0.0198) | 94.0 / 46.0 | 100.0 / 87.2 | 26.591 | 42.9 |
| A_Q_EQ | -10.0423 (0.0387) | 94.2 / 26.3 | 100.0 / 75.0 | 41.431 | 4.1 |
| A_Q_UQ | -10.4051 (0.0388) | 94.1 / 28.0 | 100.0 / 73.1 | 41.871 | 4.0 |

## Table S14. Recall results under quantization and unequal group sizes. The target (reference MCSE) and interval width are in pp; coverage/rejection rates are percentages. N/A: null/alternative; C/Q: continuous/quantized; EQ/UQ: equal/unequal groups. Each condition has 1,000 available outer repetitions. Refit rejection estimates Type I error under N and two-sided power under A.

| Condition | Target (MCSE) | Conditional fitted-policy / procedure-average coverage | Refit percentile / basic procedure-average coverage | Refit width | Refit rejection |
|---|---|---|---|---|---|
| N_C_EQ | 0.0000 (0.0000) | 92.8 / 71.8 | 100.0 / 92.0 | 10.842 | 0.0 |
| N_C_UQ | 0.0000 (0.0000) | 93.2 / 69.7 | 100.0 / 91.2 | 11.457 | 0.0 |
| N_Q_EQ | 0.0000 (0.0000) | 95.1 / 38.9 | 100.0 / 81.8 | 14.823 | 0.0 |
| N_Q_UQ | 0.0000 (0.0000) | 94.1 / 37.8 | 100.0 / 80.8 | 15.530 | 0.0 |
| A_C_EQ | -0.3125 (0.0100) | 93.2 / 66.7 | 100.0 / 90.4 | 14.800 | 0.1 |
| A_C_UQ | -0.3892 (0.0105) | 93.1 / 65.3 | 100.0 / 88.6 | 15.684 | 0.2 |
| A_Q_EQ | 0.4125 (0.0137) | 93.9 / 48.4 | 100.0 / 80.7 | 16.678 | 0.0 |
| A_Q_UQ | 0.2546 (0.0142) | 93.6 / 45.1 | 100.0 / 78.6 | 17.572 | 0.0 |

## Table S15. S02 Joint-minus-Late FSR coverage for nominal 95% intervals. Widths are in percentage points.

| Interval | Fitted-policy coverage (%) | Procedure-average coverage (%) | Mean width (pp) |
|---|---:|---:|---:|
| Conditional percentile | 94.4 | 47.7 | 14.82 |
| Cluster sandwich-t | 95.3 | 47.4 | 15.10 |
| Refit percentile | 99.7 | 98.0 | 46.99 |
| Refit basic | 99.7 | 87.0 | 46.99 |

## Table S16. Timing of protocol specifications relative to the available results. Specifications were recorded internally without external preregistration.

| Analysis | Information available at specification | Design |
|---|---|---|
| Historical InternVL3.5/Qwen3-VL | Existing scores and outcomes | Retrospective |
| Original calibration-aware protocol | Historical findings; SmolVLM outputs unavailable | Prospective SmolVLM and REASSEMBLE evaluations |
| Supporting clustered-score contrast experiment | Original protocol specified | Simulation contrasts with known targets, including S02/S20 |
| Original overlapping-pair simulation and scorer audit | Original findings available; extensions specified before their outputs | Extensions specified before execution |
| September 14 sensitivity analysis | Manuscript and assessment of the original results available | Descriptive diagnostics and a separately specified twelve-condition simulation |
| September 15 stored-score and score-resolution analyses | Original outcomes and development scorer analysis available; alternative top-five probabilities stored | Post hoc recalibration on original evaluation splits; eight score-resolution/group-size conditions specified before their simulation outputs |
| September 15 cohort and weak-discrimination analyses | All preceding outcomes and the subsequent assessment available | Complete-cohort descriptive audit; eight conditions and BCa construction fixed before new simulation outcomes |
| Finite-bootstrap sensitivity | B=999 coverage and extreme-tail diagnostics available | Post hoc H065_Q125 comparison at B=4,999 on the same 1,000 outer datasets |

## Table S17. Bootstrap interval-center diagnostics for all reference conditions. Biases, SDs, and widths are in percentage points.

| Case / outcome | Point bias / SD (pp) | Mean bootstrap bias (pp) | Mean displacement d (pp) | Corr(T,d) | Percentile / basic center SD (pp) | Shared width (pp) | Procedure-average coverage, percentile / basic (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| N01 / FSR | -0.107 / 4.737 | +0.138 | +0.085 | -0.849 | 2.693 / 9.381 | 28.161 | 100.0 / 88.5 |
| N01 / Recall | -0.024 / 2.916 | +0.023 | +0.034 | -0.862 | 1.515 / 5.548 | 17.946 | 100.0 / 91.4 |
| N02 / FSR | +0.113 / 3.082 | -0.113 | -0.114 | -0.893 | 1.417 / 5.948 | 19.587 | 100.0 / 90.5 |
| N02 / Recall | +0.030 / 1.757 | -0.025 | -0.016 | -0.891 | 0.800 / 3.261 | 11.133 | 100.0 / 91.6 |
| N03 / FSR | -0.004 / 1.671 | +0.016 | +0.028 | -0.906 | 0.708 / 3.104 | 10.485 | 100.0 / 91.2 |
| N03 / Recall | -0.011 / 0.935 | +0.018 | +0.021 | -0.894 | 0.420 / 1.724 | 5.891 | 100.0 / 92.6 |
| N04 / FSR | -0.062 / 3.513 | +0.047 | +0.039 | -0.915 | 1.423 / 6.690 | 20.217 | 100.0 / 90.1 |
| N04 / Recall | -0.045 / 2.445 | +0.039 | +0.055 | -0.916 | 0.980 / 4.602 | 14.501 | 100.0 / 89.7 |
| A01 / FSR | +0.031 / 5.487 | +0.042 | +0.321 | -0.740 | 3.694 / 8.792 | 26.398 | 100.0 / 87.5 |
| A01 / Recall | +0.033 / 3.015 | -0.309 | -0.593 | -0.712 | 2.116 / 4.771 | 14.990 | 99.9 / 89.2 |
| A02 / FSR | +0.007 / 5.265 | +0.115 | +0.433 | -0.720 | 3.654 / 8.483 | 26.630 | 100.0 / 90.2 |
| A02 / Recall | +0.027 / 4.232 | -0.372 | -0.741 | -0.736 | 2.885 / 6.568 | 20.432 | 99.9 / 89.4 |
| A03 / FSR | -0.020 / 5.542 | -0.139 | +0.178 | -0.747 | 3.699 / 8.776 | 27.351 | 99.7 / 89.4 |
| A03 / Recall | -0.042 / 4.041 | -0.409 | -0.723 | -0.723 | 2.804 / 6.240 | 19.956 | 99.8 / 90.9 |
| A04 / FSR | +0.040 / 3.397 | -0.020 | +0.122 | -0.673 | 2.550 / 4.845 | 15.797 | 99.6 / 90.7 |
| A04 / Recall | -0.033 / 1.849 | -0.142 | -0.275 | -0.650 | 1.418 / 2.626 | 8.815 | 99.7 / 91.1 |
| S02 / FSR | -0.473 / 11.150 | +0.023 | +0.220 | -0.497 | 9.726 / 15.482 | 46.993 | 98.0 / 87.0 |
| S02 / Recall | -0.278 / 6.231 | +0.010 | +0.014 | -0.412 | 5.769 / 8.377 | 27.632 | 98.3 / 90.7 |
| S20 / FSR | +0.806 / 11.391 | +0.067 | +0.066 | -0.502 | 9.887 / 15.768 | 45.200 | 97.2 / 84.7 |
| S20 / Recall | +0.207 / 5.655 | +0.272 | +1.403 | -0.464 | 5.038 / 7.664 | 22.789 | 96.3 / 84.9 |

## Table S18. Transfer operating points using six or three source camera pairs.

| Transfer case | Fusion | Pool6 FSR / recall (%) | Pool3 FSR / recall (%) | Pair-specific FSR / recall (%) |
|---|---|---|---|---|
| SmolVLM / UR5 | Joint | 94.697 / 86.667 | 94.697 / 86.667 | 81.818 / 66.667 |
| SmolVLM / UR5 | Late | 94.697 / 86.667 | 84.091 / 76.190 | 82.576 / 70.476 |
| SmolVLM / RL→RE | Joint | 78.000 / 84.124 | 78.000 / 84.124 | 53.333 / 63.567 |
| SmolVLM / RL→RE | Late | 84.000 / 86.907 | 78.000 / 80.266 | 67.333 / 72.802 |
| InternVL3.5-4B / UR5 | Joint | 84.848 / 94.286 | 83.333 / 94.286 | 84.848 / 94.286 |
| InternVL3.5-4B / UR5 | Late | 73.485 / 90.476 | 66.667 / 89.524 | 63.636 / 88.571 |
| Qwen3-VL-4B / UR5 | Joint | 42.424 / 81.905 | 37.121 / 80.000 | 38.636 / 83.810 |
| Qwen3-VL-4B / UR5 | Late | 30.303 / 87.619 | 23.485 / 82.857 | 32.576 / 84.762 |

## Table S19. Sensitivity to weighting and exact-pixel exclusion. Effects are in percentage points.

| Case | Outcome | Sample interaction (pp) | Group interaction (pp) | Task-macro interaction (pp) | Max absolute change after exact-pixel exclusion (pp) |
|---|---|---|---|---|---|
| SmolVLM / RE local | FSR | 2.000 | 2.535 | 1.317 | 0.000 |
| SmolVLM / RE local | Recall | -0.253 | 0.089 | -0.405 | 0.000 |
| SmolVLM / RL→RE | FSR | -8.000 | -7.289 | -6.550 | 0.000 |
| SmolVLM / RL→RE | Recall | -6.452 | -6.554 | -6.555 | 0.000 |
| InternVL3.5-4B / RL | FSR | 2.722 | 1.082 | 1.344 | 0.014 |
| InternVL3.5-4B / RL | Recall | 3.252 | 2.017 | 3.648 | 0.000 |
| InternVL3.5-4B / UR5 | FSR | 9.848 | 9.072 | 9.070 | 0.000 |
| InternVL3.5-4B / UR5 | Recall | 1.905 | 2.807 | 2.137 | 0.000 |
| Qwen3-VL-4B / RL | FSR | 1.793 | 1.812 | 1.346 | 0.023 |
| Qwen3-VL-4B / RL | Recall | 0.102 | -0.153 | -0.941 | 0.000 |
| Qwen3-VL-4B / UR5 | FSR | -6.061 | -7.747 | -5.244 | 0.000 |
| Qwen3-VL-4B / UR5 | Recall | 4.762 | 0.936 | 7.906 | 0.000 |
| SmolVLM / RL | FSR | -1.328 | -1.065 | -1.166 | 0.200 |
| SmolVLM / RL | Recall | -1.829 | -1.610 | -1.201 | 0.000 |
| SmolVLM / UR5 | FSR | -0.758 | 0.102 | -0.057 | 0.000 |
| SmolVLM / UR5 | Recall | -3.810 | -3.392 | -1.923 | 0.000 |

## Table S20. Decision disagreement after camera-order reversal, with ranges across camera-pair/seed combinations.

| Case | Pooled disagreement % (pair/seed range) | Pair-specific disagreement % (pair/seed range) |
|---|---|---|
| SmolVLM / RE local | 11.438 (0.000–18.891) | 14.962 (12.825–19.237) |
| SmolVLM / RL→RE | 16.984 (1.733–27.383) | 31.947 (21.837–46.620) |
| InternVL3.5-4B / RL | 11.647 (8.675–14.458) | 13.936 (4.578–22.651) |
| InternVL3.5-4B / UR5 | 8.861 (6.329–11.392) | 6.751 (2.532–8.861) |
| Qwen3-VL-4B / RL | 15.542 (13.012–17.831) | 14.739 (10.361–20.723) |
| Qwen3-VL-4B / UR5 | 16.878 (8.861–22.785) | 14.346 (8.861–18.987) |
| SmolVLM / RL | 15.542 (9.157–18.554) | 22.450 (15.663–47.711) |
| SmolVLM / UR5 | 14.346 (11.392–17.722) | 26.582 (11.392–50.633) |

## Table S21. FSR / recall (%) under camera-order reversal and recalibration with pooled thresholds.

| Case | Forward Joint | Reverse / forward threshold | Reverse / refitted threshold | Symmetric Joint |
|---|---|---|---|---|
| SmolVLM / RE local | 87.333 / 88.678 | 100.000 / 100.000 | 84.000 / 89.374 | 84.667 / 88.552 |
| SmolVLM / RL→RE | 78.000 / 84.124 | 98.667 / 99.114 | 91.333 / 94.371 | 77.333 / 82.796 |
| InternVL3.5-4B / RL | 78.884 / 91.463 | 77.490 / 91.362 | 74.768 / 88.923 | 73.174 / 90.142 |
| InternVL3.5-4B / UR5 | 84.848 / 94.286 | 81.818 / 95.238 | 79.545 / 94.286 | 80.303 / 94.286 |
| Qwen3-VL-4B / RL | 72.178 / 89.228 | 70.784 / 87.805 | 83.533 / 92.378 | 77.224 / 90.752 |
| Qwen3-VL-4B / UR5 | 42.424 / 81.905 | 41.667 / 88.571 | 61.364 / 94.286 | 44.697 / 86.667 |
| SmolVLM / RL | 89.841 / 87.805 | 94.090 / 94.004 | 89.243 / 87.805 | 85.525 / 84.959 |
| SmolVLM / UR5 | 94.697 / 86.667 | 89.394 / 93.333 | 78.788 / 80.952 | 81.818 / 76.190 |

## Table S22. Empirical score dependence, duplicate excess, and group sizes.

| Model | Dataset | Split | Median within-label/pair Joint–Late Spearman correlation | Joint duplicate excess (%) | Late duplicate excess (%) | Group-size range |
|---|---|---|---|---|---|---|
| internvl35_4b | rlbenchfail | confirmation | 0.767 | 51.917 | 14.343 | 1–13 |
| internvl35_4b | rlbenchfail | dev | 0.782 | 26.540 | 4.545 | 1–13 |
| internvl35_4b | ur5fail | external | 0.856 | 15.097 | 2.273 | 1–6 |
| qwen3vl4b | rlbenchfail | confirmation | 0.831 | 62.255 | 3.386 | 1–13 |
| qwen3vl4b | rlbenchfail | dev | 0.791 | 28.482 | 0.000 | 1–13 |
| qwen3vl4b | ur5fail | external | 0.842 | 18.799 | 2.273 | 1–6 |
| smolvlm_instruct | reassemble | confirmation | 0.789 | 71.505 | 64.987 | 1–28 |
| smolvlm_instruct | reassemble | dev | 0.774 | 86.215 | 80.115 | 1–26 |
| smolvlm_instruct | rlbenchfail | confirmation | 0.607 | 77.247 | 67.987 | 1–13 |
| smolvlm_instruct | rlbenchfail | dev | 0.550 | 46.591 | 34.787 | 1–13 |
| smolvlm_instruct | ur5fail | external | 0.631 | 43.182 | 31.916 | 1–6 |

## Table S23. Score medians [Q1, Q3] and numbers of exactly tied within-class pairs.

| Dataset | Context | Scorer | Failure score | Success score | Failure tied pairs | Success tied pairs |
|---|---|---|---:|---:|---:|---:|
| rlbenchfail | joint | ab_bare | 0.473 [0.402, 0.549] | 0.457 [0.415, 0.492] | 4/276 | 9/276 |
| rlbenchfail | joint | ab_space | 0.665 [0.562, 0.731] | 0.622 [0.577, 0.679] | 14/276 | 25/276 |
| rlbenchfail | joint | word_bare | 0.761 [0.662, 0.849] | 0.699 [0.570, 0.755] | 2/276 | 3/276 |
| rlbenchfail | joint | word_space | 0.917 [0.881, 0.954] | 0.884 [0.818, 0.925] | 1/276 | 2/276 |
| rlbenchfail | late | ab_bare | 0.438 [0.404, 0.511] | 0.449 [0.391, 0.489] | 4/276 | 3/276 |
| rlbenchfail | late | ab_space | 0.651 [0.589, 0.696] | 0.622 [0.593, 0.655] | 1/276 | 2/276 |
| rlbenchfail | late | word_bare | 0.725 [0.691, 0.772] | 0.676 [0.600, 0.775] | 2/276 | 2/276 |
| rlbenchfail | late | word_space | 0.902 [0.880, 0.920] | 0.874 [0.826, 0.918] | 1/276 | 0/276 |
| reassemble | joint | ab_bare | 0.449 [0.392, 0.525] | 0.480 [0.413, 0.531] | 3/276 | 5/276 |
| reassemble | joint | ab_space | 0.622 [0.562, 0.679] | 0.679 [0.622, 0.712] | 18/276 | 18/276 |
| reassemble | joint | word_bare | 0.863 [0.816, 0.896] | 0.854 [0.827, 0.907] | 4/276 | 4/276 |
| reassemble | joint | word_space | 0.969 [0.951, 0.977] | 0.972 [0.941, 0.981] | 5/276 | 1/276 |
| reassemble | late | ab_bare | 0.423 [0.375, 0.472] | 0.432 [0.399, 0.469] | 5/276 | 3/276 |
| reassemble | late | ab_space | 0.562 [0.547, 0.641] | 0.600 [0.562, 0.651] | 17/276 | 6/276 |
| reassemble | late | word_bare | 0.893 [0.862, 0.914] | 0.870 [0.843, 0.916] | 1/276 | 3/276 |
| reassemble | late | word_space | 0.973 [0.964, 0.978] | 0.971 [0.961, 0.983] | 1/276 | 1/276 |

## Table S24. FSR interval location and scale under the alternative in the dependence simulation. SDs and widths are in percentage points.

| Condition | FSR point SD (pp) | Percentile midpoint SD (pp) | Basic midpoint SD (pp) | Bootstrap mean − point (pp) | Percentile mean width (pp) | Oracle conditional mean width (pp) |
|---|---:|---:|---:|---:|---:|---:|
| A_G40_L000 | 5.365 | 3.797 | 8.389 | 0.074 | 25.940 | 6.457 |
| A_G40_L050 | 5.176 | 3.660 | 8.247 | 0.127 | 25.989 | 6.472 |
| A_G40_L090 | 5.170 | 3.640 | 8.172 | 0.059 | 24.655 | 6.461 |
| A_G100_L000 | 3.648 | 2.852 | 5.140 | 0.116 | 16.815 | 6.521 |
| A_G100_L050 | 3.651 | 2.782 | 5.228 | 0.015 | 16.853 | 6.506 |
| A_G100_L090 | 3.407 | 2.611 | 4.908 | 0.050 | 16.773 | 6.513 |

## Table S25. Coverage for the alternative FSR interaction at fixed population thresholds, with 95% Wilson Monte Carlo intervals.

| Condition | Covered / 1,000 | Coverage (%) [95% Wilson] | Mean width (pp) | Point SD (pp) |
|---|---:|---:|---:|---:|
| A_G40_L000 | 940 | 94.0 [92.35, 95.31] | 6.457 | 1.695 |
| A_G40_L050 | 950 | 95.0 [93.47, 96.19] | 6.472 | 1.622 |
| A_G40_L090 | 949 | 94.9 [93.36, 96.10] | 6.461 | 1.584 |
| A_G100_L000 | 947 | 94.7 [93.13, 95.93] | 6.521 | 1.648 |
| A_G100_L050 | 953 | 95.3 [93.81, 96.45] | 6.506 | 1.647 |
| A_G100_L090 | 950 | 95.0 [93.47, 96.19] | 6.513 | 1.610 |

## Table S26. Recall interactions and paired scorer differences, pp [pointwise nominal 95% refit percentile interval]. These post hoc intervals are unadjusted for multiplicity.

| Application | Bare interaction | Space interaction | Paired space−bare change |
|---|---|---|---|
| RLBench | -1.829 [-8.187, 6.713] | -6.402 [-14.609, 5.032] | -4.573 [-16.667, 7.799] |
| UR5 transfer | -3.810 [-24.144, 16.092] | -46.667 [-65.687, -12.191] | -42.857 [-69.702, -7.836] |
| REASSEMBLE local | -0.253 [-1.790, 3.506] | 0.190 [-2.244, 3.317] | 0.443 [-3.817, 2.652] |
| RLBench→REASSEMBLE | -6.452 [-18.969, 10.581] | -14.674 [-35.208, 8.790] | -8.223 [-32.305, 14.983] |

## Table S27. Coverage (%) in the score-resolution and group-size simulation, fitted-policy / procedure-average target. C: conditional percentile; R: refit percentile; B: refit basic; S: cluster sandwich-t. Each cell is based on 1,000 repetitions.

| Condition | Metric | C | R | B | S |
|---|---|---|---|---|---|
| N_C_EQ | FSR | 94.9 / 48.0 | 99.9 / 100.0 | 99.6 / 92.6 | 95.0 / 48.9 |
| N_C_EQ | Recall | 92.8 / 71.8 | 100.0 / 100.0 | 99.1 / 92.0 | 94.4 / 73.6 |
| N_C_UQ | FSR | 94.0 / 50.7 | 100.0 / 100.0 | 99.3 / 90.3 | 94.5 / 51.0 |
| N_C_UQ | Recall | 93.2 / 69.7 | 100.0 / 100.0 | 98.7 / 91.2 | 94.1 / 70.4 |
| N_Q_EQ | FSR | 95.6 / 35.1 | 98.5 / 100.0 | 97.8 / 80.1 | 95.6 / 35.1 |
| N_Q_EQ | Recall | 95.1 / 38.9 | 99.0 / 100.0 | 98.4 / 81.8 | 94.8 / 39.5 |
| N_Q_UQ | FSR | 95.8 / 34.0 | 97.8 / 100.0 | 97.7 / 77.7 | 96.2 / 34.1 |
| N_Q_UQ | Recall | 94.1 / 37.8 | 98.6 / 100.0 | 98.2 / 80.8 | 94.0 / 38.6 |
| A_C_EQ | FSR | 94.3 / 51.9 | 100.0 / 100.0 | 100.0 / 91.1 | 95.0 / 52.5 |
| A_C_EQ | Recall | 93.2 / 66.7 | 100.0 / 100.0 | 99.3 / 90.4 | 94.4 / 69.2 |
| A_C_UQ | FSR | 94.0 / 46.0 | 100.0 / 100.0 | 99.9 / 87.2 | 94.3 / 46.8 |
| A_C_UQ | Recall | 93.1 / 65.3 | 100.0 / 100.0 | 99.0 / 88.6 | 94.0 / 66.7 |
| A_Q_EQ | FSR | 94.2 / 26.3 | 98.6 / 100.0 | 99.0 / 75.0 | 94.9 / 27.0 |
| A_Q_EQ | Recall | 93.9 / 48.4 | 99.0 / 100.0 | 98.9 / 80.7 | 94.4 / 50.4 |
| A_Q_UQ | FSR | 94.1 / 28.0 | 98.5 / 100.0 | 97.7 / 73.1 | 94.4 / 27.9 |
| A_Q_UQ | Recall | 93.6 / 45.1 | 98.7 / 100.0 | 98.3 / 78.6 | 94.3 / 47.7 |

## Table S28. Rejection frequencies (%) [95% Wilson interval] in the score-resolution and group-size simulation. Conditional inference is evaluated against the procedure-average null. N: empirical Type I error; A: two-sided power. Wilson intervals quantify uncertainty, including when no rejection is observed.

| Condition | Metric | Conditional, cross-target | Full refit |
|---|---|---|---|
| N_C_EQ | FSR | 51.1 [48.00, 54.19] | 0.0 [0.00, 0.38] |
| N_C_EQ | Recall | 26.5 [23.86, 29.32] | 0.0 [0.00, 0.38] |
| N_C_UQ | FSR | 48.9 [45.81, 52.00] | 0.0 [0.00, 0.38] |
| N_C_UQ | Recall | 28.8 [26.08, 31.68] | 0.0 [0.00, 0.38] |
| N_Q_EQ | FSR | 64.9 [61.89, 67.80] | 0.0 [0.00, 0.38] |
| N_Q_EQ | Recall | 59.9 [56.83, 62.89] | 0.0 [0.00, 0.38] |
| N_Q_UQ | FSR | 65.9 [62.91, 68.77] | 0.0 [0.00, 0.38] |
| N_Q_UQ | Recall | 60.5 [57.44, 63.48] | 0.0 [0.00, 0.38] |
| A_C_EQ | FSR | 96.2 [94.83, 97.22] | 41.9 [38.88, 44.98] |
| A_C_EQ | Recall | 29.9 [27.14, 32.81] | 0.1 [0.02, 0.56] |
| A_C_UQ | FSR | 94.6 [93.02, 95.84] | 42.9 [39.87, 45.99] |
| A_C_UQ | Recall | 32.4 [29.57, 35.36] | 0.2 [0.05, 0.73] |
| A_Q_EQ | FSR | 83.8 [81.39, 85.95] | 4.1 [3.04, 5.51] |
| A_Q_EQ | Recall | 50.4 [47.31, 53.49] | 0.0 [0.00, 0.38] |
| A_Q_UQ | FSR | 84.5 [82.13, 86.61] | 4.0 [2.95, 5.40] |
| A_Q_UQ | Recall | 52.7 [49.60, 55.78] | 0.0 [0.00, 0.38] |

## Table S29. Interval-center diagnostics in the score-resolution and group-size simulation. SDs and biases are in pp. Correlation relates point-estimation error to percentile-midpoint displacement. Percentile and basic intervals have equal widths and centers reflected about the point estimate in every repetition.

| Condition | Metric | Point SD | Percentile / basic midpoint SD | Correlation | Point bias | Mean bootstrap bias |
|---|---|---|---|---|---|---|
| N_C_EQ | FSR | 3.014 | 1.418 / 5.756 | -0.886 | -0.103 | 0.067 |
| N_C_EQ | Recall | 1.718 | 0.805 / 3.223 | -0.885 | -0.028 | 0.025 |
| N_C_UQ | FSR | 3.103 | 1.481 / 6.081 | -0.888 | -0.060 | 0.070 |
| N_C_UQ | Recall | 1.824 | 0.841 / 3.472 | -0.890 | -0.020 | 0.038 |
| N_Q_EQ | FSR | 8.316 | 1.927 / 16.338 | -0.973 | -0.181 | 0.113 |
| N_Q_EQ | Recall | 3.092 | 0.865 / 6.069 | -0.960 | -0.093 | 0.065 |
| N_Q_UQ | FSR | 8.773 | 1.971 / 17.164 | -0.974 | -0.283 | 0.250 |
| N_Q_UQ | Recall | 3.297 | 0.961 / 6.495 | -0.957 | -0.015 | 0.030 |
| A_C_EQ | FSR | 4.938 | 3.742 / 7.807 | -0.657 | 0.034 | 0.164 |
| A_C_EQ | Recall | 3.014 | 2.146 / 4.699 | -0.703 | -0.002 | -0.254 |
| A_C_UQ | FSR | 5.580 | 3.842 / 8.990 | -0.725 | -0.020 | 0.230 |
| A_C_UQ | Recall | 3.154 | 2.238 / 4.995 | -0.705 | -0.010 | -0.304 |
| A_Q_EQ | FSR | 9.731 | 4.212 / 17.618 | -0.903 | -0.454 | -0.270 |
| A_Q_EQ | Recall | 3.721 | 1.956 / 6.577 | -0.851 | -0.133 | -0.286 |
| A_Q_UQ | FSR | 10.358 | 4.451 / 18.858 | -0.904 | -0.111 | -0.259 |
| A_Q_UQ | Recall | 4.030 | 1.990 / 7.392 | -0.870 | -0.031 | -0.304 |

## Table S30. Mean positive-class probability mass at the threshold and recall (%), Joint pooled / Late pooled. Empirical mass counts observations tied at the selected threshold; population mass is zero for continuous score distributions. These measures differ from duplicate excess.

| Condition | Empirical mass at threshold | Population mass at threshold | Development recall | Population recall |
|---|---|---|---|---|
| N_C_EQ | 0.70 / 0.70 | 0.00 / 0.00 | 90.31 / 90.31 | 89.29 / 89.20 |
| N_C_UQ | 0.73 / 0.73 | 0.00 / 0.00 | 90.33 / 90.33 | 89.04 / 89.16 |
| N_Q_EQ | 11.10 / 11.24 | 10.41 / 10.51 | 94.27 / 94.28 | 93.40 / 93.31 |
| N_Q_UQ | 11.39 / 11.45 | 10.51 / 10.63 | 94.41 / 94.15 | 93.23 / 93.13 |
| A_C_EQ | 0.70 / 0.70 | 0.00 / 0.00 | 90.31 / 90.31 | 89.50 / 89.20 |
| A_C_UQ | 0.73 / 0.73 | 0.00 / 0.00 | 90.33 / 90.33 | 89.42 / 89.16 |
| A_Q_EQ | 9.24 / 11.24 | 8.82 / 10.51 | 93.51 / 94.28 | 92.96 / 93.31 |
| A_Q_UQ | 9.38 / 11.45 | 8.84 / 10.63 | 93.58 / 94.15 | 92.89 / 93.13 |

## Table S31. Bare/space decision disagreement on the original evaluation splits after separate development calibration (% of sample-pair decisions), averaged over three seeds. All point fits are available. Seeds and camera pairs are averaged within each estimate; resampling operates on dependence groups.

| Application | Policy | All | Failures | Successes |
|---|---|---|---|---|
| RLBench | joint pooled | 8.88 | 9.23 | 8.33 |
| RLBench | joint pair | 11.61 | 12.02 | 10.98 |
| RLBench | late pooled | 9.72 | 10.36 | 8.74 |
| RLBench | late pair | 8.23 | 8.10 | 8.43 |
| UR5 transfer | joint pooled | 5.49 | 4.55 | 6.67 |
| UR5 transfer | joint pair | 47.68 | 47.73 | 47.62 |
| UR5 transfer | late pooled | 54.43 | 50.76 | 59.05 |
| UR5 transfer | late pair | 65.40 | 70.45 | 59.05 |
| REASSEMBLE local | joint pooled | 7.34 | 9.33 | 7.15 |
| REASSEMBLE local | joint pair | 8.03 | 12.00 | 7.65 |
| REASSEMBLE local | late pooled | 6.53 | 7.33 | 6.45 |
| REASSEMBLE local | late pair | 6.99 | 9.33 | 6.77 |
| RLBench→REASSEMBLE | joint pooled | 11.84 | 14.67 | 11.57 |
| RLBench→REASSEMBLE | joint pair | 23.45 | 20.00 | 23.78 |
| RLBench→REASSEMBLE | late pooled | 19.76 | 22.67 | 19.48 |
| RLBench→REASSEMBLE | late pair | 35.12 | 39.33 | 34.72 |

## Table S32. Request accounting. Availability refers to a persisted usable output, not a count of every internal forward execution.

| Scope | Scheduled records | Available outputs |
| --- | --- | --- |
| Original-data main | 27,141 | 27,141 |
| REASSEMBLE main | 61,911 | 61,910 |
| Main total | 89,052 | 89,051 |
| Original-data subset replay | 452 | 452 |
| REASSEMBLE subset replay | 72 | 72 |
| Cost-accounting total | 89,576 | 89,575 |

## Table S33. Failure-group contribution and concentration. The concentration count is descriptive and is not a coverage guarantee.

| Cohort | Failure groups | Concentration count | Largest class weight (%) | No-failure bootstrap probability |
| --- | --- | --- | --- | --- |
| RLBenchFail development | 22 | 12.986 | 14.516 | 1.344e-14 |
| RLBenchFail evaluation | 95 | 51.346 | 4.781 | 1.532e-59 |
| UR5Fail transfer evaluation | 31 | 24.200 | 9.091 | 1.847e-21 |
| REASSEMBLE development | 70 | 52.477 | 3.306 | 9.731e-49 |
| REASSEMBLE evaluation | 21 | 14.881 | 14.000 | 3.380e-14 |

## Table S34. Complete-cohort AUROC by method and scorer. Pair AUROC averages within-pair values; pooled AUROC includes cross-pair comparisons.

| Cohort | Method / scorer | Pair AUROC | Pooled AUROC | Unavailable sample-pairs across seeds |
| --- | --- | --- | --- | --- |
| RLBenchFail development | joint / bare | 0.5100 | 0.5195 | 0 |
| RLBenchFail development | joint / space | 0.5427 | 0.5462 | 0 |
| RLBenchFail development | late / bare | 0.5481 | 0.5539 | 0 |
| RLBenchFail development | late / space | 0.5897 | 0.5940 | 0 |
| RLBenchFail evaluation | joint / bare | 0.4915 | 0.4938 | 0 |
| RLBenchFail evaluation | joint / space | 0.5099 | 0.5139 | 0 |
| RLBenchFail evaluation | late / bare | 0.4936 | 0.4961 | 0 |
| RLBenchFail evaluation | late / space | 0.5280 | 0.5294 | 0 |
| UR5Fail transfer evaluation | joint / bare | 0.3843 | 0.3898 | 0 |
| UR5Fail transfer evaluation | joint / space | 0.3859 | 0.3845 | 0 |
| UR5Fail transfer evaluation | late / bare | 0.3877 | 0.3877 | 0 |
| UR5Fail transfer evaluation | late / space | 0.4053 | 0.4063 | 0 |
| REASSEMBLE development | joint / bare | 0.6098 | 0.6066 | 0 |
| REASSEMBLE development | joint / space | 0.6253 | 0.6335 | 0 |
| REASSEMBLE development | late / bare | 0.5812 | 0.5802 | 2 |
| REASSEMBLE development | late / space | 0.6000 | 0.6014 | 2 |
| REASSEMBLE evaluation | joint / bare | 0.5566 | 0.5516 | 0 |
| REASSEMBLE evaluation | joint / space | 0.5643 | 0.5589 | 0 |
| REASSEMBLE evaluation | late / bare | 0.5644 | 0.5578 | 0 |
| REASSEMBLE evaluation | late / space | 0.5790 | 0.5741 | 0 |

## Table S35. Realized score summaries in the weak-discrimination and BCa experiment. Entries are averages across 1,000 outer datasets; duplicate and pair-tie measures are medians over label/pair cells within each dataset.

| Condition / split | Method | Population pair AUROC | Sample pair AUROC | Duplicate excess (%) | Pair ties (%) |
| --- | --- | --- | --- | --- | --- |
| H050_C / development | Joint | 0.5000 | 0.5010 | 0.00 | 0.00 |
| H050_C / development | Late | 0.5000 | 0.4991 | 0.00 | 0.00 |
| H050_C / evaluation | Joint | 0.5000 | 0.5003 | 0.00 | 0.00 |
| H050_C / evaluation | Late | 0.5000 | 0.5002 | 0.00 | 0.00 |
| H050_Q125 / development | Joint | 0.5000 | 0.5010 | 58.75 | 4.05 |
| H050_Q125 / development | Late | 0.5000 | 0.4992 | 58.71 | 4.06 |
| H050_Q125 / evaluation | Joint | 0.5000 | 0.5002 | 81.40 | 4.06 |
| H050_Q125 / evaluation | Late | 0.5000 | 0.5002 | 81.42 | 4.07 |
| H050_Q500 / development | Joint | 0.5000 | 0.5011 | 85.25 | 16.05 |
| H050_Q500 / development | Late | 0.5000 | 0.4991 | 85.22 | 16.12 |
| H050_Q500 / evaluation | Joint | 0.5000 | 0.5004 | 94.21 | 16.06 |
| H050_Q500 / evaluation | Late | 0.5000 | 0.5002 | 94.21 | 16.08 |
| H065_C / development | Joint | 0.6500 | 0.6517 | 0.00 | 0.00 |
| H065_C / development | Late | 0.6500 | 0.6504 | 0.00 | 0.00 |
| H065_C / evaluation | Joint | 0.6500 | 0.6505 | 0.00 | 0.00 |
| H065_C / evaluation | Late | 0.6500 | 0.6504 | 0.00 | 0.00 |
| H065_Q125 / development | Joint | 0.6498 | 0.6515 | 58.73 | 4.06 |
| H065_Q125 / development | Late | 0.6498 | 0.6502 | 58.67 | 4.06 |
| H065_Q125 / evaluation | Joint | 0.6498 | 0.6503 | 81.40 | 4.06 |
| H065_Q125 / evaluation | Late | 0.6498 | 0.6501 | 81.43 | 4.07 |
| H065_Q500 / development | Joint | 0.6461 | 0.6478 | 85.24 | 16.03 |
| H065_Q500 / development | Late | 0.6461 | 0.6465 | 85.21 | 16.12 |
| H065_Q500 / evaluation | Joint | 0.6461 | 0.6467 | 94.21 | 16.06 |
| H065_Q500 / evaluation | Late | 0.6461 | 0.6465 | 94.22 | 16.08 |
| S_N_C / development | Joint | 0.8897 | 0.8914 | 0.00 | 0.00 |
| S_N_C / development | Late | 0.8897 | 0.8910 | 0.00 | 0.00 |
| S_N_C / evaluation | Joint | 0.8897 | 0.8904 | 0.00 | 0.00 |
| S_N_C / evaluation | Late | 0.8897 | 0.8903 | 0.00 | 0.00 |
| S_H_C / development | Joint | 0.8897 | 0.8914 | 0.00 | 0.00 |
| S_H_C / development | Late | 0.8897 | 0.8910 | 0.00 | 0.00 |
| S_H_C / evaluation | Joint | 0.8897 | 0.8904 | 0.00 | 0.00 |
| S_H_C / evaluation | Late | 0.8897 | 0.8903 | 0.00 | 0.00 |

## Table S36. Independent procedure-average reference values for the review sensitivity. Values and MCSEs are in pp; the null control is analytic.

| Condition | Metric | Target | Reference MCSE | Available reference draws |
| --- | --- | --- | --- | --- |
| H050_C | FSR | -0.31664 | 0.01428 | 32768 |
| H050_C | recall | -0.31664 | 0.01428 | 32768 |
| H050_Q125 | FSR | -0.11047 | 0.01433 | 32768 |
| H050_Q125 | recall | -0.11047 | 0.01433 | 32768 |
| H050_Q500 | FSR | +0.41519 | 0.01937 | 32768 |
| H050_Q500 | recall | +0.41519 | 0.01937 | 32768 |
| H065_C | FSR | -3.18233 | 0.02373 | 32768 |
| H065_C | recall | -0.31664 | 0.01428 | 32768 |
| H065_Q125 | FSR | -2.68014 | 0.02449 | 32768 |
| H065_Q125 | recall | -0.11514 | 0.01434 | 32768 |
| H065_Q500 | FSR | -1.07350 | 0.03548 | 32768 |
| H065_Q500 | recall | +0.46345 | 0.01954 | 32768 |
| S_N_C | FSR | +0.00000 | 0.00000 | 0 |
| S_N_C | recall | +0.00000 | 0.00000 | 0 |
| S_H_C | FSR | -12.53510 | 0.02762 | 32768 |
| S_H_C | recall | -0.31664 | 0.01428 | 32768 |

## Table S37. BCa tail diagnostics. Extreme tails use adjusted probabilities at or beyond the empirical resolution bounds $1/(B+1)$ and $B/(B+1)$; all 1,000 intervals per row are available.

| Condition | Metric | Extreme-tail intervals | Mean acceleration | Min lower probability | Max upper probability |
| --- | --- | --- | --- | --- | --- |
| H050_C | FSR | 299 | +0.0066 | 2.07e-09 | 0.999999992 |
| H050_C | recall | 293 | +0.0074 | 2.27e-08 | 0.999999999 |
| H050_Q125 | FSR | 376 | +0.0047 | 3.1e-08 | 1.000000000 |
| H050_Q125 | recall | 356 | +0.0045 | 1.03e-08 | 1.000000000 |
| H050_Q500 | FSR | 531 | +0.0086 | 9.75e-15 | 1.000000000 |
| H050_Q500 | recall | 528 | +0.0096 | 2.78e-13 | 1.000000000 |
| H065_C | FSR | 288 | +0.0097 | 3.1e-08 | 0.999999962 |
| H065_C | recall | 293 | +0.0074 | 2.27e-08 | 0.999999999 |
| H065_Q125 | FSR | 352 | +0.0058 | 5.51e-09 | 1.000000000 |
| H065_Q125 | recall | 363 | +0.0045 | 1.07e-08 | 1.000000000 |
| H065_Q500 | FSR | 567 | +0.0079 | 4.35e-13 | 1.000000000 |
| H065_Q500 | recall | 540 | +0.0071 | 7.31e-13 | 1.000000000 |
| S_N_C | FSR | 441 | +0.0005 | 2.47e-15 | 0.999999999 |
| S_N_C | recall | 427 | +0.0017 | 1.04e-09 | 0.999999997 |
| S_H_C | FSR | 320 | +0.0057 | 1.46e-16 | 0.999999963 |
| S_H_C | recall | 293 | +0.0074 | 2.27e-08 | 0.999999999 |

## Table S38. Complete FSR coverage (%) [95% Wilson Monte Carlo interval] in the new experiment. C/R/B/S/A denote conditional percentile / refit percentile / refit basic / conditional sandwich-t / BCa.

| Condition | Target | C | R | B | S | A |
| --- | --- | --- | --- | --- | --- | --- |
| H050_C | fitted policy | 93.8 [92.1, 95.1] | 99.8 [99.3, 99.9] | 99.4 [98.7, 99.7] | 94.2 [92.6, 95.5] | 99.3 [98.6, 99.7] |
| H050_C | procedure average | 58.5 [55.4, 61.5] | 100.0 [99.6, 100.0] | 89.9 [87.9, 91.6] | 60.3 [57.2, 63.3] | 89.6 [87.6, 91.3] |
| H050_Q125 | fitted policy | 94.4 [92.8, 95.7] | 99.9 [99.4, 100.0] | 99.5 [98.8, 99.8] | 94.7 [93.1, 95.9] | 99.4 [98.7, 99.7] |
| H050_Q125 | procedure average | 56.8 [53.7, 59.8] | 100.0 [99.6, 100.0] | 86.6 [84.3, 88.6] | 57.9 [54.8, 60.9] | 86.5 [84.2, 88.5] |
| H050_Q500 | fitted policy | 92.4 [90.6, 93.9] | 98.7 [97.8, 99.2] | 98.3 [97.3, 98.9] | 93.0 [91.2, 94.4] | 98.4 [97.4, 99.0] |
| H050_Q500 | procedure average | 38.7 [35.7, 41.8] | 100.0 [99.6, 100.0] | 79.7 [77.1, 82.1] | 40.7 [37.7, 43.8] | 78.8 [76.2, 81.2] |
| H065_C | fitted policy | 95.7 [94.3, 96.8] | 100.0 [99.6, 100.0] | 99.8 [99.3, 99.9] | 95.8 [94.4, 96.9] | 99.9 [99.4, 100.0] |
| H065_C | procedure average | 52.0 [48.9, 55.1] | 99.8 [99.3, 99.9] | 89.4 [87.3, 91.2] | 53.4 [50.3, 56.5] | 89.8 [87.8, 91.5] |
| H065_Q125 | fitted policy | 95.2 [93.7, 96.4] | 100.0 [99.6, 100.0] | 99.7 [99.1, 99.9] | 95.9 [94.5, 97.0] | 99.9 [99.4, 100.0] |
| H065_Q125 | procedure average | 49.1 [46.0, 52.2] | 99.8 [99.3, 99.9] | 85.6 [83.3, 87.6] | 50.3 [47.2, 53.4] | 86.3 [84.0, 88.3] |
| H065_Q500 | fitted policy | 93.9 [92.2, 95.2] | 99.0 [98.2, 99.5] | 97.9 [96.8, 98.6] | 94.5 [92.9, 95.8] | 97.9 [96.8, 98.6] |
| H065_Q500 | procedure average | 30.0 [27.2, 32.9] | 100.0 [99.6, 100.0] | 73.4 [70.6, 76.0] | 30.7 [27.9, 33.6] | 74.5 [71.7, 77.1] |
| S_N_C | fitted policy | 93.5 [91.8, 94.9] | 99.8 [99.3, 99.9] | 99.9 [99.4, 100.0] | 93.8 [92.1, 95.1] | 99.8 [99.3, 99.9] |
| S_N_C | procedure average | 48.7 [45.6, 51.8] | 100.0 [99.6, 100.0] | 90.5 [88.5, 92.2] | 49.1 [46.0, 52.2] | 87.6 [85.4, 89.5] |
| S_H_C | fitted policy | 93.8 [92.1, 95.1] | 99.9 [99.4, 100.0] | 99.6 [99.0, 99.8] | 94.8 [93.2, 96.0] | 99.7 [99.1, 99.9] |
| S_H_C | procedure average | 51.1 [48.0, 54.2] | 100.0 [99.6, 100.0] | 88.2 [86.1, 90.1] | 51.1 [48.0, 54.2] | 89.3 [87.2, 91.1] |

## Table S39. Complete recall coverage (%) [95% Wilson Monte Carlo interval] in the new experiment. C/R/B/S/A denote conditional percentile / refit percentile / refit basic / conditional sandwich-t / BCa.

| Condition | Target | C | R | B | S | A |
| --- | --- | --- | --- | --- | --- | --- |
| H050_C | fitted policy | 93.2 [91.5, 94.6] | 99.9 [99.4, 100.0] | 99.2 [98.4, 99.6] | 94.2 [92.6, 95.5] | 98.9 [98.0, 99.4] |
| H050_C | procedure average | 63.0 [60.0, 65.9] | 99.8 [99.3, 99.9] | 87.8 [85.6, 89.7] | 65.2 [62.2, 68.1] | 88.0 [85.8, 89.9] |
| H050_Q125 | fitted policy | 93.1 [91.4, 94.5] | 100.0 [99.6, 100.0] | 98.5 [97.5, 99.1] | 93.5 [91.8, 94.9] | 98.5 [97.5, 99.1] |
| H050_Q125 | procedure average | 61.4 [58.3, 64.4] | 100.0 [99.6, 100.0] | 85.8 [83.5, 87.8] | 63.5 [60.5, 66.4] | 84.1 [81.7, 86.2] |
| H050_Q500 | fitted policy | 94.0 [92.4, 95.3] | 99.2 [98.4, 99.6] | 98.6 [97.7, 99.2] | 94.1 [92.5, 95.4] | 98.7 [97.8, 99.2] |
| H050_Q500 | procedure average | 46.1 [43.0, 49.2] | 100.0 [99.6, 100.0] | 78.8 [76.2, 81.2] | 48.7 [45.6, 51.8] | 77.3 [74.6, 79.8] |
| H065_C | fitted policy | 93.2 [91.5, 94.6] | 99.9 [99.4, 100.0] | 99.2 [98.4, 99.6] | 94.2 [92.6, 95.5] | 98.9 [98.0, 99.4] |
| H065_C | procedure average | 63.0 [60.0, 65.9] | 99.8 [99.3, 99.9] | 87.8 [85.6, 89.7] | 65.2 [62.2, 68.1] | 88.0 [85.8, 89.9] |
| H065_Q125 | fitted policy | 93.3 [91.6, 94.7] | 99.9 [99.4, 100.0] | 98.3 [97.3, 98.9] | 94.0 [92.4, 95.3] | 98.1 [97.1, 98.8] |
| H065_Q125 | procedure average | 61.6 [58.5, 64.6] | 100.0 [99.6, 100.0] | 86.2 [83.9, 88.2] | 63.7 [60.7, 66.6] | 85.5 [83.2, 87.5] |
| H065_Q500 | fitted policy | 94.5 [92.9, 95.8] | 99.0 [98.2, 99.5] | 97.6 [96.5, 98.4] | 94.6 [93.0, 95.8] | 98.1 [97.1, 98.8] |
| H065_Q500 | procedure average | 43.2 [40.2, 46.3] | 100.0 [99.6, 100.0] | 75.8 [73.0, 78.4] | 45.5 [42.4, 48.6] | 75.4 [72.6, 78.0] |
| S_N_C | fitted policy | 92.4 [90.6, 93.9] | 100.0 [99.6, 100.0] | 99.2 [98.4, 99.6] | 93.6 [91.9, 95.0] | 98.8 [97.9, 99.3] |
| S_N_C | procedure average | 70.7 [67.8, 73.4] | 100.0 [99.6, 100.0] | 92.2 [90.4, 93.7] | 71.3 [68.4, 74.0] | 89.0 [86.9, 90.8] |
| S_H_C | fitted policy | 93.2 [91.5, 94.6] | 99.9 [99.4, 100.0] | 99.2 [98.4, 99.6] | 94.2 [92.6, 95.5] | 98.9 [98.0, 99.4] |
| S_H_C | procedure average | 63.0 [60.0, 65.9] | 99.8 [99.3, 99.9] | 87.8 [85.6, 89.7] | 65.2 [62.2, 68.1] | 88.0 [85.8, 89.9] |

## Table S40. Empirical score repetition and within-class pair ties (%), medians over class/pair/seed cells for the original bare scorer.

| Cohort | Method | Cells | Duplicate excess | Observations in ties | Pair ties |
| --- | --- | --- | --- | --- | --- |
| RLBench development | Joint | 36 | 46.59 | 72.65 | 3.28 |
| RLBench development | Late | 36 | 34.79 | 60.23 | 1.61 |
| RLBench evaluation | Joint | 36 | 77.25 | 93.86 | 3.04 |
| RLBench evaluation | Late | 36 | 67.99 | 92.03 | 1.72 |
| UR5 evaluation | Joint | 18 | 43.18 | 64.77 | 3.40 |
| UR5 evaluation | Late | 18 | 31.92 | 58.70 | 2.10 |
| REASSEMBLE development | Joint | 18 | 86.22 | 97.66 | 1.97 |
| REASSEMBLE development | Late | 18 | 80.11 | 95.24 | 1.81 |
| REASSEMBLE evaluation | Joint | 18 | 71.50 | 91.58 | 2.27 |
| REASSEMBLE evaluation | Late | 18 | 64.99 | 85.72 | 1.70 |

## Table S41. Paired finite-bootstrap sensitivity in H065_Q125. Coverage addresses the procedure-average target; conditional constructions are cross-target comparisons. Changes and their paired MCSEs are in pp. Widths are in pp.

| Metric / interval | Coverage B999 / B4999 (%) | Change (MCSE) | Width B999 / B4999 |
| --- | --- | --- | --- |
| FSR / conditional percentile | 49.1 / 49.8 | +0.7 (0.33) | 6.08 / 6.10 |
| FSR / refit percentile | 99.8 / 99.8 | +0.0 (0.00) | 21.95 / 22.03 |
| FSR / refit basic | 85.6 / 85.6 | +0.0 (0.35) | 21.95 / 22.03 |
| FSR / conditional sandwich-t | 50.3 / 50.3 | +0.0 (0.00) | 6.19 / 6.19 |
| FSR / refit BCa | 86.3 / 85.9 | -0.4 (0.32) | 21.39 / 22.22 |
| recall / conditional percentile | 61.6 / 61.9 | +0.3 (0.39) | 5.58 / 5.59 |
| recall / refit percentile | 100.0 / 100.0 | +0.0 (0.00) | 14.59 / 14.66 |
| recall / refit basic | 86.2 / 86.7 | +0.5 (0.33) | 14.59 / 14.66 |
| recall / conditional sandwich-t | 63.7 / 63.7 | +0.0 (0.00) | 5.66 / 5.66 |
| recall / refit BCa | 85.5 / 85.7 | +0.2 (0.32) | 14.37 / 14.95 |

## Table S42. Width diagnostics from saved outer records. Point SD and widths are in pp; ratios divide mean width by $3.92s_T$. Original rows cover the reference interaction and simple-contrast experiments; additional rows cover the weak-discrimination/BCa experiment. Each row uses 1,000 available outer datasets. A dash means BCa was not evaluated in that original experiment.

| Experiment / condition | Metric | Point SD | Refit width | Refit ratio | BCa width | BCa ratio |
| --- | --- | --- | --- | --- | --- | --- |
| Original / N01 | FSR | 4.737 | 28.161 | 1.517 | — | — |
| Original / N01 | recall | 2.916 | 17.946 | 1.570 | — | — |
| Original / N02 | FSR | 3.082 | 19.587 | 1.621 | — | — |
| Original / N02 | recall | 1.757 | 11.133 | 1.617 | — | — |
| Original / N03 | FSR | 1.671 | 10.485 | 1.601 | — | — |
| Original / N03 | recall | 0.935 | 5.891 | 1.606 | — | — |
| Original / N04 | FSR | 3.513 | 20.217 | 1.468 | — | — |
| Original / N04 | recall | 2.445 | 14.501 | 1.513 | — | — |
| Original / A01 | FSR | 5.487 | 26.398 | 1.227 | — | — |
| Original / A01 | recall | 3.015 | 14.990 | 1.268 | — | — |
| Original / A02 | FSR | 5.265 | 26.630 | 1.290 | — | — |
| Original / A02 | recall | 4.232 | 20.432 | 1.232 | — | — |
| Original / A03 | FSR | 5.542 | 27.351 | 1.259 | — | — |
| Original / A03 | recall | 4.041 | 19.956 | 1.260 | — | — |
| Original / A04 | FSR | 3.397 | 15.797 | 1.186 | — | — |
| Original / A04 | recall | 1.849 | 8.815 | 1.216 | — | — |
| Original / S02 | FSR | 11.150 | 46.993 | 1.075 | — | — |
| Original / S02 | recall | 6.231 | 27.632 | 1.131 | — | — |
| Original / S20 | FSR | 11.391 | 45.200 | 1.012 | — | — |
| Original / S20 | recall | 5.655 | 22.789 | 1.028 | — | — |
| Additional / H050_C | FSR | 2.930 | 14.301 | 1.245 | 14.141 | 1.231 |
| Additional / H050_C | recall | 3.160 | 14.955 | 1.207 | 14.859 | 1.200 |
| Additional / H050_Q125 | FSR | 2.937 | 13.975 | 1.214 | 13.703 | 1.190 |
| Additional / H050_Q125 | recall | 3.132 | 14.608 | 1.190 | 14.345 | 1.168 |
| Additional / H050_Q500 | FSR | 3.588 | 16.461 | 1.170 | 15.684 | 1.115 |
| Additional / H050_Q500 | recall | 3.738 | 16.887 | 1.153 | 16.149 | 1.102 |
| Additional / H065_C | FSR | 4.581 | 21.845 | 1.216 | 21.511 | 1.198 |
| Additional / H065_C | recall | 3.160 | 14.955 | 1.207 | 14.859 | 1.200 |
| Additional / H065_Q125 | FSR | 4.671 | 21.947 | 1.199 | 21.385 | 1.168 |
| Additional / H065_Q125 | recall | 3.173 | 14.592 | 1.173 | 14.368 | 1.155 |
| Additional / H065_Q500 | FSR | 6.878 | 28.024 | 1.039 | 25.155 | 0.933 |
| Additional / H065_Q500 | recall | 4.014 | 16.898 | 1.074 | 16.047 | 1.020 |
| Additional / S_N_C | FSR | 3.071 | 18.985 | 1.577 | 19.160 | 1.592 |
| Additional / S_N_C | recall | 1.716 | 10.918 | 1.623 | 11.048 | 1.642 |
| Additional / S_H_C | FSR | 5.330 | 25.998 | 1.244 | 26.075 | 1.248 |
| Additional / S_H_C | recall | 3.160 | 14.955 | 1.207 | 14.859 | 1.200 |

## Table S43. Interval-center standard deviations in the added weak-discrimination and BCa simulation. All values are in pp and use 1,000 available outer datasets. Widths and coverage are reported separately in Tables S38–S39 and S42.

| Condition | Outcome | Point SD | Percentile midpoint SD | Basic midpoint SD | BCa midpoint SD |
|---|---|---:|---:|---:|---:|
| H050_C | FSR | 2.930 | 2.019 | 4.566 | 4.398 |
| H050_C | recall | 3.160 | 2.171 | 4.870 | 4.665 |
| H050_Q125 | FSR | 2.937 | 1.924 | 4.771 | 4.596 |
| H050_Q125 | recall | 3.132 | 2.052 | 5.016 | 4.803 |
| H050_Q500 | FSR | 3.588 | 1.837 | 6.570 | 5.983 |
| H050_Q500 | recall | 3.738 | 1.938 | 6.726 | 6.193 |
| H065_C | FSR | 4.581 | 3.006 | 7.103 | 6.342 |
| H065_C | recall | 3.160 | 2.171 | 4.870 | 4.665 |
| H065_Q125 | FSR | 4.671 | 2.907 | 7.507 | 6.729 |
| H065_Q125 | recall | 3.173 | 2.060 | 5.087 | 4.878 |
| H065_Q500 | FSR | 6.878 | 2.975 | 12.441 | 9.983 |
| H065_Q500 | recall | 4.014 | 1.941 | 7.197 | 6.477 |
| S_N_C | FSR | 3.071 | 1.410 | 5.921 | 6.620 |
| S_N_C | recall | 1.716 | 0.831 | 3.202 | 3.603 |
| S_H_C | FSR | 5.330 | 3.798 | 8.490 | 8.221 |
| S_H_C | recall | 3.160 | 2.171 | 4.870 | 4.665 |
