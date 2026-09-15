"""Versioned finite-B recovery: original float prefix plus 4000 new paired draws."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import hashlib,json,time,sys,platform
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import scipy
import review_core as c
import numerics as n

HERE=Path(__file__).resolve().parent
OUT=HERE/'tail-check-v2'
COND=next(x for x in c.conditions() if x['id']=='H065_Q125')
B=4999
TOL=2e-15
IDENTITY=('point','point_policy','point_thresholds','fitted_truth','jackknife_dev','jackknife_eval','dev_features','eval_features')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False)
def pins():
    return {name:sha(HERE/name) for name in ('review_core.py','numerics.py','run_tail_check_v2.py','TAIL-CHECK-V2-PROTOCOL.md','BCa-methods-addendum.md','run_tail_check.py')}

def extend(old,index):
    d=c.generator(COND,40,10,index);e=c.generator(COND,120,20,index)
    md=c.rng(30,index).multinomial(40,np.full(40,1/40),size=B)
    me=c.rng(40,index).multinomial(120,np.full(120,1/120),size=B)
    for domain,groups,w in ((30,40,md),(40,120,me)):
        original=c.rng(domain,index).multinomial(groups,np.full(groups,1/groups),size=999)
        np.testing.assert_array_equal(w[:999],original)
    plan=n.Plan(d,both_labels=True);fit=plan.fit(np.ones(40,int))[0]
    policy=n.rates(e,fit,np.ones(120,int))[0];point=n.interaction(policy)
    jd,je=c.jackknife(plan,e,fit)
    checked=dict(point=point,point_policy=policy,point_thresholds=fit,
                 fitted_truth=n.interaction(c.oracle(COND,fit)[0]),jackknife_dev=jd,jackknife_eval=je,
                 dev_features=c.empirical_features(d),eval_features=c.empirical_features(e))
    for key in IDENTITY:np.testing.assert_array_equal(checked[key],old[key])
    conditional=n.interaction(n.rates(e,fit,me));refit=np.full((B,2),np.nan)
    for start in range(0,B,64):
        refit[start:start+64]=n.interaction(n.rates(e,plan.fit(md[start:start+64]),me[start:start+64]))
    raw_max=[];raw_counts=[]
    for key,arr in (('conditional_draws',conditional),('refit_draws',refit)):
        raw=arr[:999];original=old[key]
        np.testing.assert_array_equal(np.isfinite(raw),np.isfinite(original))
        delta=np.abs(raw-original)
        np.testing.assert_allclose(raw,original,rtol=0,atol=TOL,equal_nan=True)
        raw_max.append(np.nanmax(delta,axis=0));raw_counts.append(np.sum((raw!=original)&np.isfinite(raw),axis=0))
        arr[:999]=original
        np.testing.assert_array_equal(arr[:999],original)
    ci=np.full((5,2,2),np.nan)
    for y in (0,1):
        ci[0,y]=n.interval(conditional[:,y]);ci[1,y]=n.interval(refit[:,y]);ci[2,y]=n.interval(refit[:,y],point[y],True)
    ci[3],_=n.sandwich(e,fit,point)
    np.testing.assert_array_equal(ci[3],old['intervals'][3])
    ci[4],diag=c.bca(point,refit,jd,je)
    pvalues=np.array([[n.centered_p(point[y],v[:,y]) for y in (0,1)] for v in (conditional,refit)])
    return dict(**checked,intervals=ci,pvalues=pvalues,bca_diagnostics=diag,
                refit_draws=refit,conditional_draws=conditional,
                finite_draw_counts=np.array([np.isfinite(conditional).sum(axis=0),np.isfinite(refit).sum(axis=0)]),
                raw_prefix_max_absolute_difference=np.array(raw_max),raw_prefix_mismatch_counts=np.array(raw_counts),
                integer_prefix_checked=np.array([True,True]),combined_float_prefix_exact=np.array([True,True]))

def chunk(start):
    oldfile=HERE/'run'/COND['id']/'outer'/f'{start:06d}.npz'
    receipt=json.loads(oldfile.with_suffix('.json').read_text())
    assert sha(oldfile)==receipt['sha256']
    with np.load(oldfile,allow_pickle=False) as z:original={k:z[k] for k in z.files}
    records=[extend({k:v[j] for k,v in original.items()},start+j) for j in range(25)]
    return {k:np.stack([v[k] for v in records]) for k in records[0]}

def main():
    OUT.mkdir(exist_ok=False)
    pin=pins();initial_freeze=HERE/'tail-check/freeze.json'
    assert not list((HERE/'tail-check').glob('*.npz'))
    oldpin=json.loads((HERE/'run/freeze.json').read_text())['pins']
    for name,digest in oldpin.items():assert sha(HERE/name)==digest
    write(OUT/'previous-attempt-failure.json',dict(status='PRESERVED_TECHNICAL_FAILURE',
         previous_script='run_tail_check.py',previous_script_sha256=sha(HERE/'run_tail_check.py'),
         previous_freeze_sha256=sha(initial_freeze),committed_scientific_chunks=0,
         root_observed_failure='Exact floating prefix assertion: 37/49950 values differed; maximum absolute difference approximately 6.66e-16.',
         evidence='Root execution report; filesystem inspection confirms only the prior freeze and no scientific NPZ chunks.',
         reason_for_v2='Verify integer prefixes exactly and numerical prefix within fixed tolerance, then explicitly retain the saved original float prefix.'))
    write(OUT/'freeze.json',dict(pins=pin,original_run_freeze_sha256=sha(HERE/'run/freeze.json'),
         original_summary_reference_sha256=sha(HERE/'summary/reference-targets.csv'),
         condition=COND,outer_indices=[0,999],M=1000,B=B,retained_draws=999,additional_paired_draws_per_outer=4000,
         raw_prefix_absolute_tolerance=TOL,raw_prefix_relative_tolerance=0,
         original_float_prefix_reused=True,integer_prefix_validation='all 1000 outer indices; independent B999 and B4999 generation',
         storage='E: SATA HDD',python=sys.executable,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),
         new_outer_datasets=0,new_reference_datasets=0,new_model_calls=0))
    fixture=900104;old=c.outer(COND,fixture,999);probe=extend(old,fixture)
    write(OUT/'preflight.json',dict(status='PASS',excluded_index=fixture,pins=pin,
         integer_prefix_checked=bool(probe['integer_prefix_checked'].all()),combined_float_prefix_exact=bool(probe['combined_float_prefix_exact'].all()),
         raw_prefix_max_absolute_difference=float(probe['raw_prefix_max_absolute_difference'].max()),
         scientific_chunks_written_before_preflight=0))
    started=time.perf_counter();count=0
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(chunk,start):start for start in range(0,1000,25)}
        for job in as_completed(jobs):
            start=jobs[job];data=job.result();dst=OUT/f'{start:06d}.npz'
            with dst.open('xb') as f:np.savez_compressed(f,**data)
            write(dst.with_suffix('.json'),dict(start=start,stop=start+25,sha256=sha(dst),
                 max_raw_prefix_difference=float(data['raw_prefix_max_absolute_difference'].max()),
                 raw_prefix_mismatches=int(data['raw_prefix_mismatch_counts'].sum()),
                 integer_prefix_exact=bool(data['integer_prefix_checked'].all()),combined_float_prefix_exact=bool(data['combined_float_prefix_exact'].all())))
            count+=1
            if count%8==0:print(json.dumps(dict(chunks=count,total=40,elapsed_seconds=round(time.perf_counter()-started,1))),flush=True)
    assert pins()==pin
    assert sha(initial_freeze)==json.loads((OUT/'previous-attempt-failure.json').read_text())['previous_freeze_sha256']
    write(OUT/'completion.json',dict(status='COMPLETE',outer_datasets_reused=1000,B=B,
         additional_paired_bootstrap_replicates=4000000,new_outer_datasets=0,new_reference_datasets=0,new_model_calls=0,
         committed_chunks=count,seconds=time.perf_counter()-started,pins=pin))
    print('TAIL SENSITIVITY V2 COMPLETE',flush=True)
if __name__=='__main__':main()
