"""Frozen 12-condition CPU study with chunk resume and explicit root review."""
from __future__ import annotations
import os
from pathlib import Path
HERE=Path(__file__).resolve().parent
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[k]='1'
for name,sub in [('TEMP','runtime'),('TMP','runtime'),('TMPDIR','runtime'),('MPLCONFIGDIR','mplconfig')]:
    (HERE/sub).mkdir(exist_ok=True);os.environ[name]=str(HERE/sub)
import argparse,hashlib,json,math,platform,sys,time,uuid
from datetime import datetime,timezone
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
import importlib.metadata
import numpy as np
import psutil
import revision_core_v1 as core
import multipair_core_v1 as old
from frozen_primitives_v1 import threshold,interval,centered_p

STUDY=Path('E:/SoftwareX/camv-eval-study-v1')
OLD_DIR=STUDY/'staging/p0-e2e-20260914-v1/simulation'
REFERENCE=STUDY/'amendments/p0-e2e-20260914-v1/simulation-run-v1/reference-truth.json'
PRIMARY=Path('E:/SoftwareX/.conda-envs/grasp-vlm/python.exe')
def utc():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok,message):
    if not ok:raise ValueError(message)
def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [clean(v) for v in value]
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value
def encoded(value):return (json.dumps(clean(value),indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
def exclusive_json(path,value):
    with Path(path).open('xb') as f:f.write(encoded(value));f.flush();os.fsync(f.fileno())
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def event(value):
    value={'utc':utc(),**value}
    with (HERE/'run/events.jsonl').open('ab') as f:
        f.write((json.dumps(clean(value),sort_keys=True,allow_nan=False)+'\n').encode());f.flush();os.fsync(f.fileno())
def current_pins():
    paths=[HERE/x for x in ['PROTOCOL.md','revision_core_v1.py','run_revision_v1.py',
        'multipair_core_v1.py','frozen_primitives_v1.py']]
    paths += [OLD_DIR/'multipair_core_v1.py',OLD_DIR/'frozen_primitives_v1.py',REFERENCE]
    return {str(p):sha(p) for p in paths}
def verify(pins):
    for p,h in pins.items():need(sha(p)==h,'Frozen source changed: '+p)
def environment():
    return {'utc':utc(),'python':sys.executable,'version':sys.version,'platform':platform.platform(),
      'storage':'E: SATA HDD','logical_cpus':psutil.cpu_count(),'ram_bytes':psutil.virtual_memory().total,
      'packages':{x:importlib.metadata.version(x) for x in ['numpy','scipy','psutil','matplotlib']},
      'thread_environment':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']},
      'temp':os.environ['TEMP'],'conda_prefix':os.environ.get('CONDA_PREFIX'),'model_inference_requests':0}

def validate_sources():
    for n in ['multipair_core_v1.py','frozen_primitives_v1.py']:
        need(sha(HERE/n)==sha(OLD_DIR/n),'Original copy differs: '+n)
    need(Path(sys.executable).resolve()==PRIMARY.resolve(),'Use existing E: primary Python')
    need(os.environ.get('CONDA_PREFIX','').lower().startswith('e:'),'Run through E: launcher')

def checks():
    validate_sources();checks=[]
    def record(name,**details):checks.append({'name':name,'pass':True,**details})
    scenarios=core.conditions();s=scenarios[3]
    namespace=[20260914,10,4,987654]
    for target in (False,True):
        a=core.generator(s,40,namespace,target);b=old.generator(s,40,namespace,target)
        for key in ['y','cameras','joint']:need(np.array_equal(getattr(a,key),getattr(b,key)),'lambda0 original mismatch')
    record('lambda_zero_exact_original_generator',namespace=namespace)
    identical={**scenarios[0],'lambda_':1.}
    d=core.generator(identical,40,[91431,1]);e=core.generator(identical,120,[91431,2],True)
    need(np.array_equal(d.late,d.joint) and np.array_equal(e.late,e.joint),'lambda1 scores not identical')
    md=np.random.default_rng(456).multinomial(40,np.ones(40)/40,size=31)
    me=np.random.default_rng(789).multinomial(120,np.ones(120)/120,size=31)
    ident=old.analyze_data(identical,d,e,md,me)
    for key in ['point_contrasts','conditional_truth_contrasts']:
        need(np.array_equal(ident[key][[0,1,4]],np.zeros((3,2))),'lambda1 contrast identity')
    for key in ['conditional_policy_draws','refit_policy_draws']:
        c=old.contrasts(ident[key])[:,[0,1,4]];need(np.array_equal(c,np.zeros_like(c)),'lambda1 bootstrap identity')
    record('lambda_one_null_exact_policy_interaction_identity')
    oracle_values=[]
    for ss in scenarios:
        fit=core.oracle_fits(ss);risk=old.oracle(ss,fit)[0]
        need(np.max(np.abs(risk[:,1]-.9))<2e-14,'oracle recall != .9')
        oracle_values.append({'condition':ss['id'],'fits':fit,'rates':risk,'interaction_raw':old.contrasts(risk)[4]})
    record('population_oracle_pooled_root_and_pair_thresholds',maximum_recall_error=max(np.max(np.abs(x['rates'][:,1]-.9)) for x in oracle_values))
    # Fast weighted fits against the source threshold primitive, including zero multiplicities.
    alt=scenarios[6];dev=core.generator(alt,40,[20260914,919,1]);plan=old.CalibrationPlan(dev)
    draw=np.random.default_rng(99).multinomial(40,np.ones(40)/40,size=17)
    fast=plan.fit(draw);labels=dev.y.reshape(-1)
    for r,w in enumerate(draw):
        samplew=np.repeat(w,3);slow=[]
        for score in [dev.joint.reshape(-1,3),dev.late.reshape(-1,3)]:
            for chosen in [score,score[:,[0]],score[:,[1]],score[:,[2]]]:
                slow.append(threshold(chosen,labels,samplew,np.isfinite(chosen))['threshold'])
        need(np.allclose(fast[r],slow,atol=0,rtol=0,equal_nan=True),'fast threshold regression')
    record('weighted_calibration_against_slow_frozen_primitive',draws=17)
    values=np.arange(100,dtype=float)
    need(np.allclose(interval(values),[2.475,96.525],rtol=0,atol=1e-12),'percentile fixture')
    need(np.allclose(interval(values,30.,True),[-36.525,57.525],rtol=0,atol=1e-12),'basic fixture')
    need(centered_p(30.,values,100)==(1+np.sum(np.abs(values-30.)>=30.))/101,'centered p fixture')
    need(np.isnan(interval(np.r_[np.ones(94),np.repeat(np.nan,6)])).all(),'availability fixture')
    record('percentile_basic_centered_p_availability_primitives')
    # Lambda0 complete analysis matches the original with manually identical inputs.
    ss=scenarios[6];gi=ss['development_size_index'];oi=900001;B=31
    ns=lambda domain:[*core.ROOT_NAMESPACE,domain,gi,oi]
    dd=old.generator(ss,ss['G_dev'],ns(10));ee=old.generator(ss,120,ns(20),True)
    mdd=np.random.default_rng(np.random.SeedSequence(ns(30))).multinomial(ss['G_dev'],np.ones(ss['G_dev'])/ss['G_dev'],size=B)
    mee=np.random.default_rng(np.random.SeedSequence(ns(40))).multinomial(120,np.ones(120)/120,size=B)
    expected=old.analyze_data(ss,dd,ee,mdd,mee);actual=core.outer_record(ss,oi,B)
    for key,v in expected.items():need(np.array_equal(v,actual[key],equal_nan=True),'complete analysis regression: '+key)
    record('lambda_zero_complete_original_analysis',bootstrap_B=B)
    start=time.perf_counter();probe=core.outer_record(scenarios[10],999999,999);elapsed=time.perf_counter()-start
    need(probe['refit_policy_draws'].shape==(999,4,2),'runtime draw shape')
    need(probe['oracle_conditional_policy_draws'].shape==(999,4,2),'runtime oracle shape')
    need(probe['intervals'].dtype==np.float64,'runtime dtype')
    record('fixed_excluded_runtime_probe',condition=scenarios[10]['id'],outer_index=999999,B=999,seconds=elapsed,
           estimated_12000_outer_four_worker_seconds=elapsed*12000/4,scientific_summary_inclusion=False)
    return {'created_utc':utc(),'all_pass':True,'checks':checks,'oracle_values':oracle_values,
            'environment':environment(),'pins':current_pins()}

def prepare():
    need(not (HERE/'contract-v1.json').exists(),'Contract already frozen; do not overwrite')
    cks=checks();exclusive_json(HERE/'technical-checks-v1.json',cks)
    ref=read(REFERENCE);truth={}
    for s in core.conditions():
        key='A01' if s['G_dev']==40 else 'A04'
        rr=ref[key]
        need(rr['valid']==32768 and rr['invalid']==0,'Unexpected frozen reference availability')
        mu=np.asarray(rr['truth_mean'])[4];se=np.asarray(rr['truth_mcse'])[4]
        if s['kind']=='N':mu=np.zeros(2);se=np.zeros(2)
        need(np.max(se)<.0005,'Frozen reference MCSE exceeds prespecified precision')
        truth[s['id']]={'mean':mu,'mcse':se,'source_condition':None if s['kind']=='N' else key,
            'source_path':str(REFERENCE),'source_sha256':sha(REFERENCE),'valid_reference_datasets':32768,
            'proof':'PROTOCOL.md: marginal-law and common-validity invariance; evaluation group count not in population target'}
    contract={'schema':'camv-reviewer-dependence-calibration-v1','created_utc':utc(),
      'conditions':core.conditions(),'outer_M':1000,'bootstrap_B':999,'chunk_size':25,'workers_max':4,
      'blas_threads':1,'rng_namespace':list(core.ROOT_NAMESPACE),'procedure_reference':truth,
      'targets':['fitted_policy','procedure_average_given_valid_calibration','fixed_population_oracle_policy'],
      'confirmatory_family':None,'storage':'E: SATA HDD','technical_probe_excluded':True,
      'runtime_probe_seconds':cks['checks'][-1]['seconds'],'protocol_sha256':sha(HERE/'PROTOCOL.md')}
    exclusive_json(HERE/'contract-v1.json',contract)
    pins=current_pins();pins[str(HERE/'contract-v1.json')]=sha(HERE/'contract-v1.json')
    pins[str(HERE/'technical-checks-v1.json')]=sha(HERE/'technical-checks-v1.json')
    exclusive_json(HERE/'source-manifest-v1.json',{'created_utc':utc(),'pins':pins})
    print(json.dumps({'prepared':True,'contract_sha256':sha(HERE/'contract-v1.json'),
        'manifest_sha256':sha(HERE/'source-manifest-v1.json'),'checks_all_pass':True,
        'runtime_probe_seconds':contract['runtime_probe_seconds']}),flush=True)

def identity():return {'pid':os.getpid(),'created':psutil.Process().create_time()}
def alive(ident):
    try:return abs(psutil.Process(ident['pid']).create_time()-ident['created'])<1e-6
    except psutil.NoSuchProcess:return False
def tasks(c):
    for lo in range(0,c['outer_M'],c['chunk_size']):
        for s in c['conditions']:
            yield {'id':f"{s['id']}-{lo:04d}-{lo+c['chunk_size']:04d}",'scenario':s,
                   'start':lo,'stop':min(lo+c['chunk_size'],c['outer_M'])}
def worker(task,contract_hash,pins):
    verify(pins);begin=time.perf_counter();records=[]
    for oi in range(task['start'],task['stop']):records.append(core.outer_record(task['scenario'],oi,999))
    arrays={k:np.stack([r[k] for r in records]) for k in records[0]}
    meta={'task':task,'contract_sha256':contract_hash,'source_pins':pins,'identity':identity(),'utc':utc(),
          'seconds':time.perf_counter()-begin}
    arrays['metadata']=np.array(json.dumps(meta,sort_keys=True))
    path=HERE/'run/chunks'/(task['id']+'.npz');need(not path.exists(),'Refusing to replace completed chunk')
    temp=path.with_name(path.name+'.partial-'+uuid.uuid4().hex)
    with temp.open('xb') as f:np.savez_compressed(f,**arrays);f.flush();os.fsync(f.fileno())
    verify(pins);need(not path.exists(),'Concurrent chunk collision');os.rename(temp,path)
    return {'task_id':task['id'],'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,
      'seconds':time.perf_counter()-begin,'worker_peak_rss_bytes':psutil.Process().memory_info().peak_wset if os.name=='nt' else psutil.Process().memory_info().rss}
def validate_chunk(path,task,contract_hash,pins):
    with np.load(path,allow_pickle=False) as z:
        meta=json.loads(str(z['metadata']));n=task['stop']-task['start']
        need(meta['task']==task and meta['contract_sha256']==contract_hash,'Chunk identity mismatch')
        need(meta['source_pins']==pins,'Chunk provenance mismatch')
        need(z['point_contrasts'].shape==(n,5,2),'Point shape mismatch')
        need(z['intervals'].shape==(n,4,5,2,2),'Interval shape mismatch')
        for key in ['conditional_policy_draws','refit_policy_draws','oracle_conditional_policy_draws']:
            need(z[key].shape==(n,999,4,2) and z[key].dtype==np.float64,'Inner draw shape/dtype mismatch')
        for key,g in [('dev_multiplicity',task['scenario']['G_dev']),('eval_multiplicity',120)]:
            value=z[key];need(value.shape==(n,999,g) and np.all(value.sum(axis=-1)==g),'Group multiplicity mismatch')
        for key in ['point_thresholds','intervals','oracle_intervals','point_contrasts']:
            need(not np.isinf(z[key]).any(),'Infinite scientific values')

def run(workers):
    validate_sources();need(1<=workers<=4,'Worker cap')
    manifest=read(HERE/'source-manifest-v1.json');pins=manifest['pins'];verify(pins)
    review=read(HERE/'execution-review-v1.json')
    need(review.get('authorized') is True and review.get('reviewed') is True and review.get('actor')=='root','Root technical review required')
    need(review.get('manifest_sha256')==sha(HERE/'source-manifest-v1.json'),'Reviewed source manifest mismatch')
    c=read(HERE/'contract-v1.json');need(c['conditions']==core.conditions() and c['outer_M']==1000 and c['bootstrap_B']==999,'Unreviewed design')
    runpath=HERE/'run';(runpath/'chunks').mkdir(parents=True,exist_ok=True)
    lock=runpath/'controller-lock.json'
    if lock.exists():
        prior=read(lock);need(not alive(prior),'Controller already active')
        os.rename(lock,lock.with_name('stale-lock-'+uuid.uuid4().hex+'.json'))
    exclusive_json(lock,identity());started=time.perf_counter();ch=sha(HERE/'contract-v1.json')
    event({'event':'RUN_OPEN','identity':identity(),'environment':environment(),'review_sha256':sha(HERE/'execution-review-v1.json')})
    known={}
    for line in (runpath/'events.jsonl').read_text().splitlines():
        item=json.loads(line)
        if item['event']=='TASK_END':known[item['task_id']]=item
    todo=[];completed=[]
    for task in tasks(c):
        path=runpath/'chunks'/(task['id']+'.npz')
        if path.exists():
            validate_chunk(path,task,ch,pins)
            if task['id'] in known:need(sha(path)==known[task['id']]['sha256'],'Completed chunk hash changed')
            else:event({'event':'ATOMIC_CHUNK_ADOPTED','task_id':task['id'],'path':str(path),'sha256':sha(path)})
            completed.append({'task_id':task['id'],'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size})
        else:todo.append(task)
    event({'event':'CENSUS','planned_chunks':480,'existing_chunks':len(completed),'pending_chunks':len(todo)})
    peak=0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending={};iterator=iter(todo)
        while True:
            while len(pending)<workers:
                try:task=next(iterator)
                except StopIteration:break
                event({'event':'TASK_START','task':task});pending[pool.submit(worker,task,ch,pins)]=task
            if not pending:break
            done,_=wait(pending,timeout=20,return_when=FIRST_COMPLETED)
            for future in done:
                task=pending.pop(future)
                try:result=future.result()
                except BaseException as exc:
                    event({'event':'TASK_FAILURE','task':task,'exception':repr(exc)});raise
                validate_chunk(Path(result['path']),task,ch,pins);verify(pins)
                event({'event':'TASK_END',**result});completed.append(result)
                peak=max(peak,result.get('worker_peak_rss_bytes',0))
                progress={'completed_chunks':len(completed),'planned_chunks':480,'completed_outer':len(completed)*25,
                  'elapsed_seconds':time.perf_counter()-started,'total_chunk_bytes':sum(r['bytes'] for r in completed)}
                (runpath/'progress.json').write_bytes(encoded(progress));print(json.dumps(progress),flush=True)
    need(len(completed)==480,'Incomplete fixed grid');verify(pins)
    receipt={'schema':'camv-reviewer-simulation-computation-completion-v1','completed_utc':utc(),'all_fixed_work_complete':True,
      'conditions':12,'outer_per_condition':1000,'total_outer':12000,'bootstrap_B':999,'oracle_arm':True,
      'elapsed_this_run_seconds':time.perf_counter()-started,'chunk_count':len(completed),'chunks':completed,
      'total_chunk_bytes':sum(r['bytes'] for r in completed),'maximum_worker_peak_rss_bytes':peak,
      'source_hashes_unchanged':True,'source_pins':pins,'environment':environment(),
      'review_sha256':sha(HERE/'execution-review-v1.json'),'summary_status':'pending_separate_summary'}
    exclusive_json(runpath/'computation-completion.json',receipt);event({'event':'RUN_COMPLETE','total_outer':12000})
    os.rename(lock,runpath/('closed-lock-'+uuid.uuid4().hex+'.json'))
    print(json.dumps({'completed':True,'total_outer':12000,'elapsed_seconds':receipt['elapsed_this_run_seconds']}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','run']);parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    if args.mode=='prepare':prepare()
    else:run(args.workers)
