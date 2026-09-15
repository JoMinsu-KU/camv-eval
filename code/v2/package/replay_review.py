"""Self-contained numerical reviewer replay. Requires only a fresh output path."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,sys,time
ROOT=Path(__file__).resolve().parent
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
sys.dont_write_bytecode=True
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readj(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def writej(p,x):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')
def load(p,name):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 out=args.output.resolve()
 if out.exists() or out.is_relative_to(ROOT):raise ValueError('Output must be a fresh directory outside the immutable package')
 out.mkdir(parents=True,exist_ok=False);os.environ['MPLCONFIGDIR']=str(out/'mplconfig');os.environ['MPLBACKEND']='Agg'
 manifest=readj(ROOT/'review-manifest.json')
 for rel,h in manifest['files_sha256'].items():
  p=(ROOT/rel).resolve()
  if not p.is_relative_to(ROOT) or sha(p)!=h:raise ValueError('Package input hash mismatch: '+rel)
 loader=load(ROOT/'src/original_v6_replay.py','review_v6_loader');loader.ROOT=ROOT
 audit=loader.Audit(out);sys.addaudithook(audit.hook)
 begun=time.perf_counter();audit.phase='compute';sys.path.insert(0,str(ROOT/'src'))
 import numpy as np
 import empirical_core_v2 as core
 from run_empirical_v2 import run_case
 import portable_adapters as adapters
 spec=readj(ROOT/'data/case-manifest.json');assert len(spec['cases'])==16
 data={k:loader.load_collection(v) for k,v in spec['collections'].items()};frozen={}
 for r in readj(ROOT/'data/frozen_calibration.json')['thresholds']:
  mapping={'joint':'joint','late_meanlogodds':'late','single':'single'}
  if r['ablation']=='native' and r['calibration_family'] in mapping:frozen.setdefault((r['model_id'],r['seed']),{})[mapping[r['calibration_family']]]=r['threshold']
 checks=[];case_keys=set()
 for case in spec['cases']:
  assert case['key'] not in case_keys;case_keys.add(case['key']);ds,ts=adapters.cohorts(case,data,core)
  dest=out/'empirical'/case['key'];dest.parent.mkdir(parents=True,exist_ok=True)
  run_case(ds,ts,case['case_id'],dest,2000,frozen if case['axis']=='historical' else {},case['rng_namespace'])
  audit.phase='comparison';ref=ROOT/case['reference']
  for f in ref.glob('*.csv'):checks.append({'case':case['key'],'file':f.name,'kind':'csv_byte_identical','pass':sha(f)==sha(dest/f.name)})
  checks.append({'case':case['key'],'file':'point-fits.json','kind':'json_byte_identical','pass':sha(ref/'point-fits.json')==sha(dest/'point-fits.json')})
  catalog=readj(ROOT/'reference/empirical-array-digests.json')[case['reference']+'/bootstrap-arrays.npz']
  with np.load(dest/'bootstrap-arrays.npz',allow_pickle=False) as z:
   assert z.files==[r['array'] for r in catalog]
   for r in catalog:
    a=z[r['array']];ok=list(a.shape)==r['shape'] and str(a.dtype)==r['dtype'] and hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()==r['c_order_bytes_sha256']
    checks.append({'case':case['key'],'array':r['array'],'kind':'decoded_array_hash_identical','pass':bool(ok)})
  audit.phase='compute'
 adapters.run_transfer(out/'transfer',spec,data,frozen,core,out/'empirical')
 audit.phase='comparison'
 for f in (ROOT/'reference/transfer').rglob('*.csv'):
  rel=f.relative_to(ROOT/'reference/transfer');checks.append({'case':'transfer','file':str(rel),'kind':'csv_byte_identical','pass':sha(f)==sha(out/'transfer'/rel)})
 audit.phase='compute';adapters.run_scorer(out/'scorer');audit.phase='comparison'
 for f in (ROOT/'reference/scorer').glob('*.csv'):
  checks.append({'case':'scorer','file':f.name,'kind':'csv_byte_identical','pass':sha(f)==sha(out/'scorer'/f.name)})
 audit.phase='compute';adapters.run_centering(out/'centering');audit.phase='comparison'
 import pandas as pd
 x=pd.read_csv(ROOT/'centering/centering-summary.csv');y=pd.read_csv(out/'centering/centering-summary.csv')
 assert x.shape==y.shape and list(x.columns)==list(y.columns)
 for k in x:
  ok=np.allclose(x[k],y[k],rtol=1e-12,atol=1e-12,equal_nan=True) if np.issubdtype(x[k].dtype,np.number) else x[k].equals(y[k])
  checks.append({'case':'centering','field':k,'kind':'saved_outer_summary_tolerance_1e-12','pass':bool(ok)})
 audit.phase='compute';sim=load(ROOT/'simulation/summarize_revision_v1.py','review_simulation_summary')
 sim.summarize(ROOT/'simulation/compact-v1',out/'simulation',figures=True)
 audit.phase='comparison'
 for f in (ROOT/'reference/simulation').glob('*.csv'):
  checks.append({'case':'simulation','file':f.name,'kind':'csv_byte_identical','pass':sha(f)==sha(out/'simulation'/f.name)})
 audit.phase='closure'
 for rel,h in manifest['files_sha256'].items():assert sha(ROOT/rel)==h,('Package modified',rel)
 passed=all(c['pass'] for c in checks)
 writej(out/'comparison-receipt.json',{'status':'PASS' if passed else 'DIFFERENCES','checks':checks,'check_count':len(checks)})
 writej(out/'file-access-audit.json',audit.receipt())
 writej(out/'completion.json',{'status':'COMPLETE' if passed else 'COMPLETE_WITH_DIFFERENCES','empirical_cases':16,'empirical_B':2000,'new_transfer_cases':4,'transfer_B':2000,
  'scorer_replayed':'All 1,536 stored score records and exact positive-knot/rank/distribution/decision analysis; projected raw-score lineage verified.',
  'original_simulation_replayed':'All 20,000 retained outer/metric centering rows summarized; no inner-draw or oracle regeneration.',
  'revision_simulation_replayed':'All 12,000 saved outer repetitions summarized; no inner-draw or oracle regeneration.',
  'inference_calls':0,'package_sha256':sha(ROOT/'review-manifest.json'),'all_package_hashes_preserved':True,'check_count':len(checks),'elapsed_seconds':time.perf_counter()-begun,
  'environment':{'python':sys.version,'executable':sys.executable,'numpy':np.__version__,'storage_note':'Host supplied output path; local verification on E: SATA HDD'},
  'isolation_limit':'Python file-access audit, not a fresh OS/kernel sandbox or an external researcher reproduction.'})
 print(json.dumps({'status':'PASS' if passed else 'DIFFERENCES','checks':len(checks),'elapsed_seconds':time.perf_counter()-begun}),flush=True)
 return 0 if passed else 2
if __name__=='__main__':raise SystemExit(main())
