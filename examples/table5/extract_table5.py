"""Extract existing paired bootstrap results; no fitting or random draws.

Run --extract once in the study workspace to capture the four-method slices.
The default replay reads only local inputs and independently reconstructs
Table 5. All stored scores, thresholds, and original results remain untouched.
"""
from pathlib import Path
import argparse, csv, hashlib, json, platform, sys
import numpy as np

A = Path(__file__).resolve().parent
METHODS = ['joint_pooled', 'joint_pair', 'late_pooled', 'late_pair']
METRICS = ['false_success_rate', 'success_recall']
LABELS = ['RLBench confirmation', 'UR5 source transfer', 'REASSEMBLE local', 'RL-to-REASSEMBLE transfer']

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def writej(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

def extract():
    study = A.parents[1]
    package = study / 'staging/p0-e2e-20260914-v1/package/release-v6'
    casefile = study / 'amendments/score-ties-revision-20260915-v1/scorer/inputs/cases.json'
    evidence = study / 'manuscript/ieee-access-draft-20260915-v7-minor/evidence/paper-tables.json'
    tables = json.loads(evidence.read_text(encoding='utf-8'))['tables']
    cases = json.loads(casefile.read_text(encoding='utf-8'))
    pins = [{'path': str(p), 'sha256': sha(p)} for p in [casefile, evidence]]
    records = []
    (A / 'inputs').mkdir(exist_ok=True)
    for case, label in zip(cases, LABELS):
        root = package / case['reference']
        meta = json.loads((root / 'metadata.json').read_text(encoding='utf-8'))
        assert meta['B'] == 2000 and meta['seeds'] == [17, 29, 43]
        ix = [meta['method_axis'].index(m) for m in METHODS]
        wi = meta['weightings'].index('sample')
        assert meta['metric_axis'] == METRICS
        with np.load(root / 'bootstrap-arrays.npz', allow_pickle=False) as src:
            projection = {
                name: np.take(np.take(src[name], wi, axis=-3), ix, axis=-2)
                for name in ['point_by_seed', 'conditional_by_seed', 'refit_by_seed']
            }
        out = A / 'inputs' / (case['case_id'] + '.npz')
        np.savez_compressed(out, **projection)
        records.append(dict(case_id=case['case_id'], evaluation=label, B=meta['B'],
                            seeds=meta['seeds'], methods=METHODS, metrics=METRICS,
                            weighting='sample', scope=case['scope'],
                            projection=out.relative_to(A).as_posix(), sha256=sha(out),
                            expected=[r for r in tables[case['case_id'] + '_contrasts']
                                      if r['contrast'] == 'interaction' and r['weighting'] == 'sample'],
                            original_test=next(r for r in tables['primary_holm4'] if r['case_id'] == case['case_id'])))
        pins.extend({'path': str(p), 'sha256': sha(p)} for p in [root / 'metadata.json', root / 'bootstrap-arrays.npz'])
    writej(A / 'inputs/cases.json', records)
    writej(A / 'inputs/source-hashes.json', pins)

def interaction(x):
    # Same seed is not an independent sampling unit. Average seeds first,
    # retaining the original paired development/evaluation draw index.
    v = x.mean(axis=0)
    return (v[..., 1, :] - v[..., 3, :]) - (v[..., 0, :] - v[..., 2, :])

def replay(output):
    output.mkdir(parents=True, exist_ok=True)
    cases = json.loads((A / 'inputs/cases.json').read_text(encoding='utf-8'))
    rows, checks, table = [], [], []
    for case in cases:
        p = A / case['projection']
        assert sha(p) == case['sha256']
        with np.load(p, allow_pickle=False) as arrays:
            point = interaction(arrays['point_by_seed'])
            cond = interaction(arrays['conditional_by_seed'])
            refit = interaction(arrays['refit_by_seed'])
        assert point.shape == (2,) and cond.shape == refit.shape == (2000, 2)
        assert np.isfinite(point).all() and np.isfinite(cond).all() and np.isfinite(refit).all()
        cci = np.quantile(cond, [.025, .975], axis=0, method='linear')
        rci = np.quantile(refit, [.025, .975], axis=0, method='linear')
        values = []
        for ki, metric in enumerate(METRICS):
            old = next(r for r in case['expected'] if r['metric'] == metric)
            # Reconstruct approximate centered p only to verify the saved test;
            # no new conditional p-values or multiplicity family are introduced.
            approximate_p = (1 + np.sum(np.abs(refit[:, ki] - point[ki]) >= abs(point[ki]))) / (case['B'] + 1)
            vals = dict(estimate=point[ki], conditional_lower=cci[0, ki], conditional_upper=cci[1, ki],
                        refit_lower=rci[0, ki], refit_upper=rci[1, ki],
                        conditional_width=np.diff(cci[:, ki])[0], refit_width=np.diff(rci[:, ki])[0],
                        approximate_centered_bootstrap_p=approximate_p)
            for key, value in vals.items():
                delta = abs(float(value) - float(old[key]))
                checks.append(dict(case_id=case['case_id'], metric=metric, field=key,
                                   absolute_difference=delta, passed=delta <= 1e-12))
            rows.append(dict(case_id=case['case_id'], evaluation=case['evaluation'], metric=metric,
                             estimate_pp=100*point[ki], conditional_lower_pp=100*cci[0, ki], conditional_upper_pp=100*cci[1, ki],
                             refit_lower_pp=100*rci[0, ki], refit_upper_pp=100*rci[1, ki],
                             conditional_valid=case['B'], refit_valid=case['B'],
                             refit_to_conditional_width_ratio=vals['refit_width']/vals['conditional_width']))
            values.extend([f'{100*point[ki]:+.3f} [{100*rci[0,ki]:+.3f}, {100*rci[1,ki]:+.3f}]',
                           f'[{100*cci[0,ki]:+.3f}, {100*cci[1,ki]:+.3f}]'])
        op = case['original_test']
        assert abs(float(op['fsr_approximate_centered_bootstrap_p']) - float(case['expected'][0]['approximate_centered_bootstrap_p'])) < 1e-12
        table.append('| ' + ' | '.join([case['evaluation'], *values,
                        f"{float(op['fsr_approximate_centered_bootstrap_p']):.6f}", f"{float(op['fsr_holm4_adjusted_approximate_p']):.3f}"]) + ' |')
    assert len(checks) == 64 and all(c['passed'] for c in checks)
    with (output / 'table5-intervals.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (output / 'table5-rows.md').write_text('\n'.join(table) + '\n', encoding='utf-8')
    writej(output / 'verification.json', dict(passed=True, checks=checks, check_count=len(checks),
        max_absolute_difference=max(c['absolute_difference'] for c in checks),
        environment=dict(python=sys.version, executable=sys.executable, numpy=np.__version__,
                         platform=platform.platform(), storage='E: SATA HDD'),
        calculation='Stored four-policy slice; average seeds; paired interaction; linear 2.5/97.5 percentiles. No new random draws.'))
    print(json.dumps(dict(passed=True, checks=len(checks), rows=len(rows), output=str(output))))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--extract', action='store_true'); parser.add_argument('--output', type=Path, default=A/'table5')
    args = parser.parse_args()
    if args.extract: extract()
    replay(args.output)
