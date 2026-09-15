"""Summarize every planned cell, including unavailable intervals and MC error."""
from pathlib import Path
import csv, hashlib, json, math
import numpy as np
import review_core as c
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def wilson(k,total):
    if total==0:return [float('nan')]*2
    z=1.959963984540054;f=k/total;den=1+z*z/total
    center=(f+z*z/(2*total))/den
    half=z*math.sqrt(f*(1-f)/total+z*z/(4*total*total))/den
    return [center-half,center+half]

def load(cond,kind):
    chunks=[]
    for p in sorted((HERE/'run'/cond/kind).glob('*.npz')):
        receipt=json.loads(p.with_suffix('.json').read_text())
        assert sha(p)==receipt['sha256']
        with np.load(p,allow_pickle=False) as z:chunks.append({k:z[k] for k in z.files})
    return {k:np.concatenate([x[k] for x in chunks]) for k in chunks[0]}

def csvout(name,rows):
    with (OUT/name).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

assert json.loads((HERE/'run/completion.json').read_text())['status']=='COMPLETE'
OUT=HERE/'summary-v2';OUT.mkdir(exist_ok=False)
covrows=[];refs=[];features=[];centers=[];bcarows=[];rejections=[];main={0:[],1:[]};saved={}
for cond in c.conditions():
    a=load(cond['id'],'outer');M=len(a['point']);assert M==1000
    if cond['exact_zero']:
        mu=np.zeros(2);mcse=np.zeros(2);validref=0
    else:
        r=load(cond['id'],'reference')['values'];assert r.shape==(32768,2)
        valid=np.isfinite(r).all(axis=1);rv=r[valid];validref=len(rv)
        mu=rv.mean(axis=0);mcse=rv.std(axis=0,ddof=1)/math.sqrt(validref)
    population=c.population_auc(cond)
    for y,metric in enumerate(('FSR','recall')):
        refs.append(dict(condition=cond['id'],metric=metric,target_pp=100*mu[y],reference_mcse_pp=100*mcse[y],
                         reference_planned=0 if cond['exact_zero'] else 32768,reference_available=validref,
                         exact_zero=cond['exact_zero'],precision_le_005pp=100*mcse[y]<=.05))
        p=a['point'][:,y];fs=a['fitted_truth'][:,y]
        for m,name in enumerate(c.METHODS):
            bounds=a['intervals'][:,m,y];av=np.isfinite(bounds).all(axis=1)
            assert np.all(bounds[av,0]<=bounds[av,1])
            for target,truth in [('fitted_policy',fs),('procedure_average',np.full(M,mu[y]))]:
                eligible=av&np.isfinite(truth);n=int(eligible.sum())
                hit=eligible&(bounds[:,0]<=truth)&(truth<=bounds[:,1]);k=int(hit.sum())
                ci=wilson(k,n)
                row=dict(condition=cond['id'],metric=metric,method=name,target=target,planned=M,available=n,covered=k,
                         coverage_available_pct=100*k/n if n else np.nan,covered_planned_pct=100*k/M,
                         wilson_low_pct=100*ci[0],wilson_high_pct=100*ci[1],
                         coverage_mcse_pct=100*math.sqrt((k/n)*(1-k/n)/n) if n else np.nan,
                         mean_width_pp=100*np.mean(bounds[eligible,1]-bounds[eligible,0]) if n else np.nan)
                for sign,label in [(-1,'minus'),(1,'plus')]:
                    t=truth+sign*3*mcse[y] if target=='procedure_average' else truth
                    row[f'coverage_ref_{label}3mcse_pct']=100*np.sum(eligible&(bounds[:,0]<=t)&(t<=bounds[:,1]))/n if n else np.nan
                covrows.append(row)
            mid=bounds.mean(axis=-1);good=av&np.isfinite(p)
            displacement=mid-p
            centers.append(dict(condition=cond['id'],metric=metric,method=name,available=int(good.sum()),
                                point_sd_pp=100*np.std(p[good],ddof=1),center_sd_pp=100*np.std(mid[good],ddof=1),
                                point_bias_pp=100*np.mean(p[good]-mu[y]),midpoint_bias_pp=100*np.mean(mid[good]-mu[y]),
                                point_displacement_correlation=np.corrcoef(p[good],displacement[good])[0,1] if np.std(displacement[good]) else np.nan))
            hits=av&((bounds[:,0]>0)|(bounds[:,1]<0));k=int(hits.sum());n=int(av.sum());ci=wilson(k,n)
            rejections.append(dict(condition=cond['id'],metric=metric,procedure=name+'_zero_exclusion',
                                   interpretation=('cross_target_zero_exclusion' if m in (0,3) else 'Type_I_error') if cond['exact_zero'] else 'descriptive_zero_exclusion',
                                   planned=M,available=n,rejected=k,rate_pct=100*k/n if n else np.nan,
                                   wilson_low_pct=100*ci[0],wilson_high_pct=100*ci[1]))
        for method,name in enumerate(('conditional_centered','refit_centered')):
            pv=a['pvalues'][:,method,y];av=np.isfinite(pv);n=int(av.sum());k=int(np.sum(av&(pv<=.05)));ci=wilson(k,n)
            rejections.append(dict(condition=cond['id'],metric=metric,procedure=name,
                                   interpretation=('cross_target_rejection' if method==0 else 'Type_I_error') if cond['exact_zero'] else 'descriptive_centered_rejection',
                                   planned=M,available=n,rejected=k,rate_pct=100*k/n if n else np.nan,
                                   wilson_low_pct=100*ci[0],wilson_high_pct=100*ci[1]))
        bd=a['bca_diagnostics'][:,y];av=bd[:,0]==0
        row=dict(condition=cond['id'],metric=metric,planned=M,available=int(av.sum()),
                 extreme_adjusted_tails=int(np.sum(bd[av,5])),mean_tie_rank_fraction=float(np.mean(bd[av,6])),
                 acceleration_mean=float(np.mean(bd[av,2])),acceleration_min=float(np.min(bd[av,2])),
                 acceleration_max=float(np.max(bd[av,2])),min_lower_probability=float(np.min(bd[av,3])),
                 max_upper_probability=float(np.max(bd[av,4])))
        for status in range(1,6):row[f'unavailable_reason_{status}']=int(np.sum(bd[:,0]==status))
        bcarows.append(row)
        lookup={r['method']:r for r in covrows if r['condition']==cond['id'] and r['metric']==metric and r['target']=='procedure_average'}
        cv=' / '.join(f"{lookup[m]['coverage_available_pct']:.1f}" for m in (c.METHODS[0],c.METHODS[1],c.METHODS[2],c.METHODS[4]))
        main[y].append([cond['id'],f"{mu[y]*100:+.3f}",cv,
                        f"{lookup[c.METHODS[1]]['mean_width_pp']:.2f} / {lookup[c.METHODS[4]]['mean_width_pp']:.2f}",
                        f"{lookup[c.METHODS[4]]['available']}/1000",
                        f"{rejections[-1]['rate_pct']:.1f}"])
    for split,key in [('development','dev_features'),('evaluation','eval_features')]:
        arr=a[key]
        for j,method in enumerate(('Joint','Late')):
            features.append(dict(condition=cond['id'],split=split,method=method,
                                 separation=cond['separation'],quantization_step=cond['step'],
                                 continuous_pair_auc=cond['continuous_pair_auc'],population_mean_pair_auc=float(population[j,:3].mean()),
                                 population_pooled_auc=float(population[j,3]),mean_sample_pair_auc=float(arr[:,j].mean()),
                                 mean_duplicate_excess_pct=100*arr[:,j+2].mean(),mean_pair_tie_probability_pct=100*arr[:,j+6].mean(),
                                 mean_tied_membership_pct=100*arr[:,j+8].mean(),
                                 mean_failure_groups=arr[:,4].mean(),mean_success_groups=arr[:,5].mean()))
    np.testing.assert_allclose(np.diff(a['intervals'][:,1],axis=-1),np.diff(a['intervals'][:,2],axis=-1),rtol=0,atol=1e-14)
    np.testing.assert_allclose(a['intervals'][:,1].mean(axis=-1)+a['intervals'][:,2].mean(axis=-1),2*a['point'],rtol=0,atol=1e-14)
    saved[cond['id']]={k:a[k][0] for k in a}
