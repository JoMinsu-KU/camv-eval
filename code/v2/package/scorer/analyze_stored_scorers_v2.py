"""MC1 post-review descriptive analysis; no inference, resampling, or model calls.

Run with Start-GraspExperiment.ps1. Outputs must be fresh. All inputs are read-only.
"""
from pathlib import Path
from collections import Counter
from types import SimpleNamespace
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone

import numpy as np
import scipy
from scipy.stats import rankdata, spearmanr, kendalltau
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent
STUDY = ROOT.parents[2]
OLD = STUDY / "amendments/p0-e2e-20260914-v1"
AUDIT = OLD / "scorer"
DS = ["rlbenchfail", "reassemble"]
CT = ["joint", "single0", "single1", "late"]
SC = ["ab_bare", "ab_space", "word_bare", "word_space"]
NAMES = {"rlbenchfail": "RLBenchFail", "reassemble": "REASSEMBLE",
         "joint": "Joint", "single0": "Single0", "single1": "Single1", "late": "Derived Late"}
checks = Counter()


def check(value, name):
    assert bool(value), name
    checks[name] += 1


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def readj(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def jsonout(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def csvout(path, values):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def average_ranks_independent(x):
    # Pairwise definition of average rank, independent of scipy's sorting code.
    return 1 + (x[:, None] > x[None, :]).sum(axis=1) + .5 * ((x[:, None] == x[None, :]).sum(axis=1) - 1)


def paired_corr(x, z):
    rx, rz = rankdata(x), rankdata(z)
    check(np.array_equal(rx, average_ranks_independent(x)), "average_ranks_x")
    check(np.array_equal(rz, average_ranks_independent(z)), "average_ranks_z")
    rho = float(np.corrcoef(rx, rz)[0, 1])
    i, j = np.triu_indices(len(x), 1)
    sx, sz = np.sign(x[i] - x[j]), np.sign(z[i] - z[j])
    conc, disc = int(((sx * sz) > 0).sum()), int(((sx * sz) < 0).sum())
    den = math.sqrt(float((sx != 0).sum()) * float((sz != 0).sum()))
    tau = (conc - disc) / den if den else math.nan
    # Only statistics are used for numerical verification. No hypothesis test is reported.
    check(np.isclose(rho, spearmanr(x, z).statistic, atol=1e-14), "spearman_scipy_check")
    check(np.isclose(tau, kendalltau(x, z, variant="b").statistic, atol=1e-14), "kendall_scipy_check")
    return {"spearman_rho": rho, "kendall_tau_b": tau, "concordant_pairs": conc,
            "discordant_pairs": disc, "both_tied_pairs": int(((sx == 0) & (sz == 0)).sum()),
            "bare_only_tied_pairs": int(((sx == 0) & (sz != 0)).sum()),
            "space_only_tied_pairs": int(((sx != 0) & (sz == 0)).sum())}


def distribution(x):
    _, counts = np.unique(x, return_counts=True)
    tied = counts[counts > 1]
    q = np.quantile(x, [.1, .25, .5, .75, .9], method="linear")
    ties = int((counts * (counts - 1) // 2).sum())
    pair_n = len(x) * (len(x) - 1) // 2
    return {"n": len(x), "unique_values": len(counts), "minimum": float(x.min()),
            "q10_linear": float(q[0]), "q25_linear": float(q[1]), "median": float(q[2]),
            "q75_linear": float(q[3]), "q90_linear": float(q[4]), "maximum": float(x.max()),
            "mean": float(x.mean()), "sample_sd": float(x.std(ddof=1)),
            "tied_observations": int(tied.sum()), "tie_groups": len(tied),
            "max_multiplicity": int(counts.max()), "tied_pairs": ties,
            "all_pairs": pair_n, "pairwise_tie_fraction": ties / pair_n}


def prepare_inputs(output):
    protocol_path = ROOT / "protocol.json"
    protocol = readj(protocol_path)
    check(protocol["status"] == "FROZEN_BEFORE_NEW_OUTCOME_COMPUTATION", "protocol_frozen")
    source = Path(protocol["input"]["path"])
    check(sha(source) == protocol["input"]["sha256"], "protocol_input_hash")
    packet_path = STUDY / "staging/p0-e2e-20260914-v1/scorer-review/scorer-results-v2/review-packet.json"
    packet = readj(packet_path)
    check(packet["numerical_status"] == "PASS" and packet["failed"] == 0, "authoritative_v2_review_pass")
    analysis_completion_path = AUDIT / "analysis-v1/completion.json"
    analysis_completion = readj(analysis_completion_path)
    for p in [source, analysis_completion_path]:
        pins = {Path(k).resolve(): v for k, v in packet["source_pins"].items()}
        check(sha(p) == pins[p.resolve()], "authoritative_v2_source_pin")
    check(sha(source) == analysis_completion["output_sha256"][source.name], "analysis_output_pin")
    checker_path = OLD / "analyze_scorer_v2.py"
    audit_checker = module(checker_path, "frozen_scorer_v2")
    args = SimpleNamespace(output=str(output), raw=str(AUDIT / "run-v1/raw.jsonl"),
        labels=str(AUDIT / "labels/diagnostic-labels.jsonl"), requests=str(AUDIT / "inputs/requests.jsonl"),
        plan=str(AUDIT / "analysis-plan-v1.json"), run_completion=str(AUDIT / "run-v1/completion.json"),
        run_identity=str(AUDIT / "run-v1/run-identity.json"), protocol=str(AUDIT / "protocol-v1.json"),
        gate=str(AUDIT / "execution-gate-v1.json"))
    _, oldpins, raw, labels, requests, _ = audit_checker.preflight(args)
    check(True, "frozen_v2_preflight_pass")
    pins = {str(p): sha(p) for p in [protocol_path, source, packet_path, analysis_completion_path,
           checker_path, STUDY / "src/empirical_core_v2.py", Path(__file__)]}
    pins.update(oldpins)
    for p, value in analysis_completion["input_pins"].items():
        check(sha(p) == value, "analysis_input_pin")
    labmap = {r["sample_id"]: r for r in labels}
    rawmap = {}
    for row in raw:
        if row["branch"] == "ab_generation":
            continue
        req = row["request"]
        for name, z in row["output"]["scores"].items():
            rawmap[(req["sample_id"], req["context"], name)] = z
    with source.open(encoding="utf-8", newline="") as f:
        flat = list(csv.DictReader(f))
    check(len(flat) == 1536, "row_count_1536")
    mapping = {}
    for row in flat:
        key = (row["sample_id"], row["context"], row["scorer"])
        check(key not in mapping, "unique_trial_context_scorer")
        row["label"] = int(row["label"])
        for k in ["score", "logodds"]:
            row[k] = float(row[k])
            check(math.isfinite(row[k]), "finite_scores")
        row["candidate_mass"] = float(row["candidate_mass"]) if row["candidate_mass"] else None
        check(row["available"] == "True", "all_available")
        lab = labmap[row["sample_id"]]
        check(all(row[k] == lab[k] for k in ["dataset", "group_id"]) and row["label"] == int(lab["label"]), "labels_and_groups")
        if row["context"] == "late":
            a = rawmap[(key[0], "single0", key[2])]["logodds"]
            b = rawmap[(key[0], "single1", key[2])]["logodds"]
            expected = (a + b) / 2
            expected_score = float(np.exp(-np.logaddexp(0, -expected)))
            check(row["logodds"] == expected and row["score"] == expected_score, "late_exact_mean_logodds")
        else:
            z = rawmap[key]
            check(row["logodds"] == z["logodds"] and row["score"] == z["score"], "raw_score_exact")
            check(row["candidate_mass"] == z["vocabulary_mass"], "raw_mass_exact")
        mapping[key] = row
    check(set(row["dataset"] for row in flat) == set(DS), "dataset_completeness")
    check(set(row["context"] for row in flat) == set(CT), "context_completeness")
    check(set(row["scorer"] for row in flat) == set(SC), "scorer_completeness")
    return protocol, flat, mapping, pins


def analyze(output):
    check(not output.exists(), "fresh_output")
    protocol, flat, mapping, pins = prepare_inputs(output)
    core = module(STUDY / "src/empirical_core_v2.py", "frozen_empirical_v2")
    distributions, correlations, thresholds, knots, decisions, comparisons, ecdfs, cross_ties = ([] for _ in range(8))
    arrays, fits = {}, {}
    sample_sizes = {}
    for ds in DS:
        ids = sorted({r["sample_id"] for r in flat if r["dataset"] == ds})
        rows = [mapping[(sid, "joint", "ab_bare")] for sid in ids]
        y = np.array([r["label"] for r in rows])
        groups = [r["group_id"] for r in rows]
        check(len(ids) == 48 and int(y.sum()) == 24, "balanced_48_trial_sample")
        sample_sizes[ds] = {"trials": 48, "successes": 24, "failures": 24,
                            "groups": len(set(groups)), "maximum_group_size": max(Counter(groups).values())}
        for ct in CT:
            for sc in SC:
                rr = [mapping[(sid, ct, sc)] for sid in ids]
                score = np.array([r["score"] for r in rr])
                logodds = np.array([r["logodds"] for r in rr])
                arrays[(ds, ct, sc)] = (ids, y, score, logodds)
                meta = {"dataset": ds, "context": ct, "scorer": sc}
                for scale, values in [("score", score), ("logodds", logodds)]:
                    for label, mask in [("all", np.ones(48, bool)), ("failure", y == 0), ("success", y == 1)]:
                        distributions.append({**meta, "class": label, "scale": scale,
                            "groups": len({groups[i] for i in np.flatnonzero(mask)}), **distribution(values[mask])})
                        for knot in np.unique(values[mask]):
                            ecdfs.append({**meta, "class": label, "scale": scale, "value": float(knot),
                                "n": int(mask.sum()), "less_than_n": int((values[mask] < knot).sum()),
                                "less_equal_n": int((values[mask] <= knot).sum()),
                                "ecdf_strict": float((values[mask] < knot).mean()),
                                "ecdf_inclusive": float((values[mask] <= knot).mean())})
                    tie_count = int((values[y == 1, None] == values[None, y == 0]).sum())
                    cross_ties.append({**meta, "scale": scale, "success_failure_pairs": 576,
                                       "cross_class_tied_pairs": tie_count, "cross_class_tie_fraction": tie_count / 576})
                fitted = core.threshold(score[:, None], y, np.ones(48), np.ones((48, 1), bool))
                candidates = np.unique(score[y == 1])
                theta = max(float(t) for t in candidates if (score[y == 1] >= t).mean() + 1e-12 >= .9)
                check(theta == fitted["threshold"] and fitted["status"] == "OK", "frozen_threshold_exact")
                pred = score >= theta
                check(float(pred[y == 1].mean()) == fitted["achieved_recall"], "frozen_recall_exact")
                next_higher = candidates[candidates > theta]
                check(len(next_higher) == 0 or (score[y == 1] >= next_higher[0]).mean() + 1e-12 < .9, "highest_feasible_positive_knot")
                theta_z = float(np.min(logodds[score == theta]))
                check(np.array_equal(score >= theta, logodds >= theta_z), "score_logodds_threshold_decisions_equal")
                fits[(ds, ct, sc)] = (theta, theta_z, pred)
                thresholds.append({**meta, "diagnostic_scope": "same_subset_resubstitution", "n": 48,
                    "success_n": 24, "failure_n": 24, "groups": len(set(groups)),
                    "target_recall": .9, "score_threshold": theta, "logodds_threshold": theta_z,
                    "positive_below_n": int(((y == 1) & (score < theta)).sum()),
                    "positive_at_knot_n": int(((y == 1) & (score == theta)).sum()),
                    "positive_at_or_below_n": int(((y == 1) & (score <= theta)).sum()),
                    "failure_at_knot_n": int(((y == 0) & (score == theta)).sum()),
                    "accepted_success_n": int(pred[y == 1].sum()), "accepted_failure_n": int(pred[y == 0].sum()),
                    "resubstitution_recall": float(pred[y == 1].mean()), "resubstitution_fsr": float(pred[y == 0].mean())})
                for knot in candidates:
                    knots.append({**meta, "positive_score_knot": float(knot),
                        "positive_logodds_knot": float(np.min(logodds[(y == 1) & (score == knot)])),
                        "positive_n": 24, "positive_below_n": int((score[y == 1] < knot).sum()),
                        "positive_at_knot_n": int((score[y == 1] == knot).sum()),
                        "positive_at_or_below_n": int((score[y == 1] <= knot).sum()),
                        "strict_positive_cdf": float((score[y == 1] < knot).mean()),
                        "inclusive_positive_cdf": float((score[y == 1] <= knot).mean()),
                        "acceptance_recall": float((score[y == 1] >= knot).mean()), "selected": bool(knot == theta)})
                ranks_s, ranks_z = rankdata(score), rankdata(logodds)
                for i, r in enumerate(rr):
                    decisions.append({**r, "score_average_rank": float(ranks_s[i]), "logodds_average_rank": float(ranks_z[i]),
                        "calibration_score_threshold": theta, "calibration_logodds_threshold": theta_z,
                        "resubstitution_accepted": bool(pred[i]), "below_threshold": bool(score[i] < theta),
                        "at_threshold": bool(score[i] == theta), "at_or_below_threshold": bool(score[i] <= theta),
                        "positive_lower_tail_strict": bool(y[i] == 1 and score[i] < theta),
                        "positive_lower_tail_inclusive": bool(y[i] == 1 and score[i] <= theta)})
            for label, mask in [("all", np.ones(48, bool)), ("failure", y == 0), ("success", y == 1)]:
                for scale, col in [("score", 2), ("logodds", 3)]:
                    a, b = arrays[(ds, ct, "ab_bare")][col][mask], arrays[(ds, ct, "ab_space")][col][mask]
                    correlations.append({"dataset": ds, "context": ct, "class": label, "scale": scale,
                        "n": int(mask.sum()), "groups": len({groups[i] for i in np.flatnonzero(mask)}),
                        **paired_corr(a, b)})
            a, b = arrays[(ds, ct, "ab_bare")][2], arrays[(ds, ct, "ab_space")][2]
            ta, _, pa = fits[(ds, ct, "ab_bare")]
            tb, _, pb = fits[(ds, ct, "ab_space")]
            r = {"dataset": ds, "context": ct, "diagnostic_scope": "same_subset_resubstitution", "n": 48,
                 "groups": len(set(groups)), "bare_score_threshold": ta, "space_score_threshold": tb,
                 "disagree_n": int((pa != pb).sum()), "disagreement_fraction": float((pa != pb).mean()),
                 "bare_accept_space_reject_n": int((pa & ~pb).sum()),
                 "bare_reject_space_accept_n": int((~pa & pb).sum()),
                 "success_disagree_n": int(((pa != pb) & (y == 1)).sum()),
                 "failure_disagree_n": int(((pa != pb) & (y == 0)).sum()),
                 "bare_resubstitution_recall": float(pa[y == 1].mean()), "space_resubstitution_recall": float(pb[y == 1].mean()),
                 "bare_resubstitution_fsr": float(pa[y == 0].mean()), "space_resubstitution_fsr": float(pb[y == 0].mean())}
            for name, lower_a, lower_b in [("strict", (a < ta) & (y == 1), (b < tb) & (y == 1)),
                                           ("inclusive", (a <= ta) & (y == 1), (b <= tb) & (y == 1))]:
                union, intersect = int((lower_a | lower_b).sum()), int((lower_a & lower_b).sum())
                r.update({name + "_bare_n": int(lower_a.sum()), name + "_space_n": int(lower_b.sum()),
                          name + "_intersection_n": intersect, name + "_union_n": union,
                          name + "_jaccard": intersect / union if union else 1.0,
                          name + "_symmetric_difference_n": int((lower_a != lower_b).sum())})
            check(r["success_disagree_n"] == r["strict_symmetric_difference_n"], "positive_decision_tail_identity")
            comparisons.append(r)
    check(all(sha(p) == h for p, h in pins.items()), "frozen_inputs_unchanged_before_write")
    output.mkdir(parents=True, exist_ok=False)
    tables = {"class-distributions.csv": distributions, "ab-rank-correlations.csv": correlations,
              "calibration-knots-and-resubstitution.csv": thresholds, "all-positive-knots.csv": knots,
              "per-trial-scores-ranks-decisions.csv": decisions, "ab-calibrated-comparison.csv": comparisons,
              "empirical-cdfs.csv": ecdfs, "cross-class-ties.csv": cross_ties}
    for name, rr in tables.items():
        csvout(output / name, rr)
    jsonout(output / "results.json", {"protocol_id": protocol["protocol_id"], "sample_sizes": sample_sizes,
        "scope": protocol["interpretive_limits"], "class_distributions": distributions,
        "ab_correlations": correlations, "calibration": thresholds, "ab_comparisons": comparisons,
        "cross_class_ties": cross_ties})
    figure(output, arrays, fits, correlations, comparisons)
    narrative(output, sample_sizes, correlations, thresholds, comparisons, distributions)
    check(all(sha(p) == h for p, h in pins.items()), "frozen_inputs_unchanged_after_write")
    environment = {"python": sys.executable, "python_version": sys.version, "platform": platform.platform(),
                   "numpy": np.__version__, "scipy": scipy.__version__, "matplotlib": matplotlib.__version__,
                   "storage": "E: SATA HDD", "model_calls": 0, "resampling_draws": 0,
                   "new_calibration_fits_on_existing_audit": 32, "heldout_evaluation": False}
    jsonout(output / "verification.json", {"status": "PASS", "checks": dict(checks),
        "checks_passed": sum(checks.values()), "failed": 0, "scope": "Direct raw lineage and two numerical definitions for ranks/thresholds; no model rerun or new resampling.",
        "input_hashes": pins, "environment": environment})
    jsonout(output / "completion.json", {"status": "PASS_NUMERICAL_PENDING_VISUAL_REVIEW",
        "utc": datetime.now(timezone.utc).isoformat(), "protocol_sha256": pins[str(ROOT / "protocol.json")],
        "input_hashes": pins, "output_sha256": {p.name: sha(p) for p in output.iterdir() if p.is_file()},
        "table_rows": {name: len(rr) for name, rr in tables.items()}, "checks_passed": sum(checks.values()),
        "environment": environment, "interpretation": protocol["interpretive_limits"]})
    print(json.dumps({"status": "PASS", "output": str(output), "checks": sum(checks.values()), "comparisons": comparisons}))


def figure(output, arrays, fits, correlations, comparisons):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.labelsize": 8,
                         "axes.titlesize": 9, "xtick.labelsize": 7, "ytick.labelsize": 7,
                         "pdf.fonttype": 42, "ps.fonttype": 42, "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, axs = plt.subplots(4, 4, figsize=(7.35, 9.4), gridspec_kw={"wspace": .36, "hspace": .72})
    colors = {"ab_bare": "#0077BB", "ab_space": "#EE7733"}
    for row, ct in enumerate(CT):
        for dsidx, ds in enumerate(DS):
            ax = axs[row, 2 * dsidx]
            _, y, a, _ = arrays[(ds, ct, "ab_bare")]
            _, _, b, _ = arrays[(ds, ct, "ab_space")]
            rx, rz = rankdata(a), rankdata(b)
            ax.plot([1, 48], [1, 48], color=".82", linewidth=.8, zorder=0)
            ax.scatter(rx[y == 0], rz[y == 0], s=17, marker="o", facecolors="none", edgecolors=".4", linewidths=.7, label="Failure")
            ax.scatter(rx[y == 1], rz[y == 1], s=19, marker="^", color="#0077BB", linewidths=.3, label="Success")
            ax.set(xlim=(0, 49), ylim=(0, 49), xticks=[1, 24, 48], yticks=[1, 24, 48],
                   xlabel="Bare AB rank", ylabel="Space AB rank")
            r = next(r for r in correlations if r["dataset"] == ds and r["context"] == ct and r["class"] == "all" and r["scale"] == "score")
            ax.text(.05, .96, f"$\\rho$={r['spearman_rho']:.3f}", transform=ax.transAxes, va="top", fontsize=8,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=.8, pad=.2))
            ax.set_title(f"{chr(97 + row * 4 + dsidx * 2)}) {NAMES[ct]}", loc="left")
            ax = axs[row, 2 * dsidx + 1]
            allx = np.concatenate([arrays[(ds, ct, s)][3][y == 1] for s in ["ab_bare", "ab_space"]])
            lo, hi = float(allx.min()) - .5, float(allx.max()) + .5
            for sc, style in [("ab_bare", "-"), ("ab_space", "--")]:
                values = arrays[(ds, ct, sc)][3][y == 1]
                x = np.unique(values)
                cdf = np.array([(values <= t).mean() for t in x])
                ax.step(np.r_[lo, x, hi], np.r_[0, cdf, 1], where="post", color=colors[sc], linestyle=style, linewidth=1.3)
                _, tz, _ = fits[(ds, ct, sc)]
                ax.axvline(tz, color=colors[sc], linestyle=style, linewidth=.65, alpha=.65)
                ax.plot(tz, (values <= tz).mean(), marker="o", markersize=4, color=colors[sc],
                        markerfacecolor="white", markeredgewidth=1)
            ax.axhline(.1, color=".5", linewidth=.7, linestyle=":")
            ax.set(xlim=(lo, hi), ylim=(-.025, 1.035), yticks=[0, .1, .5, 1], xlabel="Positive log odds", ylabel="Empirical CDF")
            ax.tick_params(axis="y", pad=2)
            ax.set_title(f"{chr(98 + row * 4 + dsidx * 2)}) Positive scores", loc="left")
    fig.text(.285, .971, "RLBenchFail · 48 trials, 40 groups", ha="center", fontsize=9, fontweight="bold")
    fig.text(.715, .971, "REASSEMBLE · 48 trials, 48 groups", ha="center", fontsize=9, fontweight="bold")
    handles = [Line2D([], [], marker="o", linestyle="none", markerfacecolor="none", markeredgecolor=".4", label="Failure (24)"),
               Line2D([], [], marker="^", linestyle="none", color="#0077BB", label="Success (24)"),
               Line2D([], [], color=colors["ab_bare"], label="Bare AB CDF"),
               Line2D([], [], color=colors["ab_space"], linestyle="--", label="Space AB CDF")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, .956), ncol=4, frameon=False, fontsize=8, columnspacing=1)
    fig.subplots_adjust(left=.075, right=.985, top=.898, bottom=.115)
    fig.text(.075, .027, "Average ranks within 48 trials. CDF panels: 24 successes; vertical lines mark fitted 0.90-recall knots.\n"
             "Open circles show inclusive CDF at the knot; acceptance includes ties. Log-odds axes vary by panel.\n"
             "Repeated contexts share trials. Descriptive development sample; no held-out performance is shown.", fontsize=7.3, va="center")
    fig.savefig(output / "figure-scorer-ranks-positive-cdf.pdf", metadata={"Title": "Stored development scorer rankings and positive CDFs", "CreationDate": None, "ModDate": None})
    fig.savefig(output / "figure-scorer-ranks-positive-cdf.png", dpi=300)
    plt.close(fig)


def narrative(output, sample_sizes, correlations, thresholds, comparisons, distributions):
    rows = []
    for r in comparisons:
        rho = next(z for z in correlations if z["dataset"] == r["dataset"] and z["context"] == r["context"] and z["class"] == "all" and z["scale"] == "score")
        positive = next(z for z in correlations if z["dataset"] == r["dataset"] and z["context"] == r["context"] and z["class"] == "success" and z["scale"] == "score")
        rows.append(f"| {NAMES[r['dataset']]} | {NAMES[r['context']]} | {rho['spearman_rho']:.3f} | {positive['spearman_rho']:.3f} | {rho['kendall_tau_b']:.3f} | {r['inclusive_intersection_n']}/{r['inclusive_union_n']} | {r['disagree_n']}/48 | {100*r['bare_resubstitution_fsr']:.2f}/{100*r['space_resubstitution_fsr']:.2f} | {100*r['bare_resubstitution_recall']:.2f}/{100*r['space_resubstitution_recall']:.2f} |")
    rhoall = [r["spearman_rho"] for r in correlations if r["class"] == "all" and r["scale"] == "score"]
    diff = [r["disagree_n"] for r in comparisons]
    main = "\n".join(rows)
    english = f"""# Stored scorer analysis for Major Comment 1

This post-review descriptive analysis uses the frozen development audit: 48 trials per dataset, with 24 successes and 24 failures; RLBenchFail has 40 groups and REASSEMBLE 48. Joint, Single0, Single1, and derived Late reuse those trials. No new model calls, resampling, label changes, or held-out evaluations were performed. The all-four-scorer distributions, exact ties, and positive score knots are retained in the accompanying CSV/JSON files. The focused contrast is bare versus space-prefixed AB under the same AB instruction.

Bare and space AB are positively rank-associated, but their rankings are not identical. Across the eight dataset/context combinations, descriptive Spearman correlations range from {min(rhoall):.3f} to {max(rhoall):.3f}. The class-specific correlations are reported separately rather than combining repeated contexts into a nominally larger sample. The score CDFs and log-odds summaries retain exact ties; descriptive interpolated quantiles are not used to fit a threshold.

For each scorer and context, we fitted the original rule on this same 48-trial subset: select the highest observed positive score knot achieving at least 0.90 empirical recall (tolerance 1e-12), with acceptance at or above the knot. With 24 positives this generally permits at most two rejected successes; ties at the selected knot are retained. Lower-tail membership is reported both strictly below the knot (rejected positives) and at or below it (rejected plus boundary positives). The table reports inclusive-set intersection/union without breaking ties. The independently fitted AB policies disagree on {min(diff)}–{max(diff)} of 48 trials across contexts. These are resubstitution diagnostics. They connect the lexical event to the calibration rule, but do not estimate replacement-scorer held-out performance or show how the original held-out pooled-versus-pair interaction would change. One selected pair per trial also prevents this subset from replaying the original all-pair contrast.

| Dataset | Context | Spearman, all | Spearman, success | Kendall tau-b, all | Positive lower-tail intersection/union | Decision disagreement | FSR bare/space (%) | Recall bare/space (%) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{main}

The FSR columns use the same 24 failures that enter this diagnostic sample, and all calibrated recall values are recorded in `calibration-knots-and-resubstitution.csv`. Changing the lexical event can change ranking and the positive calibration tail even after each score receives its own recall threshold. Neither higher native agreement nor a lower resubstitution FSR establishes grasp validity. There is no selected winner, reversed label, or causal attribution to tokenization alone beyond the fixed AB candidate contrast.

Figure caption: Bare/space AB rankings and positive-score CDFs in the fixed development audit. Rank panels use average ranks over 48 trials; symbols distinguish the 24 failures and 24 successes. CDF panels use only the 24 positive log odds and separate horizontal scales, with vertical lines at each scorer's fitted 0.90-recall knot. Open circles denote inclusive CDF at the knot; the dotted horizontal line is 0.10. Acceptance includes boundary ties, so the strict CDF below the knot, rather than the displayed inclusive CDF, determines rejected-positive mass. Contexts share trials; all summaries are descriptive and no confidence intervals are implied.

Reproduce by dot-sourcing `E:/SoftwareX/Start-GraspExperiment.ps1`, then running `& E:/SoftwareX/.conda-envs/grasp-vlm/python.exe E:/SoftwareX/camv-eval-study-v1/amendments/reviewer-revision-20260914-v1/scorer/analyze_stored_scorers_v2.py --output E:/SoftwareX/camv-eval-study-v1/amendments/reviewer-revision-20260914-v1/scorer/replay-v2`.
"""
    (output / "manuscript-insert.en.md").write_text(english, encoding="utf-8")
    korean = f"""# MC1 주요 결과

기존 development audit의 데이터셋별 48 trial(성공 24, 실패 24)만 분석했다. RLBenchFail은 40개 group, REASSEMBLE은 48개 group이며, 네 context는 같은 trial을 반복 사용한다. 새 VLM 추론·bootstrap·평가 실험은 없었다.

bare/space AB의 전체 점수 Spearman 상관은 context별 {min(rhoall):.3f}–{max(rhoall):.3f}였다. 두 scorer에 동일한 양성 knot 기반 recall 0.90 규칙을 각각 적용한 뒤에도 48개 trial 중 {min(diff)}–{max(diff)}개 판정이 달랐다. 성공 하위 점수 집합의 겹침은 boundary 동점을 유지한 채 별도로 계산했다. 따라서 0.5에서의 native agreement 차이에 더해, 점수 순위와 실제 보정 규칙 사이의 연결을 같은 자료에서 직접 확인할 수 있다.

{main}

위 행의 열 순서는 데이터셋/context/전체 Spearman/성공 Spearman/전체 Kendall/양성 하위집합 교집합·합집합/판정 불일치/FSR bare·space/recall bare·space이다. 정확한 문턱값·recall·실패 수·동점 수는 calibration-knots-and-resubstitution.csv와 ab-calibrated-comparison.csv에 있다. 네 scorer의 분포는 모두 보존했고, AB 두 scorer를 주된 비교로 고정했다.

FSR과 recall은 보정에 사용한 동일 부분집합에서 다시 계산한 resubstitution 진단이다. 새 scorer의 독립 평가 성능, 원래 held-out interaction의 변화, 또는 약한 분별력의 원인을 입증하지 않는다. 독립 평가나 positive control은 이번 작업에 포함되지 않았다. 원래 prospective 결과를 대체하지 않는다.
"""
    (output / "findings.ko.md").write_text(korean, encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=ROOT / "results-v2")
    analyze(p.parse_args().output.resolve())
