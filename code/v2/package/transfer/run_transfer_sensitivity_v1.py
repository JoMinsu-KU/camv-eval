"""Post-review saved-score sensitivity; immutable v6 primitives, no inference.

Prepare writes the prospective case census before run can inspect score outcomes.
Outputs are exclusive-create. Run into another new subdirectory to replay.
"""
from pathlib import Path
import argparse, copy, csv, hashlib, importlib.util, json, os, sys, time
from datetime import datetime, timezone
for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[k] = '1'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[2]
PACKAGE = STUDY / 'staging/p0-e2e-20260914-v1/package/release-v6'
METHODS = ('joint_pool6', 'joint_pool3', 'joint_pair', 'late_pool6', 'late_pool3', 'late_pair')
WEIGHTINGS = ('sample', 'group', 'task_macro')
METRICS = ('false_success_rate', 'success_recall')
CASE_KEYS = (
    'original/main/smolvlm_instruct__ur5fail',
    'external/main/smolvlm_instruct__reassemble_rl_transfer',
    'historical/main/internvl35_4b__ur5fail',
    'historical/main/qwen3vl4b__ur5fail',
)
PAIRS = ('c0_c1', 'c0_c2', 'c1_c2')

def readj(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''): h.update(b)
    return h.hexdigest()
def writej(p, v):
    with Path(p).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(v, f, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        f.write('\n')
def writecsv(p, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows:
            r = core.clean(r)
            w.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for k,v in r.items()})
def load_module(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s); sys.modules[name] = m; s.loader.exec_module(m)
    return m
def prepare():
    spec = readj(PACKAGE / 'data/case-manifest.json')
    cases = [next(c for c in spec['cases'] if c['key'] == k) for k in CASE_KEYS]
    inputs = [PACKAGE/'data/case-manifest.json', PACKAGE/'data/frozen_calibration.json',
              PACKAGE/'release-manifest.json', PACKAGE/'replay.py', PACKAGE/'src/empirical_core_v2.py',
              PACKAGE/'src/run_empirical_v2.py', STUDY/'src/empirical_core_v2.py', STUDY/'src/run_empirical_v2.py']
    for c in spec['collections'].values(): inputs.extend([PACKAGE/c['metadata'], PACKAGE/c['scores']])
    for c in spec['cases']:
        inputs.extend(PACKAGE/c['reference']/f for f in ('metadata.json','operating-summary.csv','contrasts.csv','order-by-seed.csv','operating-by-seed.csv'))
        if c['key'] in CASE_KEYS: inputs.append(PACKAGE/c['reference']/'bootstrap-arrays.npz')
    protocol = {
        'protocol_id': 'reviewer-transfer-pooling-sensitivity-v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'classification': 'Post hoc after review; no replacement of original estimands or confirmatory family.',
        'case_selection': 'Complete census of four requested transfer cases with available saved scores, fixed before outcome computation.',
        'case_keys': list(CASE_KEYS), 'cases': cases,
        'pooled_source_pair_sets': {'pool6': ['c0_c1','c0_c2','c0_c3','c1_c2','c1_c3','c2_c3'], 'pool3': list(PAIRS)},
        'pair_calibration': 'Unchanged source pair-specific thresholds for the same three target slot pairs.',
        'camera_interpretation': 'Neutral source-slot transfer; physical camera poses are not assumed matched.',
        'methods': list(METHODS), 'metrics': list(METRICS), 'weightings': list(WEIGHTINGS),
        'threshold_rule': 'Unmodified empirical_core_v2.threshold: largest observed available positive-score knot attaining weighted recall >= 0.90 (tolerance 1e-12); accept score >= threshold; each trial has total weight one divided over included columns. Missing scores are operational rejection and remain in denominator.',
        'bootstrap': {'B': 2000, 'seed_namespaces': {c['key']:c['rng_namespace'] for c in cases},
                      'draws': 'SeedSequence(namespace).spawn(2); independent development/evaluation multinomial group multiplicities, shared over methods and model seeds, exactly original RNG.',
                      'conditional': 'Fixed policies, evaluation groups resampled.',
                      'refit': 'Development groups resampled and all thresholds refit; evaluation groups independently resampled.',
                      'intervals': '95% linear-quantile percentile and refit basic sensitivity; >=95% finite draws required.',
                      'pvalues': 'None; no new Holm family or confirmatory superiority declarations.'},
        'historical_threshold_audit': 'All six native seed17 pooled point estimators actually used in the manuscript (2 models x single/Joint/Late). Compare same original development scores under exact current rule, validity, float hex/delta, development and target decisions/rates. Inventory stored seed29/43 copies against seed17; do not claim unavailable seed29/43 score replay. All non-native and unused historical methods are out of this manuscript estimand.',
        'historical_point_policy': 'Preserve frozen pool6 at point; refit pool6 in bootstrap as original. Never silently replace a historical threshold. Halt dependent sensitivity if an unexpected original-development mismatch changes target decisions.',
        'existing_sensitivity_extraction': 'All 16 baseline release cases: complete interaction/calibration contrast rows for sample/group/task weighting, exact-pixel exclusion, order flips, reverse and SymmetricJoint operating points; descriptive extraction only.',
        'empirical_structure_description': 'Describe Joint/Late score dependence, exact ties and group-size imbalance from source/evaluation saved cohorts; no model fit or selection.',
        'environment': {'python': 'E:/SoftwareX/.conda-envs/grasp-vlm/python.exe', 'storage': 'E: SATA HDD', 'inference_calls': 0},
        'code_sha256': sha(__file__),
        'inputs_sha256': {str(p):sha(p) for p in inputs},
    }
    writej(HERE/'protocol.json', protocol)
    print(json.dumps({'status':'PROTOCOL_SAVED','case_count':len(cases),'input_count':len(protocol['inputs_sha256'])}), flush=True)

