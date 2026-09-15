"""Raw-to-table CAMV retrospective/prospective evaluation with complete bootstrap arrays."""
from __future__ import annotations
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
import argparse
from pathlib import Path
import hashlib
import json
import csv
import math
import time
from datetime import datetime,timezone
import numpy as np
from empirical_core_v2 import (clean,fit,policies,policy_metrics,prediction_matrix,matrix_rates,
    historical_rows,prospective_rows,build_cohorts,contrast_arrays,interval,decision,COSTS)

ROOT=Path(__file__).resolve().parents[1]
OLD=Path('E:/SoftwareX/grasp-study')
WEIGHTINGS=('sample','group','task_macro')
METRICS=('false_success_rate','success_recall')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''): h.update(block)
    return h.hexdigest()

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(clean(value),stream,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False)
        stream.write('\n')

def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader()
        for row in rows:
            c=clean(row)
            w.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in c.items()})

def frozen_thresholds():
    x=json.loads((OLD/'results/review-v5-v1/reanalysis/inputs/frozen_calibration.json').read_text(encoding='utf-8-sig'))
    mapping={'joint':'joint','late_meanlogodds':'late','single':'single'}
    result={}
    for r in x['thresholds']:
        if r['ablation']=='native' and r['calibration_family'] in mapping:
            result.setdefault((r['model_id'],r['seed']),{})[mapping[r['calibration_family']]]=r['threshold']
    return result

def fit_vector(fitted):
    fields=[];values=[]
    for base,record in fitted.items():
        fields.append(base+'.pooled');values.append(record['pooled']['threshold'])
        for column,v in record['columns'].items():
            fields.append(base+'.'+column);values.append(v['threshold'])
    return fields,np.array(values)

def source_recall(fitted,method,target):
    """Report the empirical source reference appropriate to the fitted policy.

    Pooled fusion uses all source pairs; pair calibration averages target-eligible
    source pairs; camera-selected policies use their actually selected source camera.
    This distinction is saved with the output, rather than calling both matched recall.
    """
    from empirical_core_v2 import choose_camera
    if method in ('joint_pooled','late_pooled','symmetric_pooled'):
        return fitted[method.removesuffix('_pooled')]['pooled']['achieved_recall']
    if method in ('joint_pair','late_pair','symmetric_pair'):
        return float(np.mean([fitted[method.removesuffix('_pair')]['columns'][p]['success_recall'] for p in target.pairs]))
    if method=='single_pooled_average': return fitted['single']['pooled']['achieved_recall']
    if method=='single_calibrated_average':
        return float(np.mean([fitted['single']['columns'][c]['success_recall'] for c in target.cameras]))
    if method.startswith('single_calibrated_c'):
        return fitted['single']['columns'][method.removeprefix('single_calibrated_')]['success_recall']
    if method=='best_calibrated':
        c=choose_camera(fitted,target.cameras)
        return fitted['single']['columns'][c]['success_recall'] if c else math.nan
    if method=='pair_best_calibrated':
        chosen=[choose_camera(fitted,p.split('_')) for p in target.pairs]
        return float(np.mean([fitted['single']['columns'][c]['success_recall'] if c else math.nan for c in chosen]))
    # Reverse-under-forward-threshold recall is a secondary ordering diagnostic;
    # no fabricated calibration recall is attached to a rule not calibrated this way.
    if method.startswith('reverse_recalibrated_'):
        if method.endswith('_pooled'): return fitted['reverse']['pooled']['achieved_recall']
        return float(np.mean([fitted['reverse']['columns'][p]['success_recall'] for p in target.pairs]))
    return math.nan

