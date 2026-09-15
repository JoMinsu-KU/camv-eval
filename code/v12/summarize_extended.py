from pathlib import Path
import csv,json,hashlib
import numpy as np
import extended_core as x
import review_core as c
R=Path(__file__).parent;OUT=R/'summary';OUT.mkdir(exist_ok=True)
assert json.loads((R/'run/completion.json').read_text())['status']=='COMPLETE'
def writecsv(name,rows):
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
def wilson(k,n):
    z=1.959963984540054;p=k/n;d=1+z*z/n
    m=(p+z*z/(2*n))/d;w=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return 100*(m-w),100*(m+w)
def arrays(folder,keys):
    bins={k:[] for k in keys};count=0
    for p in sorted(folder.glob('*.npz')):
        receipt=json.loads(p.with_suffix('.json').read_text());assert receipt['start']==count
        assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['sha256']
        with np.load(p) as z:
            for k in keys:bins[k].append(z[k])
        count=receipt['stop']
    return {k:np.concatenate(v) for k,v in bins.items()}
coverage=[];refs=[];reject=[];counts=[];diag=[]
for law in x.conditions():
    folder=R/'run'/law['id']
    a=arrays(folder/'outer',['point','fitted_truth','intervals','pvalues','counts','bca_diagnostics'])
    assert len(a['point'])==1000
    if law['exact_zero']:mu=np.zeros(2);se=np.zeros(2);refn=0
    else:
        ref=arrays(folder/'reference',['values'])['values'];assert len(ref)==16384
        mu=ref.mean(axis=0);se=ref.std(axis=0,ddof=1)/np.sqrt(len(ref));refn=len(ref)
    for y,metric in enumerate(['FSR','recall']):
        refs.append(dict(condition=law['id'],metric=metric,target_pp=100*mu[y],mcse_pp=100*se[y],reference_n=refn,exact=law['exact_zero']))
        for j,method in enumerate(c.METHODS):
            bounds=a['intervals'][:,j,y,:];valid=np.isfinite(bounds).all(axis=1);width=bounds[:,1]-bounds[:,0]
            for target in ['fitted_policy','procedure_average']:
                truth=a['fitted_truth'][:,y] if target=='fitted_policy' else np.repeat(mu[y],1000)
                yes=valid&(bounds[:,0]<=truth)&(truth<=bounds[:,1]);k=int(yes.sum());lo,hi=wilson(k,1000)
                shifts=[int(np.sum(valid&(bounds[:,0]<=truth+shift)&(truth+shift<=bounds[:,1]))) for shift in [-3*se[y],3*se[y]]]
                coverage.append(dict(condition=law['id'],metric=metric,method=method,target=target,planned=1000,available=int(valid.sum()),covered=k,
                                     coverage_planned_pct=k/10,coverage_available_pct=100*k/valid.sum(),wilson_low_pct=lo,wilson_high_pct=hi,
                                     mean_width_pp=100*np.mean(width[valid]),reference_minus3se_coverage_pct=shifts[0]/10,reference_plus3se_coverage_pct=shifts[1]/10))
        for j,label in enumerate(['conditional','refit']):
            p=a['pvalues'][:,j,y];valid=np.isfinite(p);k=int(np.sum(p[valid]<=.05));lo,hi=wilson(k,1000)
            reject.append(dict(condition=law['id'],metric=metric,test=label,planned=1000,available=int(valid.sum()),rejections=k,rejection_pct=k/10,wilson_low_pct=lo,wilson_high_pct=hi,interpretation='null Type I error for this structured law' if law['exact_zero'] else 'alternative rejection; post hoc simulation'))
        statuses=a['bca_diagnostics'][:,y,0]
        diag.append(dict(condition=law['id'],metric=metric,available=int(np.sum(statuses==0)),unavailable=int(np.sum(statuses!=0))))
    for stage in [0,1]:
        means=a['counts'][:,stage,:].mean(axis=0)
        counts.append(dict(condition=law['id'],stage=['development','evaluation'][stage],**dict(zip(['mean_trials','mean_groups','mean_failures','mean_successes','mean_failure_groups','mean_success_groups'],means))))
writecsv('coverage.csv',coverage);writecsv('reference-targets.csv',refs);writecsv('rejections.csv',reject);writecsv('group-counts.csv',counts);writecsv('bca-availability.csv',diag)
(OUT/'completion.json').write_text(json.dumps({'status':'COMPLETE','outer_datasets':3000,'reference_datasets':32768,'coverage_rows':len(coverage),'new_model_calls':0},indent=2))
for law in x.conditions():
    for metric in ['FSR','recall']:
        print(json.dumps({'condition':law['id'],'metric':metric,'target':[r for r in refs if r['condition']==law['id'] and r['metric']==metric][0],
                          'coverage':{method:[r['coverage_planned_pct'] for r in coverage if r['condition']==law['id'] and r['metric']==metric and r['method']==method] for method in c.METHODS},
                          'refit_rejection':[r['rejection_pct'] for r in reject if r['condition']==law['id'] and r['metric']==metric and r['test']=='refit'][0]}))