def get_cohorts(case, data):
    output = []
    for role in ('source','target'):
        ids = set(case[role+'_samples'])
        rows = [r for r in data[case[role+'_collection']] if r['model_id']==case['model'] and r['sample_id'] in ids]
        cohorts = core.build_cohorts(rows)
        selected = [cohorts[(case['model'], case[role+'_dataset'], case[role+'_split'], seed)] for seed in case['seeds']]
        assert all(list(c.samples)==case[role+'_samples'] and list(c.groups)==case[role+'_groups'] for c in selected)
        output.append(selected)
    return output

def arrayhash(*arrays):
    h = hashlib.sha256()
    for a in arrays:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode()); h.update(str(a.shape).encode()); h.update(a.tobytes())
    return h.hexdigest()

def audit_historical(spec, data, frozen, out):
    audit_rows=[]; copied=[]; blocked=False
    cal = readj(PACKAGE/'data/frozen_calibration.json')['thresholds']
    for model in ('internvl35_4b','qwen3vl4b'):
        cases=[c for c in spec['cases'] if c['model']==model and '/main/' in c['key']]
        ds, _ = get_cohorts(cases[0],data); dev=ds[0]
        for base in ('single','joint','late'):
            pool=dev.pools[base]; current=core.threshold(pool.scores,dev.y,dev.sample_weights(),pool.available)
            t=frozen[(model,17)][base]; rt=current['threshold']
            row={'model':model,'base':base,'seed':17,'saved_threshold':t,'refitted_threshold':rt,
                 'saved_float_hex':float(t).hex(),'refitted_float_hex':float(rt).hex(),
                 'float_delta_refitted_minus_saved':rt-t,'threshold_bit_equal':float(t).hex()==float(rt).hex(),
                 'refit_status':current['status'],'refit_positive_weight':current['positive_weight'],
                 'refit_achieved_recall':current['achieved_recall'],
                 'development_arrays_sha256':arrayhash(pool.scores,pool.available,dev.y,dev.group_index),
                 'n_dev_samples':len(dev.samples),'n_dev_groups':len(dev.groups),'n_columns':len(pool.columns)}
            for target in [dev]+[get_cohorts(c,data)[1][0] for c in cases]:
                p=target.pools[base]; a=p.available & (p.scores>=t); b=p.available & (p.scores>=rt)
                label=target.dataset+'_'+target.split
                row[label+'_flips']=int((a!=b).sum())
                ma=core.rates(target,a); mb=core.rates(target,b)
                for i,m in enumerate(METRICS):row[label+'_'+m+'_delta']=float(mb[i]-ma[i])
                if target is not dev and row[label+'_flips'] and t!=rt: blocked=True
            audit_rows.append(row)
            fam={'late':'late_meanlogodds'}.get(base,base)
            for r in cal:
                if r['model_id']==model and r['ablation']=='native' and r['calibration_family']==fam:
                    copied.append({'model':model,'base':base,'stored_seed':r['seed'],'threshold':r['threshold'],
                                   'same_as_analyzed_seed17':r['threshold']==t,
                                   'score_replay_scope':'direct seed17 development audit' if r['seed']==17 else 'threshold-copy comparison only; portable scores store seed17'})
    writecsv(out/'historical-threshold-audit.csv',audit_rows)
    writecsv(out/'historical-threshold-copy-inventory.csv',copied)
    writej(out/'historical-threshold-audit.json',core.clean({'rows':audit_rows,'threshold_copy_inventory':copied,'changes_target_decisions':blocked}))
    if blocked: raise RuntimeError('Historical threshold mismatch changes target decisions; see audit; dependent pooling analysis halted.')
    return audit_rows

