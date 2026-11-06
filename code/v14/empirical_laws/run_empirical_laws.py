"""Checkpointed executor and summaries for the frozen finite-population laws."""
from pathlib import Path
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
import argparse,csv,hashlib,json,math,sys,time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import scipy
import empirical_law_engine as e

HERE=Path(__file__).resolve().parent

def clean(value):
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(np.floating,float)):return float(value) if math.isfinite(value) else None
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    return value

def csvout(name,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (HERE/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(clean(rows))

def check_protocol():
    p=json.loads((HERE/'frozen-protocol.json').read_text())
    for path,expected in p['pinned_files'].items():
        assert e.sha(path)==expected,('Frozen file changed',path)
    assert p['engine_arithmetic']=='Exact signed integer count ratio divided by P times class denominator'
    return p

def wilson(k,n):
    if not n:return [None,None]
    z=1.959963984540054;a=k/n;b=1+z*z/n
    center=(a+z*z/(2*n))/b;radius=z*np.sqrt(a*(1-a)/n+z*z/(4*n*n))/b
    return [100*(center-radius),100*(center+radius)]

def reference_run(data):
    p=check_protocol();out=[]
    for cohort in data:
        start=time.perf_counter();N=p['reference_initial_N']
        while True:
            counts,values=e.reference(data,cohort,N)
            good={v:np.isfinite(x).all(axis=1) for v,x in values.items()}
            summaries={}
            for v,x in values.items():
                a=x[good[v]]
                summaries[v]={'mean':a.mean(axis=0),'mcse':a.std(axis=0,ddof=1)/np.sqrt(len(a)),'available':len(a)}
            if max(float(np.max(s['mcse'])) for s in summaries.values())<=p['reference_mcse_max_rate'] or N>=p['reference_cap_N']:
                break
            N*=2
        for variant,x in values.items():
            folder=HERE/'reference';folder.mkdir(exist_ok=True)
            np.savez_compressed(folder/f'{cohort}-{variant}.npz',reference_values=x,development_multiplicity=counts)
            s=summaries[variant]
            for metric in (0,1):
                out.append(dict(condition=f'EP-{cohort}-{variant}',cohort=cohort,scorer=variant,metric=e.METRICS[metric],
                    planned=N,available=s['available'],target=float(s['mean'][metric]),mcse=float(s['mcse'][metric]),
                    mcse_pp=float(100*s['mcse'][metric]),target_pp=float(100*s['mean'][metric]),
                    reference_precision_met=bool(s['mcse'][metric]<=p['reference_mcse_max_rate']),
                    validity='V requires both class denominators and all calibration thresholds finite'))
        e.dump(HERE/f'reference-{cohort}-completion.json',clean(dict(status='PASS' if all(r['reference_precision_met'] for r in out if r['cohort']==cohort) else 'PRECISION_TARGET_UNMET',
               planned=N,cohort=cohort,elapsed_seconds=time.perf_counter()-start,summaries=summaries)))
        print('REFERENCE',cohort,N,clean(summaries),flush=True)
    csvout('reference-targets.csv',out)
    assert all(row['reference_precision_met'] for row in out),'Reference MCSE requirement unmet'
    return out

def run_cohort(cohort):
    p=check_protocol();data=e.load_inputs();start=time.perf_counter()
    completed=0
    for index in range(p['M']):
        paths={v:HERE/'outer'/cohort/v/f'{index:04}.npz' for v in ('bare','space')}
        if all(path.exists() for path in paths.values()):
            for path in paths.values():
                with np.load(path) as f:assert f['refit_draws'].shape==(p['B'],2)
            completed+=1;continue
        result=e.outer(data,cohort,index,p['B'])
        for variant,row in result.items():
            dest=paths[variant];dest.parent.mkdir(parents=True,exist_ok=True)
            temp=dest.with_suffix('.tmp.npz')
            np.savez_compressed(temp,**row);temp.replace(dest)
        completed+=1
        if completed%100==0:
            e.dump(HERE/f'progress-{cohort}.json',dict(cohort=cohort,completed=completed,planned=p['M'],variants=2,
                   elapsed_seconds=time.perf_counter()-start))
            print('OUTER',cohort,completed,p['M'],round(time.perf_counter()-start,3),flush=True)
    e.dump(HERE/f'outer-{cohort}-completion.json',dict(status='PASS',cohort=cohort,completed=completed,variants=2,
           B=p['B'],elapsed_seconds=time.perf_counter()-start))
    return cohort,completed,time.perf_counter()-start

def summarize():
    p=check_protocol()
    with (HERE/'reference-targets.csv').open() as f:
        refs={(r['cohort'],r['scorer'],r['metric']):r for r in csv.DictReader(f)}
    coverage=[];summaries=[];bca=[];counts=[];diagrows=[]
    for cohort in ('RL','RE'):
        for variant in ('bare','space'):
            arrays={}
            paths=sorted((HERE/'outer'/cohort/variant).glob('*.npz'))
            assert len(paths)==p['M'],(cohort,variant,len(paths))
            names=['point','fitted_truth','intervals','bca_diagnostics','counts','threshold_values','finite_draw_counts']
            gathered={name:[] for name in names}
            for path in paths:
                with np.load(path) as saved:
                    for name in names:gathered[name].append(saved[name])
            for name in names:arrays[name]=np.stack(gathered[name])
            np.savez_compressed(HERE/f'summary-arrays-{cohort}-{variant}.npz',**arrays)
            point=arrays['point'];truth=arrays['fitted_truth'];interval=arrays['intervals']
            for k,metric in enumerate(e.METRICS):
                ref=refs[(cohort,variant,metric)];mu=float(ref['target']);se=float(ref['mcse'])
                U=point[:,k]-truth[:,k];V=truth[:,k]-mu
                out=dict(condition=f'EP-{cohort}-{variant}',cohort=cohort,scorer=variant,metric=metric,M=p['M'],
                    procedure_average_target_pp=mu*100,reference_mcse_pp=se*100,point_mean_pp=np.nanmean(point[:,k])*100,
                    point_sd_pp=np.nanstd(point[:,k],ddof=1)*100,point_bias_pp=(np.nanmean(point[:,k])-mu)*100,
                    point_rmse_pp=np.sqrt(np.nanmean((point[:,k]-mu)**2))*100,
                    evaluation_error_sd_pp=np.nanstd(U,ddof=1)*100,development_policy_sd_pp=np.nanstd(V,ddof=1)*100,
                    development_variance_ratio=np.nanvar(V,ddof=1)/np.nanvar(point[:,k],ddof=1),
                    covariance_uv_pp2=np.cov(U[np.isfinite(U)&np.isfinite(V)],V[np.isfinite(U)&np.isfinite(V)],ddof=1)[0,1]*10000,
                    finite_point_count=int(np.isfinite(point[:,k]).sum()),finite_fitted_truth_count=int(np.isfinite(truth[:,k]).sum()))
                summaries.append(out)
                for j,method in enumerate(e.METHODS):
                    ci=interval[:,j,k];valid=np.isfinite(ci).all(axis=1)
                    width=(ci[:,1]-ci[:,0])*100;mid=ci.mean(axis=1)
                    for target,tval in [('fitted_policy',truth[:,k]),('procedure_average',np.full(p['M'],mu))]:
                        good=valid&np.isfinite(tval)
                        covered=good&(ci[:,0]<=tval)&(tval<=ci[:,1])
                        lo,hi=wilson(int(covered.sum()),p['M'])
                        primary=((method in ('conditional_percentile','conditional_sandwich_t'))==(target=='fitted_policy'))
                        a=dict(condition=f'EP-{cohort}-{variant}',cohort=cohort,scorer=variant,metric=metric,method=method,target=target,
                            comparison_role='target_matched' if primary else 'cross_target_diagnostic',
                            planned=p['M'],available=int(good.sum()),covered=int(covered.sum()),
                            coverage_planned_pct=100*covered.sum()/p['M'],coverage_available_pct=100*covered.sum()/good.sum() if good.any() else np.nan,
                            wilson_low_pct=lo,wilson_high_pct=hi,mean_width_pp=np.nanmean(width),
                            midpoint_sd_pp=np.nanstd(mid,ddof=1)*100,
                            width_ratio=np.nanmean(width)/(3.919927969080108*np.nanstd(point[:,k],ddof=1)*100))
                        if target=='procedure_average':
                            for direction,label in [(-1,'minus'),(1,'plus')]:
                                shifted=mu+direction*3*se
                                a[f'reference_{label}3se_coverage_pct']=100*np.sum(valid&(ci[:,0]<=shifted)&(shifted<=ci[:,1]))/p['M']
                        coverage.append(a)
                    disp=mid-point[:,k]
                    keep=np.isfinite(disp)&np.isfinite(point[:,k])
                    cov=np.cov(point[keep,k],disp[keep],ddof=1)[0,1] if keep.sum()>1 else np.nan
                    diagrows.append(dict(condition=f'EP-{cohort}-{variant}',metric=metric,method=method,
                       point_sd_pp=np.std(point[keep,k],ddof=1)*100,midpoint_sd_pp=np.nanstd(mid,ddof=1)*100,
                       displacement_sd_pp=np.nanstd(disp,ddof=1)*100,covariance_point_displacement_pp2=cov*10000))
                bd=arrays['bca_diagnostics'][:,k]
                bd_available=bd[bd[:,0]==0]
                for status in range(6):
                    bca.append(dict(condition=f'EP-{cohort}-{variant}',metric=metric,status=status,
                         count=int(np.sum(bd[:,0]==status)),planned=p['M'],
                         extreme_tail_count=int(np.nansum(bd_available[:,5])) if status==0 else '',
                         z0_mean=float(np.nanmean(bd_available[:,1])) if status==0 else '',
                         acceleration_mean=float(np.nanmean(bd_available[:,2])) if status==0 else '',
                         mean_bootstrap_tie_fraction=float(np.nanmean(bd_available[:,6])) if status==0 else ''))
            for stage,si in [('development',0),('evaluation',1)]:
                values=arrays['counts'][:,si]
                counts.append(dict(condition=f'EP-{cohort}-{variant}',stage=stage,groups=p['groups'][cohort][si],
                    mean_trials=float(values.sum(axis=1).mean()),min_trials=int(values.sum(axis=1).min()),max_trials=int(values.sum(axis=1).max()),
                    mean_failures=float(values[:,0].mean()),mean_successes=float(values[:,1].mean())))
    for name,rows in [('coverage.csv',coverage),('point-decomposition.csv',summaries),('bca-availability.csv',bca),
                      ('sample-counts.csv',counts),('centering-diagnostics.csv',diagrows)]:csvout(name,rows)
    result=dict(status='PASS',M=p['M'],B=p['B'],conditions=4,metrics=2,methods=5,targets=2,
       coverage_rows=len(coverage),all_outer_records=4000,
       environment={'python':sys.executable,'python_version':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'storage':'E: SATA HDD',
                    'threads':{k:os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}},
       frozen_protocol_sha256=e.sha(HERE/'frozen-protocol.json'),source_sha256=e.sha(e.SOURCE))
    e.dump(HERE/'completion.json',result)
    print(json.dumps(result,indent=2),flush=True)

def run(workers):
    p=check_protocol();start=time.perf_counter();data=e.load_inputs()
    reference_run(data)
    del data
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(run_cohort,['RL','RE']):print('COHORT COMPLETE',result,flush=True)
    summarize()
    print('TOTAL_SECONDS',time.perf_counter()-start,flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['all','summarize']);ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
    if a.action=='all':run(a.workers)
    else:summarize()
