"""Portable, score-to-table numerical reproduction; no model or image dependencies."""
from pathlib import Path
import argparse, collections, csv, gzip, hashlib, json, math, os, sys, time
ROOT=Path(__file__).resolve().parent
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
 os.environ[key]='1'
sys.dont_write_bytecode=True
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def readj(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def writej(p,v):
 with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')
def require(v,why):
 if not v:raise ValueError(why)
def inside(p,r):return p==r or p.is_relative_to(r)
class Audit:
 """Runtime Python file-access policy; not an OS/kernel sandbox claim."""
 def __init__(self,out):
  self.out=out;self.phase='startup';self.counts=collections.Counter();self.reads=set();self.denied=[]
  self.runtime=Path(sys.executable).resolve().parent;self.system=Path(os.environ.get('SystemRoot','C:/Windows')).resolve()
 def hook(self,event,args):
  if event in ('subprocess.Popen','os.system','socket.connect','socket.bind'):raise PermissionError('No network or subprocess in baseline replay')
  if event not in ('open','os.listdir','os.scandir'):return
  value=args[0]
  if isinstance(value,int) or value is None:return
  p=Path(os.fsdecode(value)).resolve()
  write=event=='open' and ((isinstance(args[1],str) and any(c in args[1] for c in 'wax+')) or (len(args)>2 and isinstance(args[2],int) and bool(args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))))
  allowed=inside(p,self.out) if write else any(inside(p,r) for r in (ROOT,self.out,self.runtime,self.system))
  # During score fitting, expected tables/arrays cannot be read even accidentally.
  if not write and self.phase=='compute' and inside(p,ROOT/'reference'):allowed=False
  if not allowed:
   self.denied.append({'event':event,'path':str(p),'write':bool(write),'phase':self.phase})
   raise PermissionError('Portable replay file policy rejected '+str(p))
  self.counts[(self.phase,event,'write' if write else 'read')]+=1
  if not write:self.reads.add(str(p))
 def receipt(self):return {'policy':'Python audit hook; installed before numerical imports; existing interpreter startup and OS-native library reads are not a fresh-OS isolation proof','allowed_read_roots':[str(ROOT),str(self.out),str(self.runtime),str(self.system)],'allowed_write_root':str(self.out),'denied':self.denied,'counts':[{'phase':p,'event':e,'mode':m,'count':n} for (p,e,m),n in sorted(self.counts.items())],'successful_read_paths':sorted(self.reads),'original_study_or_parent_successful_reads':0}
def load_collection(spec):
 metadata={};group_members={}
 with (ROOT/spec['metadata']).open(encoding='utf-8-sig') as f:
  for text in f:
   m=json.loads(text);sid=m['sample_id'];require(sid not in metadata,'Duplicate sample metadata')
   require(type(m['label']) is int and m['label'] in (0,1),'Nonbinary label')
   require(m['cameras']==(['c0','c1','c2','c3'] if m['dataset']=='rlbenchfail' else ['c0','c1','c2']),'Camera axis')
   require(m['split'] in ({'dev','confirmation'} if m['dataset'] in ('rlbenchfail','reassemble') else {'external'}),'Split axis')
   require(isinstance(m['task_family'],str) and isinstance(m['group_id'],str),'Missing grouping')
   group=m['group_id'];pair=(m['dataset'],m['split'])
   require(group not in group_members or group_members[group]==pair,'Cross-split group')
   metadata[sid]=m;group_members[group]=pair
 rows=[];seen=set();requests=set();models=collections.defaultdict(set);counts=collections.Counter()
 with gzip.open(ROOT/spec['scores'],'rt',encoding='utf-8') as f:
  for text in f:
   r=json.loads(text);sid=r['sample_id'];require(sid in metadata,'Score without metadata');m=metadata[sid]
   require(type(r['available']) is bool,'Availability not boolean');require(r['ablation']=='native','Non-native observation')
   require(type(r['seed']) is int,'Seed type');models[r['model_id']].add(r['seed'])
   if 'input_hash' in m:require(r['input_hash']==m['input_hash'],'Input-hash drift')
   cameras=r['cameras'];method=r['method_id'];require(method in ('single','joint','late_meanlogodds','best_camera'),'Unsupported score method')
   require(len(cameras)==(1 if method in ('single','best_camera') else 2) and len(cameras)==len(set(cameras)) and set(cameras)<=set(m['cameras']),'Routing camera mismatch')
   if method=='late_meanlogodds':require(cameras==sorted(cameras),'Stored Late orientation')
   key=(r['model_id'],r['seed'],sid,method,tuple(cameras));require(key not in seen,'Duplicate score');seen.add(key)
   if r.get('request_id'):
    require(r['request_id'] not in requests,'Duplicate request ID');requests.add(r['request_id'])
   if r['available']:
    require(type(r.get('score')) in (int,float) and math.isfinite(r['score']),'Nonfinite available score')
    require((method=='late_meanlogodds' and r.get('logodds') is None) or (type(r.get('logodds')) in (int,float) and math.isfinite(r['logodds'])),'Nonfinite native logodds; only historical stored-Late null is allowed')
    require(0<=r['score']<=1,'Out-of-range score')
   else:
    require(bool(r.get('status')),'Missing failure category')
    # Failure is preserved as operational rejection. No imputation of a finite score.
   counts[r.get('status','UNDECLARED')]+=1
   rows.append(dict(r,**{k:m[k] for k in ('dataset','split','group_id','label','task_family')}))
 require(len(rows)==spec['score_rows'] and len(metadata)==spec['samples'],'Collection census drift')
 require(dict(counts)==spec['status_counts'],'Availability category drift')
 import itertools
 for model,seeds in models.items():
  for seed in seeds:
   for sid,m in metadata.items():
    for camera in m['cameras']:require((model,seed,sid,'single',(camera,)) in seen,'Missing Single row')
    for pair in itertools.permutations(m['cameras'],2):require((model,seed,sid,'joint',pair) in seen,'Missing Joint row')
 return rows