def fit_six(dev, target, multiplicity=None, frozen_point=None):
    weights=dev.sample_weights(multiplicity); fitted=[]; records=[]
    assert tuple(target.pairs)==PAIRS
    for base in ('joint','late'):
        p=dev.pools[base]; allfit=core.threshold(p.scores,dev.y,weights,p.available)
        if frozen_point is not None: allfit=dict(allfit,threshold=frozen_point[base],source='historical_frozen_point')
        subset=p.select(PAIRS); subsetfit=core.threshold(subset.scores,dev.y,weights,subset.available)
        pairfits=[core.threshold(p.select([c]).scores,dev.y,weights,p.select([c]).available) for c in PAIRS]
        fitted.extend([allfit['threshold'],subsetfit['threshold'],np.array([f['threshold'] for f in pairfits])])
        records.extend([dict(base=base,pool='pool6',**allfit),dict(base=base,pool='pool3',**subsetfit)])
        records.extend(dict(base=base,pool='pair',column=c,**f) for c,f in zip(PAIRS,pairfits))
    return fitted,records

def accepted_six(target, fits):
    output=[]
    for i,t in enumerate(fits):
        p=target.pools['joint' if i<3 else 'late']
        pred=(p.available & np.isfinite(t) & (p.scores>=t)).mean(axis=1)
        if not np.isfinite(t).all():pred[:]=np.nan
        output.append(pred)
    return np.array(output)

def contrast_map(a):
    jp6,jp3,jpair,lp6,lp3,lpair=[a[...,i,:] for i in range(6)]
    i6=(jpair-lpair)-(jp6-lp6);i3=(jpair-lpair)-(jp3-lp3)
    return {'interaction_pool6':i6,'interaction_pool3':i3,'interaction_pool3_minus_pool6':i3-i6,
            'joint_pool3_minus_pool6':jp3-jp6,'late_pool3_minus_pool6':lp3-lp6,
            'joint_pair_minus_pool6':jpair-jp6,'joint_pair_minus_pool3':jpair-jp3,
            'late_pair_minus_pool6':lpair-lp6,'late_pair_minus_pool3':lpair-lp3}

