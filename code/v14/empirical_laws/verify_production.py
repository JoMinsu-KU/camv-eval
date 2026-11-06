"""Independent saved-record, pairing, coverage and replay audit; no scientific mutation."""
from pathlib import Path
import csv,json,time
import numpy as np
import empirical_law_engine as e
import run_empirical_laws as r

here=Path(__file__).resolve().parent
start=time.perf_counter();p=r.check_protocol();data=e.load_inputs();checks=[]
for cohort in ('RL','RE'):
    for index in range(p['M']):
        saved={}
        for variant in ('bare','space'):
            path=here/'outer'/cohort/variant/f'{index:04}.npz'
            with np.load(path) as f:saved[variant]={k:f[k] for k in f.files}
            x=saved[variant]
            assert x['refit_draws'].shape==x['conditional_draws'].shape==(999,2)
            assert x['intervals'].shape==(5,2,2)
            assert int(x['dev_multiplicity'].sum())==p['groups'][cohort][0]
            assert int(x['eval_multiplicity'].sum())==p['groups'][cohort][1]
            assert x['jackknife_dev'].shape==(p['groups'][cohort][0],2)
            assert x['jackknife_eval'].shape==(p['groups'][cohort][1],2)
            np.testing.assert_allclose(np.diff(x['intervals'][1],axis=-1),np.diff(x['intervals'][2],axis=-1),rtol=0,atol=1e-15)
            for k in (0,1):
                if np.isfinite(x['bca_diagnostics'][k,6]):
                    ties=np.mean(x['refit_draws'][:,k]==x['point'][k])
                    np.testing.assert_equal(x['bca_diagnostics'][k,6],ties)
            if index in (0,17,999):
                replay=e.outer(data,cohort,index,999)[variant]
                for key in x:np.testing.assert_array_equal(x[key],replay[key],err_msg=f'{cohort}/{variant}/{index}/{key}')
            if index<10:
                with np.load(here/'pilot'/cohort/variant/f'outer-{index:04}.npz') as pilot:
                    for key in pilot.files:np.testing.assert_array_equal(x[key],pilot[key])
        for key in ('dev_multiplicity','eval_multiplicity'):
            np.testing.assert_array_equal(saved['bare'][key],saved['space'][key])
    checks.append(dict(cohort=cohort,all_1000_outer_shapes_and_occurrence_counts=True,
                       all_bare_space_draw_pairing=True,percentile_basic_width_identity=True,
                       exact_bca_tie_rank=True,pilot_first_10_bit_exact=True,
                       fresh_replay_indices=[0,17,999],fresh_replay_all_arrays_bit_exact=True))

with (here/'reference-targets.csv').open(newline='') as f:refs=list(csv.DictReader(f))
reference_max_mean_roundoff=0.
for row in refs:
    with np.load(here/'reference'/f"{row['cohort']}-{row['scorer']}.npz") as f:
        values=f['reference_values'];weights=f['development_multiplicity']
    k=e.METRICS.index(row['metric']);valid=np.isfinite(values).all(axis=1)
    mean=np.mean(values[valid,k]);se=np.std(values[valid,k],ddof=1)/np.sqrt(valid.sum())
    reference_max_mean_roundoff=max(reference_max_mean_roundoff,abs(mean-float(row['target'])))
    # Column-contiguous and axis-wise sums have different floating reduction orders.
    np.testing.assert_allclose(mean,float(row['target']),rtol=0,atol=1e-13)
    np.testing.assert_allclose(se,float(row['mcse']),rtol=0,atol=1e-15)
    assert se<=p['reference_mcse_max_rate']
    assert len(values)==int(row['planned']) and valid.sum()==int(row['available'])
    assert np.all(weights.sum(axis=1)==p['groups'][row['cohort']][0])
checks.append(dict(reference_rows=8,all_independent_reference_means_mcse_and_valid_counts=True,
                   maximum_reference_mcse_pp=max(float(row['mcse_pp']) for row in refs),
                   maximum_reference_mean_reduction_roundoff=reference_max_mean_roundoff))

with (here/'coverage.csv').open(newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==80
refmap={(v['cohort'],v['scorer'],v['metric']):float(v['target']) for v in refs}
for row in rows:
    with np.load(here/f"summary-arrays-{row['cohort']}-{row['scorer']}.npz") as f:
        k=e.METRICS.index(row['metric']);j=e.METHODS.index(row['method'])
        ci=f['intervals'][:,j,k];truth=f['fitted_truth'][:,k]
    target=truth if row['target']=='fitted_policy' else refmap[(row['cohort'],row['scorer'],row['metric'])]
    valid=np.isfinite(ci).all(axis=1)&np.isfinite(target)
    covered=valid&(ci[:,0]<=target)&(target<=ci[:,1])
    assert int(valid.sum())==int(row['available']) and int(covered.sum())==int(row['covered'])
    np.testing.assert_allclose(100*covered.mean(),float(row['coverage_planned_pct']),rtol=0,atol=1e-12)
checks.append(dict(all_80_coverage_rows_independently_recounted=True))

r.check_protocol()
e.dump(here/'postrun-validation.json',dict(status='PASS',checks=checks,
       elapsed_seconds=time.perf_counter()-start,frozen_protocol_sha256=e.sha(here/'frozen-protocol.json')))
files=sorted(set((here/'outer').rglob('*.npz'))|set((here/'reference').glob('*.npz'))|
             set(here.glob('*.csv'))|set(here.glob('summary-arrays-*.npz'))|
             {here/'completion.json',here/'postrun-validation.json'})
e.dump(here/'output-manifest.json',dict(algorithm='SHA-256',files={str(v.relative_to(here)):e.sha(v) for v in files}))
print(json.dumps(dict(status='PASS',checks=len(checks),hashed_outputs=len(files),elapsed_seconds=time.perf_counter()-start),indent=2))
