from pathlib import Path
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import sys, json, hashlib, time, platform, argparse
sys.dont_write_bytecode=True
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import numpy as np
import extended_core as x
import numerics as n
R=Path(__file__).parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2)
def pins():return {name:sha(R/name) for name in ['PROTOCOL.md','group-profiles.json','extended_core.py','run_extended.py','numerics.py','review_core.py']}
def preflight():
    start=time.perf_counter();checked=[]
    for law in x.conditions():
        d=x.generator(law,'dev',10,900001);p=n.Plan(d,both_labels=True);fit=p.fit(np.ones(d.groups,int))[0]
        for method,score in enumerate((d.joint,d.late)):
            for j,cols in enumerate(([0,1,2],[0],[1],[2])):
                pos=score[d.y==1][:,cols].ravel()
                expected=max(v for v in np.unique(pos) if np.mean(pos>=v)+1e-12>=.9)
                assert fit[method*4+j]==expected
        if law['exact_zero']:
            # Reflection swaps heterogeneous offsets. Each method's *marginal*
            # distribution of pair-minus-pooled rates is therefore identical.
            assert np.array_equal(np.array(law['offset'])[::-1],law['late_offset'])
            assert not np.array_equal(d.joint,d.late)
        v=x.outer(law,900002,B=99)
        np.testing.assert_allclose(np.diff(v['intervals'][1],axis=-1),np.diff(v['intervals'][2],axis=-1),atol=1e-14)
        np.testing.assert_allclose(v['intervals'][1].mean(axis=-1)+v['intervals'][2].mean(axis=-1),2*v['point'],atol=1e-14)
        assert np.isfinite(v['fitted_truth']).all()
        checked.append(law['id'])
    write(R/'preflight.json',{'status':'PASS','conditions':checked,'pins':pins(),'excluded_indices':[900001,900002],'elapsed_seconds':time.perf_counter()-start})
    print(json.dumps({'status':'PASS','elapsed_seconds':time.perf_counter()-start}),flush=True)
def chunk(job):
    kind,law,a,b=job
    if kind=='reference':return {'values':np.stack([x.reference(law,i) for i in range(a,b)])}
    rows=[x.outer(law,i) for i in range(a,b)]
    return {k:np.stack([row[k] for row in rows]) for k in rows[0]}
def run(workers):
    pin=pins();assert json.loads((R/'preflight.json').read_text())['pins']==pin
    out=R/'run';out.mkdir(exist_ok=True)
    if not (out/'freeze.json').exists():write(out/'freeze.json',{'pins':pin,'M':1000,'B':999,'reference_n':16384,'laws':x.conditions(),'rng_root':x.ROOT,'python':sys.executable,'platform':platform.platform(),'storage':'E: SATA HDD','workers':workers})
    assert json.loads((out/'freeze.json').read_text())['pins']==pin
    jobs=[]
    for law in x.conditions():
        for kind,total,step in [('outer',1000,10)]+([] if law['exact_zero'] else [('reference',16384,512)]):
            folder=out/law['id']/kind;folder.mkdir(parents=True,exist_ok=True)
            for a in range(0,total,step):
                dst=folder/f'{a:06d}.npz'
                if dst.with_suffix('.json').exists():assert sha(dst)==json.loads(dst.with_suffix('.json').read_text())['sha256'];continue
                assert not dst.exists(),'Orphan chunk needs recovery.'
                jobs.append(((kind,law,a,min(a+step,total)),dst))
    started=time.perf_counter();done_count=0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        it=iter(jobs);pending={}
        def submit():
            try:job,dst=next(it)
            except StopIteration:return
            pending[pool.submit(chunk,job)]=(job,dst)
        for _ in range(workers):submit()
        while pending:
            completed,_=wait(pending,return_when=FIRST_COMPLETED)
            for f in completed:
                job,dst=pending.pop(f);values=f.result()
                with dst.open('xb') as fp:np.savez_compressed(fp,**values)
                write(dst.with_suffix('.json'),{'kind':job[0],'condition':job[1]['id'],'start':job[2],'stop':job[3],'sha256':sha(dst)})
                done_count+=1
                if done_count%5==0:
                    progress={'chunks_complete':done_count,'chunks_planned':len(jobs),'condition':job[1]['id'],'elapsed_seconds':round(time.perf_counter()-started,1)}
                    (out/'progress.json').write_text(json.dumps(progress))
                    print(json.dumps(progress),flush=True)
                submit()
    assert pin==pins()
    if not (out/'completion.json').exists():write(out/'completion.json',{'status':'COMPLETE','outer_datasets':3000,'reference_datasets':32768,'pins':pin,'elapsed_seconds':time.perf_counter()-started,'new_model_calls':0})
    print('EXTENDED SIMULATION COMPLETE',flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['check','run']);parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    preflight() if args.action=='check' else run(args.workers)