def run_case(case,data,frozen,out):
    start=time.perf_counter(); ds,ts=get_cohorts(case,data); S=len(ds); B=2000
    dest=out/case['case_id'];dest.mkdir(exist_ok=False)
    ss,es=np.random.SeedSequence(case['rng_namespace']).spawn(2)
    gd=len(ds[0].groups);ge=len(ts[0].groups)
    md=np.random.default_rng(ss).multinomial(gd,np.ones(gd)/gd,size=B)
    me=np.random.default_rng(es).multinomial(ge,np.ones(ge)/ge,size=B)
    point=np.zeros((S,3,6,2));conditional=np.zeros((S,B,3,6,2));refit=np.zeros_like(conditional)
    thresholds=np.full((S,B,2,5),np.nan);fitrows=[]
    for si,(d,t) in enumerate(zip(ds,ts)):
        f,records=fit_six(d,t,frozen_point=frozen[(d.model,d.seed)] if case['axis']=='historical' else None)
        fitrows.extend(dict(case_id=case['case_id'],seed=d.seed,**r) for r in records)
        p=accepted_six(t,f)
        for wi,w in enumerate(WEIGHTINGS):
            point[si,wi]=core.matrix_rates(t,p,np.ones(ge,dtype=int),w)[0]
            conditional[si,:,wi]=core.matrix_rates(t,p,me,w)
    for b in range(B):
        for si,(d,t) in enumerate(zip(ds,ts)):
            f,_=fit_six(d,t,md[b]);p=accepted_six(t,f)
            for bi,offset in enumerate((0,3)):thresholds[si,b,bi]=np.r_[f[offset],f[offset+1],f[offset+2]]
            for wi,w in enumerate(WEIGHTINGS):refit[si,b,wi]=core.matrix_rates(t,p,me[b],w)[0]
        if (b+1)%500==0:print(json.dumps({'case':case['case_id'],'draws':b+1,'elapsed':time.perf_counter()-start}),flush=True)
    writecsv(dest/'point-thresholds.csv',fitrows)
    np.savez_compressed(dest/'bootstrap-arrays.npz',point_by_seed=point,conditional_by_seed=conditional,refit_by_seed=refit,
                        development_group_multiplicity=md,evaluation_group_multiplicity=me,refit_thresholds=thresholds)
    reference=PACKAGE/case['reference'];meta=readj(reference/'metadata.json');checks=[]
    with np.load(reference/'bootstrap-arrays.npz',allow_pickle=False) as old:
        for name,a in [('development_group_multiplicity',md),('evaluation_group_multiplicity',me)]:
            checks.append({'check':name,'pass':bool(np.array_equal(a,old[name]))})
        for name,a in [('point_by_seed',point),('conditional_by_seed',conditional),('refit_by_seed',refit)]:
            for newi,oldname in [(0,'joint_pooled'),(2,'joint_pair'),(3,'late_pooled'),(5,'late_pair')]:
                ai=a[...,newi,:];bi=old[name][...,meta['method_axis'].index(oldname),:]
                checks.append({'check':name+'/'+oldname,'pass':bool(np.allclose(ai,bi,rtol=0,atol=1e-12,equal_nan=True)),
                               'max_abs_difference':float(np.nanmax(np.abs(ai-bi)))})
    assert all(c['pass'] for c in checks),checks
    writej(dest/'original-policy-replay-checks.json',checks)
    pointmean=point.mean(axis=0);condmean=conditional.mean(axis=0);refitmean=refit.mean(axis=0)
    rows=[];contrastrows=[]
    for wi,w in enumerate(WEIGHTINGS):
        for mi,m in enumerate(METHODS):
            for ki,k in enumerate(METRICS):
                row=dict(case_id=case['case_id'],weighting=w,method=m,metric=k,estimate=pointmean[wi,mi,ki])
                for name,a in [('conditional',condmean),('refit',refitmean)]:
                    vals=a[:,wi,mi,ki];lo,hi=core.interval(vals);row.update({name+'_lower':lo,name+'_upper':hi,name+'_valid':int(np.isfinite(vals).sum())})
                rows.append(row)
    pmap=contrast_map(pointmean);cmap=contrast_map(condmean);rmap=contrast_map(refitmean)
    for name,pv in pmap.items():
        for wi,w in enumerate(WEIGHTINGS):
            for ki,k in enumerate(METRICS):
                pe=pv[wi,ki]; cv=cmap[name][:,wi,ki];rv=rmap[name][:,wi,ki]
                ci=core.interval(cv);ri=core.interval(rv);basic=core.interval(rv,pe,True)
                contrastrows.append(dict(case_id=case['case_id'],weighting=w,contrast=name,metric=k,estimate=pe,
                                         conditional_lower=ci[0],conditional_upper=ci[1],refit_lower=ri[0],refit_upper=ri[1],
                                         basic_lower=basic[0],basic_upper=basic[1],conditional_valid=int(np.isfinite(cv).sum()),
                                         refit_valid=int(np.isfinite(rv).sum()),conditional_width=ci[1]-ci[0],refit_width=ri[1]-ri[0]))
    writecsv(dest/'operating-summary.csv',rows);writecsv(dest/'contrasts.csv',contrastrows)
    writej(dest/'metadata.json',dict(case_id=case['case_id'],source_case=case['key'],B=B,seeds=case['seeds'],
                                  rng_namespace=case['rng_namespace'],method_axis=list(METHODS),weightings=list(WEIGHTINGS),
                                  metric_axis=list(METRICS),threshold_axis=['pool6','pool3',*PAIRS],
                                  elapsed_seconds=time.perf_counter()-start,environment_storage='E: SATA HDD',
                                  original_policies_reproduced=True,classification='posthoc sensitivity, no p-values or new family'))
    return rows,contrastrows,checks

