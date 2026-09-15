"""Path-independent numeric replay for review v4; no model or network calls.

Preserved production scripts are adapted in memory only for input/output roots.
The permitted exact substitutions are recorded in the completion receipt.
"""
from pathlib import Path
import argparse, contextlib, hashlib, importlib.util, io, json, os, sys, time
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
REL=Path('amendments/review-response-20260915-v1')
SIM=ROOT/REL/'simulation'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def inside(path,root):return path==root or path.is_relative_to(root)
def load(path,name):
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    out=args.output.resolve();assert not out.exists() and not inside(out,ROOT),'Use a new output directory outside the package.'
    out.mkdir(parents=True);began=time.perf_counter();reads=set();denied=[];checks=[];adaptations=[]
    runtime=Path(sys.executable).resolve().parent;windows=Path(os.environ.get('SystemRoot','C:/Windows')).resolve()
    def guard(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system'):raise PermissionError('Replay forbids network and subprocesses')
        if event not in ('open','os.listdir','os.scandir'):return
        v=args[0]
        if v is None or isinstance(v,int):return
        p=Path(os.fsdecode(v)).resolve()
        writing=event=='open' and ((isinstance(args[1],str) and any(c in args[1] for c in 'wax+')) or (len(args)>2 and isinstance(args[2],int) and bool(args[2]&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))))
        allowed=inside(p,out) if writing else any(inside(p,r) for r in (ROOT,out,runtime,windows))
        if not allowed:
            denied.append({'path':str(p),'writing':writing});raise PermissionError('Outside numeric replay roots: '+str(p))
        if not writing:reads.add(str(p))
    sys.addaudithook(guard)
    manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    for rel,h in manifest['sha256'].items():assert sha(ROOT/rel)==h,rel
    print('Manifest verified',len(manifest['sha256']),flush=True)
    sys.path.insert(0,str(SIM))
    import numpy as np
    import scipy
    import review_core as c
    import numerics as n
    def compare(x,y,label,tol=0):
        assert x.shape==y.shape,(label,x.shape,y.shape)
        assert np.array_equal(np.isfinite(x),np.isfinite(y)),label
        exact=np.array_equal(x,y,equal_nan=True)
        valid=np.isfinite(x)&np.isfinite(y)
        delta=float(np.max(np.abs(x[valid].astype(float)-y[valid].astype(float)))) if valid.any() else 0.
        if tol:np.testing.assert_allclose(x,y,rtol=0,atol=tol,equal_nan=True,err_msg=label)
        else:assert exact,label
        checks.append({'item':label,'exact':exact,'maximum_absolute_difference':delta,'tolerance':tol})
    def patched(path,name,replacements):
        text=path.read_text(encoding='utf-8-sig')
        for old,new in replacements:
            assert text.count(old)==1,(path,old,text.count(old));text=text.replace(old,new)
            adaptations.append({'source':str(path.relative_to(ROOT)),'replace':old,'with':new})
        env={'__file__':str(path),'__name__':name}
        capture=io.StringIO()
        with contextlib.redirect_stdout(capture):exec(compile(text,str(path),'exec'),env)
        (out/(name+'-stdout.txt')).write_text(capture.getvalue(),encoding='utf-8')
        return env

    # All eight condition summaries and all saved reference contrasts.
    patched(SIM/'summarize_review_v2.py','simulation_summary',[("OUT=HERE/'summary-v2'",'OUT=Path('+repr(str(out/'simulation-summary-v2'))+')')])
    for p in sorted((SIM/'summary-v2').glob('*.csv')):
        q=out/'simulation-summary-v2'/p.name;assert p.read_bytes()==q.read_bytes();checks.append({'item':'simulation-summary-v2/'+p.name,'exact':True})
    for p in sorted((SIM/'summary-v2').glob('*-first-outer.npz')):
        with np.load(p) as x,np.load(out/'simulation-summary-v2'/p.name) as y:
            for k in x.files:compare(x[k],y[k],p.name+'/'+k)
    print('All 8000 saved outer records and 229376 reference records summarized',flush=True)

    # Regenerate a bounded set of science, rather than repeat the full run.
    for cond in c.conditions():
        original_file=SIM/'run'/cond['id']/'outer/000000.npz'
        with np.load(original_file) as z:old={k:z[k][0] for k in z.files}
        regenerated=c.outer(cond,0,999)
        for k,x in old.items():compare(x,regenerated[k],'regenerated/'+cond['id']+'/'+k,tol=2e-13)
        if not cond['exact_zero']:
            with np.load(SIM/'run'/cond['id']/'reference/000000.npz') as z:rv=z['values']
            for index in (0,1,1023):compare(rv[index],c.reference(cond,index),'reference/'+cond['id']+'/'+str(index),tol=2e-13)
        d=c.generator(cond,40,10,900001);plan=n.Plan(d,both_labels=True);fit=plan.fit(np.ones(40,int))[0]
        for j,score in enumerate((d.joint,d.late)):
            for k,cols in enumerate(([0,1,2],[0],[1],[2])):
                values=score[d.y==1][:,cols].ravel();expected=max(v for v in np.unique(values) if np.mean(values>=v)+1e-12>=.9)
                assert fit[j*4+k]==expected
        if cond['separation']==0:np.testing.assert_allclose(c.population_auc(cond),.5,rtol=0,atol=1e-14)
        checks.append({'item':'core-threshold-population-AUC/'+cond['id'],'pass':True})
    print('Regenerated 8 complete outer records and 21 reference contributions',flush=True)

    # Empirical audit: change two root assignments, preserving all calculations.
    (out/'empirical').mkdir()
    patched(ROOT/REL/'empirical/audit_empirical.py','empirical_audit',[
        ('OUT = Path(__file__).resolve().parent','OUT = Path('+repr(str(out/'empirical'))+')'),
        ('STUDY = OUT.parents[2]','STUDY = Path('+repr(str(ROOT))+')')])
    for p in sorted((ROOT/REL/'empirical').glob('*.csv')):
        q=out/'empirical'/p.name;assert p.read_bytes()==q.read_bytes(),p.name;checks.append({'item':'empirical/'+p.name,'exact':True})
    assert json.loads((out/'empirical/audit-results.json').read_text())['status']=='PASS'
    print('All empirical audit CSVs reproduced',flush=True)

    # The finite-B check reuses its original 1000 outer datasets and saved prefix.
    tailout=out/'finite-B-summary'
    patched(SIM/'summarize_tail_check_v2.py','finite_B_summary',[
        ("OUT=ROOT/'summary'",'OUT=Path('+repr(str(tailout))+')')])
    for p in sorted((SIM/'tail-check-v2/summary').glob('*.csv')):
        assert p.read_bytes()==(tailout/p.name).read_bytes();checks.append({'item':'finite-B/'+p.name,'exact':True})
    tailvalid=json.loads((tailout/'validation.json').read_text());assert tailvalid['status']=='PASS'
    tail=load(SIM/'run_tail_check_v2.py','tail_run_portable')
    with np.load(SIM/'run/H065_Q125/outer/000000.npz') as z:old={k:z[k][0] for k in z.files}
    regenerated=tail.extend(old,0)
    with np.load(SIM/'tail-check-v2/000000.npz') as z:
        for k in z.files:compare(z[k][0],regenerated[k],'finite-B-first-outer/'+k,tol=2e-13)
    print('Finite-B summary verified; first extended outer record regenerated',flush=True)
    for rel,h in manifest['sha256'].items():assert sha(ROOT/rel)==h,rel
    receipt=dict(status='PASS',checks=checks,comparisons=len(checks),
        independent_finite_B_endpoint_checks=tailvalid['checks'],elapsed_seconds=time.perf_counter()-began,
        python=sys.executable,numpy=np.__version__,scipy=scipy.__version__,new_model_calls=0,
        preserved_scientific_source=True,adaptations=adaptations,
        scope={'saved_outer_records_summarized':8000,'saved_reference_records_summarized':7*32768,
               'complete_outer_records_regenerated':8,'reference_contributions_regenerated':21,
               'finite_B_reused_outer_records_summarized':1000,'finite_B_extended_outer_records_regenerated':1,
               'empirical_csvs_recomputed':len(list((ROOT/REL/'empirical').glob('*.csv'))),
               'baseline_v3_embedded_unchanged_but_not_rerun_here':True},
        audit_guard='Python audit hook; not an OS/native-library sandbox or independent researcher reproduction',
        successful_reads_outside_package_output_runtime_windows=0,denied=denied,successful_read_paths=sorted(reads))
    (out/'completion.json').write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','comparisons':len(checks),'elapsed_seconds':receipt['elapsed_seconds']}),flush=True)
if __name__=='__main__':main()
