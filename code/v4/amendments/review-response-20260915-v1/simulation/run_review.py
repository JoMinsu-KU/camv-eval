"""Hash-frozen, resumable CPU execution of the limited review simulation."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
import argparse, hashlib, json, platform, sys, time
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import numpy as np
import scipy
from scipy.stats import bootstrap
import review_core as c
import numerics as n

HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
    with Path(p).open('x',encoding='utf-8') as f:
        json.dump(obj,f,indent=2,allow_nan=False)
def pins():
    return {p.name:sha(p) for p in [HERE/'PROTOCOL.md',HERE/'review_core.py',HERE/'numerics.py',HERE/'run_review.py']}

def preflight():
    rows=[]
    def ok(s):rows.append(s)
    old=HERE.parents[1]/'score-ties-revision-20260915-v1/numerics.py'
    assert sha(old)==sha(HERE/'numerics.py');ok('numerical core byte-identical to prior validated implementation')
    for cond in c.conditions():
        d=c.generator(cond,40,10,900001);e=c.generator(cond,120,20,900001)
        plan=n.Plan(d,both_labels=True);fit=plan.fit(np.ones(40,int))[0]
        for j,score in enumerate((d.joint,d.late)):
            for k,cols in enumerate(([0,1,2],[0],[1],[2])):
                x=score[d.y==1][:,cols].ravel();vals=np.unique(x)
                expected=max(v for v in vals if np.mean(x>=v)+1e-12>=.9)
                assert fit[j*4+k]==expected
        if cond['separation']==0:
            np.testing.assert_array_equal(c.oracle(cond,fit)[:,:,0],c.oracle(cond,fit)[:,:,1])
        if cond['exact_zero']:
            ident=c.generator(cond,40,10,900001,lam=1)
            np.testing.assert_array_equal(ident.joint,ident.late)
        if cond['step']:
            q=cond['step'];x=np.array([-.5001,-.5,-.0001,0,.4999,.5,1.])
            for cutoff in (-.5,-.3,0,.2,.5):
                np.testing.assert_array_equal(q*np.floor(x/q)>=cutoff,x>=q*np.ceil(cutoff/q))
        pop=c.population_auc(cond)
        assert np.isfinite(pop).all() and np.all((pop>=0)&(pop<=1))
        if cond['separation']==0:np.testing.assert_allclose(pop,.5,rtol=0,atol=1e-14)
    ok('all eight laws: explicit positive thresholds, zero-separation oracle, inclusive quantizer, population AUC')
    for cond in [c.conditions()[4],c.conditions()[-1]]:
        d=c.generator(cond,40,10,900002);e=c.generator(cond,120,20,900002)
        plan=n.Plan(d,both_labels=True);fit=plan.fit(np.ones(40,int))[0]
        p=n.interaction(n.rates(e,fit,np.ones(120,int))[0])
        jd,je=c.jackknife(plan,e,fit)
        def statistic(di,ei):
            md=np.bincount(di.astype(int),minlength=40)
            me=np.bincount(ei.astype(int),minlength=120)
            ff=plan.fit(md)[0]
            return n.interaction(n.rates(e,ff,me)[0])
        res=bootstrap((np.arange(40),np.arange(120)),statistic,vectorized=False,paired=False,
                      n_resamples=199,method='BCa',rng=np.random.default_rng(900002))
        draws=res.bootstrap_distribution.T
        actual,diag=c.bca(p,draws,jd,je)
        expected=np.column_stack((res.confidence_interval.low,res.confidence_interval.high))
        np.testing.assert_allclose(actual,expected,rtol=1e-12,atol=1e-13,equal_nan=True)
        assert np.all(diag[:,0]==0)
        for i in (0,5,39):
            np.testing.assert_allclose(jd[i],statistic(np.delete(np.arange(40),i),np.arange(120)),rtol=0,atol=2e-15)
        for i in (0,5,119):
            np.testing.assert_allclose(je[i],statistic(np.arange(40),np.delete(np.arange(120),i)),rtol=0,atol=2e-15)
    ok('BCa limits agree with scipy.stats.bootstrap for two independent cluster samples, continuous and tied fixtures')
    ok('separate development/evaluation delete-one outputs match explicit statistics')
    probe=c.outer(c.conditions()[5],900003,999)
    np.testing.assert_allclose(np.diff(probe['intervals'][1],axis=-1),np.diff(probe['intervals'][2],axis=-1),rtol=0,atol=1e-14)
    np.testing.assert_allclose(probe['intervals'][1].mean(axis=-1)+probe['intervals'][2].mean(axis=-1),2*probe['point'],rtol=0,atol=1e-14)
    again=c.outer(c.conditions()[5],900003,999)
    for k in probe:np.testing.assert_array_equal(probe[k],again[k])
    ok('B999 fixed fixture deterministic and equal-width/reflected-center identities hold')
    report={'status':'PASS','checks':rows,'pins':pins(),'scipy':scipy.__version__,'excluded_indices':[900001,900002,900003]}
    write(HERE/'preflight.json',report)
    print(json.dumps({'status':'PASS','checks':len(rows)}),flush=True)

def chunk(job):
    kind,cond,start,stop=job
    if kind=='reference':return {'values':np.stack([c.reference(cond,i) for i in range(start,stop)])}
    values=[c.outer(cond,i) for i in range(start,stop)]
    return {k:np.stack([v[k] for v in values]) for k in values[0]}

def run(workers):
    pin=pins();pre=json.loads((HERE/'preflight.json').read_text())
    assert pre['status']=='PASS' and pre['pins']==pin
    out=HERE/'run';out.mkdir(exist_ok=True)
    freeze=out/'freeze.json'
    if freeze.exists():assert json.loads(freeze.read_text())['pins']==pin
    else:write(freeze,{'pins':pin,'M':1000,'B':999,'reference_n':32768,'conditions':c.conditions(),
                      'rng_root':c.ROOT,'platform':platform.platform(),'python':sys.executable,
                      'numpy':np.__version__,'scipy':scipy.__version__,'storage':'E: SATA HDD','workers':workers})
    jobs=[]
    for cond in c.conditions():
        specifications=[('outer',1000,25)]+([] if cond['exact_zero'] else [('reference',32768,1024)])
        for kind,total,size in specifications:
            folder=out/cond['id']/kind;folder.mkdir(parents=True,exist_ok=True)
            for start in range(0,total,size):
                dst=folder/f'{start:06d}.npz';receipt=dst.with_suffix('.json')
                if receipt.exists():assert sha(dst)==json.loads(receipt.read_text())['sha256'];continue
                assert not dst.exists(),'Uncommitted chunk requires technical recovery'
                jobs.append(((kind,cond,start,min(start+size,total)),dst))
    started=time.perf_counter();done_count=0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        iterator=iter(jobs);pending={}
        def submit():
            try:job,dst=next(iterator)
            except StopIteration:return
            pending[pool.submit(chunk,job)]=(job,dst)
        for _ in range(workers):submit()
        while pending:
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                job,dst=pending.pop(future);data=future.result()
                with dst.open('xb') as f:np.savez_compressed(f,**data)
                write(dst.with_suffix('.json'),{'kind':job[0],'condition':job[1]['id'],'start':job[2],'stop':job[3],'sha256':sha(dst)})
                done_count+=1
                if done_count%8==0:
                    print(json.dumps({'chunks_complete_this_run':done_count,'chunks_planned_this_run':len(jobs),'elapsed_seconds':round(time.perf_counter()-started,1)}),flush=True)
                submit()
    assert pins()==pin
    if not (out/'completion.json').exists():
        write(out/'completion.json',{'status':'COMPLETE','outer_datasets':8000,'reference_datasets':7*32768,
                                     'elapsed_this_run_seconds':time.perf_counter()-started,'pins':pin,'new_model_calls':0})
    print('SCIENTIFIC EXECUTION COMPLETE',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['check','run']);parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    if args.action=='check':preflight()
    else:run(args.workers)