def extract_existing(spec,out):
    contrasts=[];operating=[];ordering=[]
    keepmethods={'joint_pooled','joint_pair','late_pooled','late_pair','symmetric_pooled','symmetric_pair',
                 'reverse_forward_threshold_pooled','reverse_forward_threshold_pair','reverse_recalibrated_pooled','reverse_recalibrated_pair'}
    keepcontrasts={'interaction','joint_pair_minus_joint_pooled','late_pair_minus_late_pooled',
                   'joint_pooled_minus_symmetric_pooled','joint_pair_minus_symmetric_pair'}
    for case in spec['cases']:
        ref=PACKAGE/case['reference']
        for file,dest,filterfn in [('contrasts.csv',contrasts,lambda r:r['contrast'] in keepcontrasts),
                                   ('operating-summary.csv',operating,lambda r:r['method'] in keepmethods),
                                   ('order-by-seed.csv',ordering,lambda r:True)]:
            with (ref/file).open(encoding='utf-8-sig',newline='') as f:
                for r in csv.DictReader(f):
                    if filterfn(r):dest.append(dict(source_case=case['key'],**r))
    writecsv(out/'existing-sensitivity-contrasts.csv',contrasts)
    writecsv(out/'existing-sensitivity-operating.csv',operating)
    writecsv(out/'existing-order-sensitivity.csv',ordering)
    return {'contrast_rows':len(contrasts),'operating_rows':len(operating),'ordering_rows':len(ordering)}