def run_case(devs,targets,case_id,out,B,frozen,namespace):
    start=time.perf_counter();out.mkdir(parents=True,exist_ok=False)
    assert len(devs)==len(targets)>0
    for ds in (devs,targets):
        assert all(c.samples==ds[0].samples and c.groups==ds[0].groups for c in ds)
    model=targets[0].model;domain=targets[0].dataset
    fitted=[fit(d,frozen_pooled=frozen.get((model,d.seed))) for d in devs]
    names=list(policies(targets[0],fitted[0]));n=len(names);S=len(devs)
    point_by_seed=np.full((S,len(WEIGHTINGS),n,2),np.nan)
    point_rows=[];pair_rows=[];task_rows=[];order_rows=[]
    point_recall_source=np.full((S,n),np.nan)
    for si,(dev,target,f) in enumerate(zip(devs,targets,fitted)):
        ps=policies(target,f)
        for wi,weighting in enumerate(WEIGHTINGS):
            for mi,name in enumerate(names):
                record=policy_metrics(target,ps[name],weighting)
                point_by_seed[si,wi,mi]=[record[m] if record['fit_available'] else np.nan for m in METRICS]
                record.update(case_id=case_id,model=model,dataset=domain,seed=target.seed,method=name)
                if weighting=='sample':
                    record['source_dev_recall']=source_recall(f,name,target)
                    record['realized_recall_transfer']=record['success_recall']-record['source_dev_recall']
                point_rows.append(record)
        for mi,name in enumerate(names):
            point_recall_source[si,mi]=source_recall(f,name,target)
            pool,t,selected=ps[name]
            for ci,column in enumerate(pool.columns):
                pc=pool.select([column]);tc=float(t) if np.ndim(t)==0 else t[ci]
                r=policy_metrics(target,(pc,tc,selected),'sample')
                pair_rows.append(dict(r,case_id=case_id,model=model,dataset=domain,seed=target.seed,method=name,column=column))
            pred=(pool.available & np.isfinite(t))&(pool.scores>=t)
            for task in sorted(set(target.tasks)):
                select=target.tasks==task;accepted=pred[select].mean(axis=1);labels=target.y[select]
                r={'case_id':case_id,'model':model,'dataset':domain,'seed':target.seed,'method':name,'task':task,
                   'n_samples':int(select.sum()),'n_success':int(labels.sum()),'n_failure':int((1-labels).sum())}
                for label,metric in enumerate(METRICS):
                    r[metric]=float(accepted[labels==label].mean()) if np.any(labels==label) else math.nan
                task_rows.append(r)
        fwd=target.pools['joint'];rev=target.pools['reverse']
        for gran in ('pooled','pair'):
            t=ps['joint_'+gran][1];a=fwd.available&np.isfinite(t);b=rev.available&np.isfinite(t)
            p=a&(fwd.scores>=t);q=b&(rev.scores>=t);valid=a&b
            for ci,pair in enumerate(target.pairs):
                v=valid[:,ci]
                order_rows.append({'case_id':case_id,'seed':target.seed,'pair':pair,'calibration':gran,
                   'n_valid':int(v.sum()),'flip_rate':float((p[v,ci]!=q[v,ci]).mean()) if v.any() else math.nan,
                   'mean_absolute_score_difference':float(np.abs(fwd.scores[v,ci]-rev.scores[v,ci]).mean()) if v.any() else math.nan})
    write_json(out/'point-fits.json',{'fits':fitted,'seeds':[d.seed for d in devs]})
    write_csv(out/'operating-by-seed.csv',point_rows);write_csv(out/'pair-operating-by-seed.csv',pair_rows)
    write_csv(out/'task-operating-by-seed.csv',task_rows);write_csv(out/'order-by-seed.csv',order_rows)
    point=point_by_seed.mean(axis=0)
    # One shared group draw for all methods and all repeated model seeds.
    source_seq,eval_seq=np.random.SeedSequence(namespace).spawn(2)
    gd=len(devs[0].groups);ge=len(targets[0].groups)
    md=np.random.default_rng(source_seq).multinomial(gd,np.ones(gd)/gd,size=B)
    me=np.random.default_rng(eval_seq).multinomial(ge,np.ones(ge)/ge,size=B)
    conditional_by_seed=np.full((S,B,len(WEIGHTINGS),n,2),np.nan)
    for si,(target,f) in enumerate(zip(targets,fitted)):
        _,p=prediction_matrix(target,f,names)
        for wi,weighting in enumerate(WEIGHTINGS):
            conditional_by_seed[si,:,wi]=matrix_rates(target,p,me,weighting)
    fields,_=fit_vector(fitted[0])
    draw_thresholds=np.full((S,B,len(fields)),np.nan)
    refit_by_seed=np.full_like(conditional_by_seed,np.nan)
    draw_source_recall=np.full((S,B,n),np.nan)
    choices=np.full((S,B,1+len(targets[0].pairs)),-1,dtype=np.int16)
    for b in range(B):
        for si,(dev,target) in enumerate(zip(devs,targets)):
            f=fit(dev,md[b]);_,v=fit_vector(f);draw_thresholds[si,b]=v
            _,p=prediction_matrix(target,f,names)
            for wi,weighting in enumerate(WEIGHTINGS):
                refit_by_seed[si,b,wi]=matrix_rates(target,p,me[b],weighting)[0]
            for mi,name in enumerate(names):draw_source_recall[si,b,mi]=source_recall(f,name,target)
            ps=policies(target,f);selected=[ps['best_calibrated'][2]]+ps['pair_best_calibrated'][2]
            choices[si,b]=[dev.cameras.index(c) if c else -1 for c in selected]
        if (b+1)%250==0:print(json.dumps({'case':case_id,'bootstrap_completed':b+1,'planned':B,'elapsed_seconds':time.perf_counter()-start}),flush=True)
    conditional=conditional_by_seed.mean(axis=0);refit=refit_by_seed.mean(axis=0)
    transfer_cond=conditional[:,:, :,1]-point_recall_source.mean(axis=0)[None,None,:]
    transfer_refit=refit[:,:,:,1]-draw_source_recall.mean(axis=0)[:,None,:]
    np.savez_compressed(out/'bootstrap-arrays.npz',point_by_seed=point_by_seed,conditional_by_seed=conditional_by_seed,
        refit_by_seed=refit_by_seed,development_group_multiplicity=md,evaluation_group_multiplicity=me,
        refit_thresholds=draw_thresholds,selected_camera_indices=choices,source_recall_by_draw=draw_source_recall,
        source_recall_point=point_recall_source,conditional_transfer=transfer_cond,refit_transfer=transfer_refit)
    summary=[];contrasts=[];classifications=[]
    pc=contrast_arrays(names,point);cc=contrast_arrays(names,conditional);rc=contrast_arrays(names,refit)
    for wi,weighting in enumerate(WEIGHTINGS):
        for mi,name in enumerate(names):
            for ki,metric in enumerate(METRICS):
                values=point_by_seed[:,wi,mi,ki]
                row={'case_id':case_id,'model':model,'dataset':domain,'weighting':weighting,'method':name,'metric':metric,
                     'estimate':point[wi,mi,ki],'seed_sd':float(np.std(values,ddof=1)) if S>1 else math.nan,
                     'n_analyzed_seeds':S,'n_bootstrap':B}
                for mode,a in (('conditional',conditional),('refit',refit)):
                    ci=interval(a[:,wi,mi,ki]);row[mode+'_lower'],row[mode+'_upper']=ci
                    row[mode+'_valid']=int(np.isfinite(a[:,wi,mi,ki]).sum())
                summary.append(row)
        for contrast,d in pc.items():
            for ki,metric in enumerate(METRICS):
                point_effect=d[wi,ki];cvals=cc[contrast][:,wi,ki];rvals=rc[contrast][:,wi,ki]
                ci=interval(cvals);ri=interval(rvals);bi=interval(rvals,point_effect,True)
                widthc=ci[1]-ci[0];widthr=ri[1]-ri[0]
                finite=rvals[np.isfinite(rvals)]
                rfp=float(np.mean(finite*point_effect<0)) if len(finite) and point_effect!=0 and np.isfinite(point_effect) else math.nan
                approximate_p=(1+int(np.sum(np.abs(finite-point_effect)>=abs(point_effect))))/(len(finite)+1) if len(finite)>=math.ceil(.95*B) and np.isfinite(point_effect) else math.nan
                contrasts.append({'case_id':case_id,'weighting':weighting,'contrast':contrast,'metric':metric,
                    'estimate':point_effect,'conditional_lower':ci[0],'conditional_upper':ci[1],
                    'refit_lower':ri[0],'refit_upper':ri[1],'basic_lower':bi[0],'basic_upper':bi[1],
                    'conditional_width':widthc,'refit_width':widthr,'cui':widthr/widthc if widthc>0 else math.nan,
                    'rfp_strict':rfp,'bootstrap_negative':float(np.mean(finite<0)) if len(finite) else math.nan,
                    'bootstrap_tie':float(np.mean(finite==0)) if len(finite) else math.nan,
                    'bootstrap_positive':float(np.mean(finite>0)) if len(finite) else math.nan,
                    'conditional_valid':int(np.isfinite(cvals).sum()),'refit_valid':len(finite),
                    'approximate_centered_bootstrap_p':approximate_p})
            for mode,vals in (('conditional',cc[contrast]),('refit',rc[contrast])):
                fc=interval(vals[:,wi,0]);rr=interval(vals[:,wi,1])
                classifications.append({'case_id':case_id,'weighting':weighting,'contrast':contrast,'uncertainty':mode,
                    'strict_pareto_diagnostic':decision(fc,rr),'illustrative_2pp_diagnostic':decision(fc,rr,.02),
                    'formal_family_superiority_claim':False})
    write_csv(out/'operating-summary.csv',summary);write_csv(out/'contrasts.csv',contrasts)
    write_csv(out/'classification-diagnostics.csv',classifications)
    metadata={'case_id':case_id,'model':model,'dataset':domain,'B':B,'seeds':[t.seed for t in targets],
        'weightings':WEIGHTINGS,'method_axis':names,'metric_axis':METRICS,'threshold_fields':fields,
        'source_groups':devs[0].groups,'target_groups':targets[0].groups,'source_samples':devs[0].samples,
        'target_samples':targets[0].samples,'rng_namespace':namespace,'source_cameras':devs[0].cameras,
        'target_cameras':targets[0].cameras,'source_pooled_reference':'all source pairs',
        'source_pair_reference':'target-eligible source pairs','camera_reference':'selected source camera(s)',
        'historical_seed_scope':'Only native seed17 compact records are reanalyzed; three original runs were verified identical separately.' if frozen else None,
        'elapsed_seconds':time.perf_counter()-start,'environment_storage':'E: SATA HDD',
        'code_sha256':{p.name:sha(p) for p in (Path(__file__),ROOT/'src/empirical_core_v2.py')}}
    write_json(out/'metadata.json',metadata)
    print(json.dumps({'case':case_id,'status':'COMPLETE','seconds':metadata['elapsed_seconds']}),flush=True)
    return metadata

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['historical','prospective'],required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--raw',nargs='*',default=[])
    parser.add_argument('--metadata',type=Path);parser.add_argument('--external-raw',nargs='*',default=[])
    parser.add_argument('--external-metadata',type=Path);parser.add_argument('--B',type=int,default=2000)
    parser.add_argument('--exclude-groups',nargs='*',default=[]);parser.add_argument('--technical-fixture',action='store_true')
    args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to(ROOT):raise ValueError('Outputs confined to new study')
    if args.B!=2000 and not args.technical_fixture:raise ValueError('Scientific B is frozen at2000')
    out.mkdir(parents=True,exist_ok=False)
    if args.phase=='historical':
        paths=[OLD/'results/review-v5-v1/reanalysis/records.csv.gz']
        cohorts=build_cohorts(historical_rows(paths[0],args.exclude_groups));frozen=frozen_thresholds()
    else:
        if not args.metadata or not args.raw:raise ValueError('Prospective raw and metadata required')
        rows=list(prospective_rows(args.raw,args.metadata));paths=[*map(Path,args.raw),args.metadata]
        if args.external_raw:
            rows.extend(prospective_rows(args.external_raw,args.external_metadata));paths.extend([*map(Path,args.external_raw),args.external_metadata])
        cohorts=build_cohorts(rows);frozen={}
    config=json.loads((ROOT/'configs/protocol-v1.json').read_text())
    results=[]
    for model in sorted({key[0] for key in cohorts}):
        seeds=sorted({key[3] for key in cohorts if key[0]==model})
        if args.phase=='prospective' and seeds!=[17,29,43]:raise ValueError(('Incomplete prospective seeds',seeds))
        devs=[cohorts[(model,'rlbenchfail','dev',seed)] for seed in seeds]
        for dataset,split,index in (('rlbenchfail','confirmation',0),('ur5fail','external',1)):
            targets=[cohorts[(model,dataset,split,seed)] for seed in seeds]
            case=model+'__'+dataset
            namespace=[20260910,config['bootstrap']['model_indices'][model],index,1 if args.exclude_groups else 0]
            results.append(run_case(devs,targets,case,out/case,args.B,frozen,namespace))
        if any(k[0]==model and k[1]=='reassemble' for k in cohorts):
            extdev=[cohorts[(model,'reassemble','dev',seed)] for seed in seeds]
            targets=[cohorts[(model,'reassemble','confirmation',seed)] for seed in seeds]
            for label,source,index in (('local',extdev,2),('rl_transfer',devs,3)):
                case=model+'__reassemble_'+label
                namespace=[20260910,config['bootstrap']['model_indices'][model],index,0]
                results.append(run_case(source,targets,case,out/case,args.B,{},namespace))
    write_json(out/'completion.json',{'status':'COMPLETE','phase':args.phase,'technical_fixture':args.technical_fixture,
       'timestamp_utc':datetime.now(timezone.utc).isoformat(),'cases':results,
       'inputs':{str(p):sha(p) for p in paths},'excluded_groups':args.exclude_groups})

if __name__=='__main__':main()
