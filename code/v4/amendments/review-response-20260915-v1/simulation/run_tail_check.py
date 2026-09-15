"""One frozen post hoc finite-B sensitivity using the original outer datasets."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
import csv,hashlib,json,time
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import review_core as c
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,o):
    with p.open('x',encoding='utf-8') as f:json.dump(o,f,indent=2,allow_nan=False)
COND=next(x for x in c.conditions() if x['id']=='H065_Q125')
def chunk(start):
    vals=[c.outer(COND,i,4999) for i in range(start,start+25)]
    return {k:np.stack([v[k] for v in vals]) for k in vals[0]}
def run():
    out=HERE/'tail-check';out.mkdir(exist_ok=False)
    pin={p.name:sha(p) for p in [HERE/'review_core.py',HERE/'numerics.py',HERE/'run_tail_check.py',HERE/'BCa-methods-addendum.md']}
    write(out/'freeze.json',{'pins':pin,'condition':COND,'outer_indices':[0,999],'M':1000,'B':4999,'storage':'E: SATA HDD','new_model_calls':0})
    started=time.perf_counter();count=0
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(chunk,i):i for i in range(0,1000,25)}
        for job in as_completed(jobs):
            i=jobs[job];v=job.result()
            with np.load(HERE/'run'/COND['id']/'outer'/f'{i:06d}.npz',allow_pickle=False) as old:
                for k in ('point','point_policy','point_thresholds','fitted_truth','jackknife_dev','jackknife_eval','dev_features','eval_features'):
                    np.testing.assert_array_equal(v[k],old[k])
                for k in ('refit_draws','conditional_draws'):np.testing.assert_array_equal(v[k][:,:999],old[k])
            dest=out/f'{i:06d}.npz'
            with dest.open('xb') as f:np.savez_compressed(f,**v)
            write(dest.with_suffix('.json'),{'start':i,'stop':i+25,'sha256':sha(dest),'original_data_and_draw_prefix_identical':True})
            count+=1
            if count%8==0:print(json.dumps({'chunks':count,'total':40,'elapsed_seconds':round(time.perf_counter()-started,1)}),flush=True)
    assert all(sha(HERE/k)==v for k,v in pin.items())
    write(out/'completion.json',{'status':'COMPLETE','outer_datasets':1000,'B':4999,'seconds':time.perf_counter()-started,'paired_data_and_prefix_checks':'PASS','pins':pin})
    print('TAIL SENSITIVITY COMPLETE',flush=True)
if __name__=='__main__':run()
