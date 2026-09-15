"""Hash-frozen CPU execution with resumable exclusive scientific chunks."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json,sys,time,platform
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import numpy as np
import ties_core as t
import numerics as n
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False)
def current_pins():return {str(p):sha(p) for p in (HERE/'PROTOCOL.md',HERE/'ties_core.py',HERE/'run_ties.py',HERE.parent/'numerics.py')}
def checks():
    sys.path.insert(0,str(HERE/'validation_sources'));import multipair_core_v1 as old;import revision_core_v1 as prev
    report=[]
    def ok(name):report.append({'check':name,'pass':True})
    c=prev.conditions()[7];d=prev.generator(c,40,[91551,901]);e=prev.generator(c,120,[91551,902])
    def flat(x):return n.Data(x.y.ravel(),np.repeat(np.arange(x.groups),3),x.groups,x.joint.reshape(-1,3),x.late.reshape(-1,3),np.ones((x.y.size,3),bool),np.ones((x.y.size,3),bool))
    dd,ee=flat(d),flat(e);r=np.random.default_rng(20260915)
    md=r.multinomial(40,np.full(40,1/40),size=37);me=r.multinomial(120,np.full(120,1/120),size=37)
    f=n.Plan(dd,both_labels=True).fit(md);fo=old.CalibrationPlan(d).fit(md);np.testing.assert_array_equal(f,fo)
    np.testing.assert_allclose(n.rates(ee,f,me),old.weighted_rates(e,fo,me),rtol=0,atol=2e-15,equal_nan=True)
    pt=n.Plan(dd,both_labels=True).fit(np.ones(40,int))[0];p=n.interaction(n.rates(ee,pt,np.ones(120,int))[0])
    bounds,se=n.sandwich(ee,pt,p);op=old.contrasts(old.weighted_rates(e,pt,np.ones(120,int))[0]);bo,so=old.sandwich(e,pt,op)
    np.testing.assert_allclose(bounds,bo[4],rtol=0,atol=2e-15);np.testing.assert_allclose(se,so[4],rtol=0,atol=2e-15)
    ok('equal_size_arrays_vs_original_fit_rates_sandwich')
    for cc in t.conditions():
        dd=t.generator(cc,40,10,999991);ff=n.Plan(dd,both_labels=True).fit(md)
        for k in range(5):
            vals=[]
            for ss in (dd.joint,dd.late):
                for cols in ([0,1,2],[0],[1],[2]):vals.append(old.threshold(ss[:,cols],dd.y,md[k,dd.g],np.ones_like(ss[:,cols],bool))['threshold'])
            np.testing.assert_array_equal(ff[k],vals)
        if cc['quantized']:
            assert np.all(ff/.5==np.floor(ff/.5))
            f0=ff[0];np.testing.assert_allclose(t.oracle(cc,f0),t.oracle(dict(cc,quantized=False),f0),rtol=0,atol=0)
        if cc['kind']=='N':
            ident=t.generator(cc,40,10,999992,lam=1.)
            np.testing.assert_array_equal(ident.joint,ident.late)
            fit=n.Plan(ident,both_labels=True).fit(np.ones(40,int))[0]
            np.testing.assert_array_equal(n.interaction(n.rates(ident,fit,np.ones(40,int))[0]),np.zeros(2))
    ok('eight_laws_weighted_tied_knots_and_lambda1_identity')
    # Direct ragged sandwich and ratio checks on a fixed excluded fixture.
    cc=t.conditions()[-1];d=t.generator(cc,40,10,999993);e=t.generator(cc,120,20,999993)
    f=n.Plan(d,both_labels=True).fit(np.ones(40,int))[0];pred=n.predictions(e,f)[0].mean(axis=-1);rates=[]
    for y in (0,1):rates.append(pred[e.y==y].mean(axis=0))
    np.testing.assert_allclose(n.rates(e,f,np.ones(120,int))[0],np.array(rates).T,rtol=0,atol=2e-15)
    p=n.interaction(np.array(rates).T);b,se=n.sandwich(e,f,p)
    z=(pred[:,1]-pred[:,3])-(pred[:,0]-pred[:,2])
    for y in (0,1):
        sums=np.array([[np.sum((e.g==g)&(e.y==y)),np.sum(z[(e.g==g)&(e.y==y)])] for g in range(120)])
        psi=(sums[:,1]-sums[:,0]*p[y])/sums[:,0].mean()
        np.testing.assert_allclose(se[y],np.sqrt(np.sum(psi**2)/(120*119)),rtol=0,atol=2e-15)
    ok('unequal_group_ratio_sandwich_direct_sums')
    # Quantized survival includes equality and rounds off-grid cutoffs upward.
    x=np.array([-.50001,-.5,-.00001,0.,.49999,.5,1.]);qx=.5*np.floor(x/.5)
    for cutoff in [-.5,-.3,0.,.2,.5]:np.testing.assert_array_equal(qx>=cutoff,x>=.5*np.ceil(cutoff/.5))
    ok('quantizer_inclusive_boundary_and_offgrid_cutoff')
    probe=t.outer(cc,999999,999)
    np.testing.assert_allclose(probe['intervals'][1,:,1]-probe['intervals'][1,:,0],probe['intervals'][2,:,1]-probe['intervals'][2,:,0],rtol=0,atol=1e-14)
    np.testing.assert_allclose(probe['intervals'][1].mean(axis=-1)+probe['intervals'][2].mean(axis=-1),2*probe['point'],rtol=0,atol=1e-14)
    ok('full_excluded_B999_probe_and_center_identities')
    dump(HERE/'preflight.json',{'status':'PASS','checks':report,'excluded_indices':[999991,999992,999993,999999],'pins':current_pins()})
    print('PREFLIGHT PASS',len(report),flush=True)
def chunk(job):
    kind,c,start,stop=job
    if kind=='reference':return {'values':np.stack([t.reference(c,i) for i in range(start,stop)])}
    rows=[t.outer(c,i) for i in range(start,stop)]
    return {k:np.stack([r[k] for r in rows]) for k in rows[0]}
def run():
    pins=current_pins();pre=json.loads((HERE/'preflight.json').read_text());assert pre['status']=='PASS' and pre['pins']==pins
    out=HERE/'run';out.mkdir(exist_ok=True);freeze=out/'freeze.json'
    if freeze.exists():assert json.loads(freeze.read_text())['pins']==pins
    else:dump(freeze,{'pins':pins,'M':1000,'B':999,'R_alternative':65536,'conditions':t.conditions(),'namespace':list(t.ROOT),'python':sys.executable,'storage':'E: SATA HDD','platform':platform.platform(),'size_subdomain':77})
    jobs=[]
    for c in t.conditions():
        for kind,total,step in [('outer',1000,25)]+([('reference',65536,1024)] if c['kind']=='A' else []):
            folder=out/c['id']/kind;folder.mkdir(parents=True,exist_ok=True)
            for start in range(0,total,step):
                dest=folder/f'{start:06d}.npz';receipt=dest.with_suffix('.json')
                if receipt.exists():
                    r=json.loads(receipt.read_text());assert sha(dest)==r['sha256'];continue
                assert not dest.exists(),'Uncommitted chunk requires explicit technical recovery'
                jobs.append(((kind,c,start,min(start+step,total)),dest))
    startclock=time.perf_counter();finished=0
    # Keep four jobs in flight; do not retain hundreds of large result arrays.
    with ProcessPoolExecutor(max_workers=4) as pool:
        iterator=iter(jobs);pending={}
        def submit():
            try:job,dest=next(iterator)
            except StopIteration:return False
            pending[pool.submit(chunk,job)]=(job,dest);return True
        for _ in range(4):submit()
        while pending:
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for fut in done:
                job,dest=pending.pop(fut);arr=fut.result()
                with dest.open('xb') as f:np.savez_compressed(f,**arr)
                dump(dest.with_suffix('.json'),{'sha256':sha(dest),'start':job[2],'stop':job[3],'kind':job[0],'condition':job[1]['id']})
                finished+=1
                if finished%16==0:print(json.dumps({'completed_this_run':finished,'planned_this_run':len(jobs),'elapsed_seconds':round(time.perf_counter()-startclock,1)}),flush=True)
                submit()
    assert current_pins()==pins
    if not (out/'completion.json').exists():dump(out/'completion.json',{'status':'COMPLETE','outer_datasets':8000,'alternative_reference_datasets':262144,'elapsed_this_run_seconds':time.perf_counter()-startclock,'new_model_calls':0,'pins':pins})
    print('ALL SCIENTIFIC CHUNKS COMPLETE',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['check','run']);args=p.parse_args();checks() if args.action=='check' else run()