def describe_structure(spec,data,out):
    from scipy.stats import spearmanr
    seen=set();rows=[]
    for case in spec['cases']:
        if '/main/' not in case['key']:continue
        ds,ts=get_cohorts(case,data)
        for c in ds+ts:
            key=(c.model,c.dataset,c.split,c.seed)
            if key in seen:continue
            seen.add(key);gsize=np.bincount(c.group_index)
            j=c.pools['joint'];l=c.pools['late'];valid=j.available & l.available
            for pi,pair in enumerate(c.pairs):
                for label in (0,1):
                    v=valid[:,pi] & (c.y==label);x=j.scores[v,pi];y=l.scores[v,pi]
                    rows.append(dict(model=c.model,dataset=c.dataset,split=c.split,seed=c.seed,pair=pair,label=label,
                                     n=int(v.sum()),n_groups=len(c.groups),group_size_min=int(gsize.min()),
                                     group_size_max=int(gsize.max()),group_size_mean=float(gsize.mean()),
                                     joint_unique_scores=len(np.unique(x)),late_unique_scores=len(np.unique(y)),
                                     joint_tied_fraction=1-len(np.unique(x))/len(x) if len(x) else np.nan,
                                     late_tied_fraction=1-len(np.unique(y))/len(y) if len(y) else np.nan,
                                     joint_late_spearman=float(spearmanr(x,y).statistic) if len(np.unique(x))>1 and len(np.unique(y))>1 else np.nan))
    writecsv(out/'empirical-score-dependence-ties-groups.csv',rows)

def run(output):
    global core,np
    begun=time.perf_counter();protocol=readj(HERE/'protocol.json')
    assert protocol['code_sha256']==sha(__file__),'Code changed after protocol freeze'
    for p,h in protocol['inputs_sha256'].items():assert sha(p)==h,('input drift',p)
    output=output.resolve();assert output.is_relative_to(HERE) and not output.exists()
    output.mkdir(parents=True,exist_ok=False)
    import numpy as np
    sys.path.insert(0,str(PACKAGE/'src'));import empirical_core_v2 as core
    loader=load_module(PACKAGE/'replay.py','immutable_v6_loader')
    spec=readj(PACKAGE/'data/case-manifest.json');data={k:loader.load_collection(v) for k,v in spec['collections'].items()}
    frozen={};mapping={'single':'single','joint':'joint','late_meanlogodds':'late'}
    for r in readj(PACKAGE/'data/frozen_calibration.json')['thresholds']:
        if r['ablation']=='native' and r['calibration_family'] in mapping:
            frozen.setdefault((r['model_id'],r['seed']),{})[mapping[r['calibration_family']]]=r['threshold']
    audit=audit_historical(spec,data,frozen,output)
    allrows=[];allcontrasts=[];allchecks=[]
    for k in protocol['case_keys']:
        case=next(c for c in spec['cases'] if c['key']==k)
        rows,cr,checks=run_case(case,data,frozen,output);allrows.extend(rows);allcontrasts.extend(cr)
        allchecks.append({'case':k,'checks':checks})
    writecsv(output/'operating-summary.csv',allrows);writecsv(output/'contrasts.csv',allcontrasts)
    extracted=extract_existing(spec,output);describe_structure(spec,data,output)
    for p,h in protocol['inputs_sha256'].items():assert sha(p)==h,('input changed during execution',p)
    writej(output/'environment.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,storage='E: SATA HDD',
                                         inference_calls=0,launcher='E:/SoftwareX/Start-GraspExperiment.ps1'))
    writej(output/'checks.json',{'status':'PASS','input_hashes_preserved':True,'original_policy_comparisons':allchecks,
                               'historical_threshold_bit_equal':all(r['threshold_bit_equal'] for r in audit),'existing_extraction':extracted})
    writej(output/'completion.json',{'status':'COMPLETE','elapsed_seconds':time.perf_counter()-begun,'case_count':4,
                                    'B_per_case':2000,'protocol_sha256':sha(HERE/'protocol.json'),'code_sha256':sha(__file__),
                                    'input_hashes_preserved':True,'output_files_sha256':{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()}})
    print(json.dumps({'status':'COMPLETE','output':str(output),'elapsed_seconds':time.perf_counter()-begun}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.prepare:prepare()
    else:
        if args.output is None:parser.error('--output required for computation')
        run(args.output)
