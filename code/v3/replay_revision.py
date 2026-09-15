"""Portable replay of the Sept15 additions; no original workspace or model calls."""
from pathlib import Path
import os,sys
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
sys.dont_write_bytecode=True
import argparse,hashlib,importlib.util,json,time
ROOT=Path(__file__).resolve().parent
REL=Path('amendments/score-ties-revision-20260915-v1')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def inside(p,r):return p==r or p.is_relative_to(r)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output.resolve()
    assert not out.exists() and not inside(out,ROOT),'Use a new output directory outside the package'
    out.mkdir(parents=True);started=time.perf_counter();denied=[];reads=set()
    runtime=Path(sys.executable).resolve().parent;windows=Path(os.environ.get('SystemRoot','C:/Windows')).resolve()
    def audit(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system'):raise PermissionError('Replay has no network or subprocess')
        if event not in ('open','os.listdir','os.scandir'):return
        val=args[0]
        if val is None or isinstance(val,int):return
        p=Path(os.fsdecode(val)).resolve()
        writing=event=='open' and ((isinstance(args[1],str) and any(c in args[1] for c in 'wax+')) or (len(args)>2 and isinstance(args[2],int) and bool(args[2]&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))))
        allowed=inside(p,out) if writing else any(inside(p,r) for r in (ROOT,out,runtime,windows))
        if not allowed:
            denied.append({'path':str(p),'write':writing});raise PermissionError('Outside portable replay roots: '+str(p))
        if not writing:reads.add(str(p))
    sys.addaudithook(audit)
    manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
    for rel,h in manifest['sha256'].items():assert sha(ROOT/rel)==h,rel
    sys.path.insert(0,str(ROOT/REL));sys.path.insert(0,str(ROOT/REL/'simulation'))
    import numpy as np
    scorer=load(ROOT/REL/'scorer/run_sensitivity.py','revision_scorer_portable')
    ordinary_read=scorer.read
    def relocated_read(p):
        data=ordinary_read(p)
        if Path(p).name=='preparation.json':
            remap={}
            for old,h in data['pins'].items():
                rel=old.replace('\\','/').split('/camv-eval-study-v1/',1)[1]
                remap[str(ROOT/rel)]=h
            data=dict(data,pins=remap)
        return data
    scorer.read=relocated_read
    scorer.run(out/'scorer')
    sim=load(ROOT/REL/'simulation/summarize_ties.py','revision_simulation_portable');sim.summarize(out/'simulation',replay=True)
    checks=[]
    for kind,sub in [('scorer','results-v1'),('simulation','summary-v1')]:
        for p in sorted((ROOT/REL/kind/sub).glob('*.csv')):
            q=out/kind/p.name;assert p.read_bytes()==q.read_bytes();checks.append({'file':kind+'/'+p.name,'exact':True})
    for d in sorted((ROOT/REL/'scorer/results-v1').glob('smolvlm*')):
        with np.load(d/'paired-bootstrap.npz') as x,np.load(out/'scorer'/d.name/'paired-bootstrap.npz') as y:
            for key in x.files:assert np.array_equal(x[key],y[key],equal_nan=True);checks.append({'case':d.name,'array':key,'exact':True})
    for p in sorted((ROOT/REL/'simulation/summary-v1').glob('*-compact.npz')):
        with np.load(p) as x,np.load(out/'simulation'/p.name) as y:
            for key in x.files:assert np.array_equal(x[key],y[key],equal_nan=True);checks.append({'file':p.name,'array':key,'exact':True})
    for rel,h in manifest['sha256'].items():assert sha(ROOT/rel)==h
    receipt={'status':'PASS','comparisons':len(checks),'checks':checks,'elapsed_seconds':time.perf_counter()-started,'python':sys.executable,'new_model_calls':0,'storage':'E: SATA HDD','guard':'Python audit hook, not OS-level isolation; installed before numeric imports','successful_reads_outside_package_output_runtime_windows':0,'denied':denied,'successful_read_paths':sorted(reads),'scope':'All four scorer recalibrations at B2000; all 8000 saved simulation summaries and first outer dataset regenerated per cell. Reference integrals summarized from saved 262144 contrasts, not regenerated.'}
    with (out/'completion.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    print(json.dumps({k:receipt[k] for k in ('status','comparisons','elapsed_seconds','new_model_calls')}),flush=True)
if __name__=='__main__':main()