csvout('coverage.csv',covrows);csvout('reference-targets.csv',refs);csvout('score-features.csv',features)
csvout('centers.csv',centers);csvout('bca-diagnostics.csv',bcarows);csvout('rejections.csv',rejections)
for name,arr in saved.items():
    with (OUT/f'{name}-first-outer.npz').open('xb') as f:np.savez_compressed(f,**arr)
lines=['# New sensitivity results','',
       'C/R/B/A: conditional percentile / refit percentile / refit basic / refit BCa. Coverage is conditional on interval availability. Targets and widths are percentage points. Refit centered rejection is a separate decision rule.','']
for y,metric in enumerate(('FSR','recall')):
    lines += [f'## {metric}','', '| Condition | Target | C/R/B/A coverage (%) | R/A width | BCa available | Refit centered rejection (%) |',
              '|---|---|---|---|---|---|']
    lines += ['| '+' | '.join(row)+' |' for row in main[y]]
    lines += ['']
(OUT/'results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
report={'status':'PASS','outer_datasets':8000,'reference_datasets':7*32768,'methods':list(c.METHODS),
        'coverage_rows':len(covrows),'all_reference_precision_checks':all(r['precision_le_005pp'] for r in refs),
        'bca_available_by_condition_metric':[{k:r[k] for k in ['condition','metric','available']} for r in bcarows],
        'summary_sha256':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()}}
(OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['status','outer_datasets','coverage_rows','all_reference_precision_checks']}))
print((OUT/'results.md').read_text())