def compare_csv(a,b):
 # Frozen CSV serialization is deterministic; exact text also checks headers,
 # identifiers, null positions, all reported scalar fields and row order.
 return {'kind':'csv_exact','pass':sha(a)==sha(b),'original_sha256':sha(a),'replayed_sha256':sha(b)}
def compare_case(output,case,np):
 ref=ROOT/case['reference'];result=[]
 for name in ('operating-by-seed.csv','pair-operating-by-seed.csv','task-operating-by-seed.csv','order-by-seed.csv','operating-summary.csv','contrasts.csv','classification-diagnostics.csv','point-fits.json'):
  item=compare_csv(ref/name,output/name);item.update(file=name);result.append(item)
 with np.load(ref/'bootstrap-arrays.npz',allow_pickle=False) as a,np.load(output/'bootstrap-arrays.npz',allow_pickle=False) as b:
  require(a.files==b.files,'NPZ key/order changed')
  for key in a.files:
   x,y=a[key],b[key];same=x.shape==y.shape and x.dtype==y.dtype and np.array_equal(x,y,equal_nan=True)
   d=float(np.nanmax(np.abs(x-y))) if x.shape==y.shape and np.issubdtype(x.dtype,np.number) and np.any(np.isfinite(x)&np.isfinite(y)) else None
   result.append({'file':'bootstrap-arrays.npz','array':key,'kind':'decoded_array_exact','pass':bool(same),'shape':list(x.shape),'dtype':str(x.dtype),'max_abs_difference':d})
 original=readj(ref/'metadata.json');replayed=readj(output/'metadata.json')
 ignore={'elapsed_seconds'};require(set(original)==set(replayed),'Metadata keys changed')
 for key in sorted(set(original)-ignore):result.append({'file':'metadata.json','field':key,'kind':'metadata_exact','pass':original[key]==replayed[key]})
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--manifest-sha256',required=True)
 args=p.parse_args();out=args.output.resolve();require(not out.exists(),'Output exists; no overwrite/retry')
 require(not inside(out,ROOT),'Replay output must be outside immutable package')
 out.mkdir(parents=True,exist_ok=False);audit=Audit(out);sys.addaudithook(audit.hook)
 begun=time.time();success=False
 try:
  manifest=ROOT/'release-manifest.json';require(sha(manifest)==args.manifest_sha256,'Release manifest SHA mismatch');release=readj(manifest)
  for relative,h in release['files_sha256'].items():
   pp=(ROOT/relative).resolve();require(inside(pp,ROOT),'Nonportable manifest member');require(sha(pp)==h,'Release input hash drift: '+relative)
  # One deliberate denied read proves this guard is active; no original content is read.
  audit.phase='guard_fixture'
  try:open('E:/SoftwareX/camv-eval-study-v1/configs/protocol-v1.json','rb')
  except PermissionError:pass
  else:raise AssertionError('Original-workspace guard failed')
  audit.phase='compute';sys.path.insert(0,str(ROOT/'src'))
  import numpy as np
  from empirical_core_v2 import build_cohorts
  from run_empirical_v2 import run_case
  spec=readj(ROOT/'data/case-manifest.json');require(spec['planned_cases']==16 and len(spec['cases'])==16,'Planned-case census')
  collections_data={name:load_collection(v) for name,v in spec['collections'].items()}
  calibration=readj(ROOT/spec['historical_calibration']);frozen={};mapping={'joint':'joint','late_meanlogodds':'late','single':'single'}
  for r in calibration['thresholds']:
   if r['ablation']=='native' and r['calibration_family'] in mapping:frozen.setdefault((r['model_id'],r['seed']),{})[mapping[r['calibration_family']]]=r['threshold']
  results=[];keys=set();case_inputs=[]
  for case in spec['cases']:
   require(case['key'] not in keys,'Duplicate analysis case');keys.add(case['key']);require(case['B']==2000,'B changed')
   ds=[];ts=[]
   for role,dest in (('source',ds),('target',ts)):
    ids=set(case[role+'_samples']);rows=[r for r in collections_data[case[role+'_collection']] if r['model_id']==case['model'] and r['sample_id'] in ids]
    require({r['sample_id'] for r in rows}==ids,'Missing declared case sample')
    cohorts=build_cohorts(rows)
    for seed in case['seeds']:
     c=cohorts[(case['model'],case[role+'_dataset'],case[role+'_split'],seed)]
     require(list(c.samples)==case[role+'_samples'] and list(c.groups)==case[role+'_groups'],'Case grouping/order drift');dest.append(c)
   cp=out/case['key'];cp.parent.mkdir(parents=True,exist_ok=True)
   metadata=run_case(ds,ts,case['case_id'],cp,case['B'],frozen if case['axis']=='historical' else {},case['rng_namespace'])
   audit.phase='comparison';checks=compare_case(cp,case,np);audit.phase='compute'
   results.append({'key':case['key'],'checks':checks,'pass':all(x['pass'] for x in checks),'replay_elapsed_seconds':metadata['elapsed_seconds']})
  audit.phase='closure'
  for relative,h in release['files_sha256'].items():require(sha(ROOT/relative)==h,'Package changed during replay')
  success=all(r['pass'] for r in results)
  writej(out/'comparison-receipt.json',{'status':'PASS' if success else 'NUMERICAL_DIFFERENCES','case_count':len(results),'check_count':sum(len(r['checks']) for r in results),'cases':results})
  writej(out/'environment.json',{'python':sys.version,'executable':sys.executable,'numpy':np.__version__,'storage':'E: SATA HDD','fresh_directory':True,'fresh_OS':False,'fresh_dependency_environment':False,'thread_environment':{k:os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}})
  writej(out/'file-access-audit.json',audit.receipt())
  outputpins={str(pp.relative_to(out)).replace('\\','/'):sha(pp) for pp in sorted(out.rglob('*')) if pp.is_file()}
  writej(out/'completion.json',{'status':'COMPLETE' if success else 'COMPLETE_WITH_NUMERICAL_DIFFERENCES','case_count':len(results),'release_manifest_sha256':args.manifest_sha256,'elapsed_seconds':time.time()-begun,'output_files_sha256':outputpins,'science_scope':'Deterministic score-to-table reproduction, 16 cases at B2000. No model calls, new outcomes, or new scientific draws.','extensions':release['extensions']})
  print(json.dumps({'status':'PASS' if success else 'NUMERICAL_DIFFERENCES','cases':len(results),'elapsed_seconds':time.time()-begun}),flush=True)
 except BaseException as error:
  audit.phase='failed'
  writej(out/'failure.json',{'type':type(error).__name__,'message':str(error),'access':audit.receipt()})
  raise
 return 0 if success else 2
if __name__=='__main__':raise SystemExit(main())
