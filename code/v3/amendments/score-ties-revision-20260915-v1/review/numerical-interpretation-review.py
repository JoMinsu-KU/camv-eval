"""Bounded saved-output arithmetic audit; never generates scientific samples."""
from pathlib import Path
import csv, json, hashlib
import numpy as np
from scipy.stats import norm

ROOT=Path(__file__).resolve().parents[1]
S=ROOT/'scorer/results-v1'; T=ROOT/'simulation/summary-v1'
counts={}; max_error=0.
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def near(a,b):
    global max_error
    a,b=np.asarray(a,float),np.asarray(b,float)
    # Independent column reductions can differ from axis-0 reductions over
    # 65536 references at ~1e-14; allow 1e-12 without rounding any science data.
    np.testing.assert_allclose(a,b,rtol=0,atol=1e-12,equal_nan=True)
    if a.size:max_error=max(max_error,float(np.nanmax(np.abs(a-b))))
def inter(a):return (a[...,1,:]-a[...,3,:])-(a[...,0,:]-a[...,2,:])
def ci(a):return np.quantile(a,[.025,.975],method='linear')
methods=('joint_pooled','joint_pair','late_pooled','late_pair')
metrics=('false_success_rate','success_recall')
scorers={}
for p in sorted(S.glob('*/paired-bootstrap.npz')):
    with np.load(p,allow_pickle=False) as z:
        scorers[p.parent.name]=tuple(z[k].mean(axis=1) for k in ('point_by_scorer_seed','conditional_by_scorer_seed','refit_by_scorer_seed'))
for row in rows(S/'operating.csv'):
    p,c,r=scorers[row['case']];v=('bare','space').index(row['scorer']);j=methods.index(row['method']);k=metrics.index(row['metric'])
    near([float(row[x]) for x in ('estimate','conditional_lower','conditional_upper','refit_lower','refit_upper')],np.r_[p[v,j,k],ci(c[v,:,j,k]),ci(r[v,:,j,k])])
counts['scorer_operating_rows']=64
for row in rows(S/'interactions.csv'):
    p,c,r=map(inter,scorers[row['case']]);k=metrics.index(row['metric'])
    if row['scorer']=='space_minus_bare':p,c,r=p[1]-p[0],c[1]-c[0],r[1]-r[0]
    else:v=('bare','space').index(row['scorer']);p,c,r=p[v],c[v],r[v]
    near([float(row[x]) for x in ('estimate','conditional_lower','conditional_upper','refit_lower','refit_upper','basic_lower','basic_upper')],np.r_[p[k],ci(c[:,k]),ci(r[:,k]),2*p[k]-ci(r[:,k])[::-1]])
    assert int(row['conditional_valid'])==np.isfinite(c[:,k]).sum()==2000
    assert int(row['refit_valid'])==np.isfinite(r[:,k]).sum()==2000
counts['scorer_interaction_rows']=24
thresholds=rows(S/'thresholds.csv');assert len(thresholds)==228 and all(np.isfinite(float(r['threshold'])) for r in thresholds)
counts['finite_empirical_threshold_entries']=228
refs={(r['condition'],r['metric']):r for r in rows(T/'reference-targets.csv')}
arrays={};validfits=0;rawprobes=0
for p in sorted(T.glob('*-compact.npz')):
    cid=p.name.removesuffix('-compact.npz')
    with np.load(p,allow_pickle=False) as z:arrays[cid]={k:z[k] for k in z.files}
    a=arrays[cid];assert a['point'].shape==(1000,2)
    validfits+=int(np.isfinite(a['point_thresholds']).all(axis=1).sum())
    near(a['point'],inter(a['point_policy']));near(a['fitted_truth'],inter(a['population_policy']))
    with np.load(ROOT/'simulation/replay-v1'/p.name,allow_pickle=False) as z:
        for k,v in a.items():np.testing.assert_array_equal(v,z[k])
    with np.load(ROOT/'simulation/run'/cid/'outer/000000.npz',allow_pickle=False) as z:
        for i in (0,12,24):
            for k in a:np.testing.assert_array_equal(a[k][i],z[k][i])
            for k in (0,1):
                c=z['conditional_draws'][i,:,k];r=z['refit_draws'][i,:,k];point=z['point'][i,k]
                near(z['intervals'][i,:3,k],np.stack((ci(c),ci(r),2*point-ci(r)[::-1])))
                near(z['pvalues'][i,:,k],[(1+np.sum(np.abs(v-point)>=abs(point)))/(len(v)+1) for v in (c,r)])
            rawprobes+=1
    if cid.startswith('A_'):
        ref=[]
        for rp in sorted((ROOT/'simulation/run'/cid/'reference').glob('*.npz')):
            with np.load(rp,allow_pickle=False) as z:ref.append(z['values'])
        ref=np.concatenate(ref);assert ref.shape==(65536,2) and np.isfinite(ref).all()
        for k,m in enumerate(metrics):near([float(refs[cid,m][x]) for x in ('truth','reference_mcse')],[ref[:,k].mean(),ref[:,k].std(ddof=1)/np.sqrt(len(ref))])
assert validfits==8000
counts.update(finite_simulation_point_fits=validfits,raw_outer_record_probes=rawprobes,reference_datasets=4*65536)
algs=('conditional_percentile','refit_percentile','refit_basic','cluster_sandwich_t')
for row in rows(T/'coverage.csv'):
    a=arrays[row['condition']];k=metrics.index(row['metric']);j=algs.index(row['algorithm']);lo,hi=a['intervals'][:,j,k].T
    tr=a['fitted_truth'][:,k] if row['target']=='fitted' else np.full(1000,float(refs[row['condition'],row['metric']]['truth']))
    valid=np.isfinite(lo)&np.isfinite(hi)&np.isfinite(tr);event=(lo<=tr)&(tr<=hi)&valid;N=int(valid.sum());K=int(event.sum());prob=K/N
    assert N==int(row['available'])==1000 and K==int(row['covered'])
    near([float(row[x]) for x in ('rate','mcse','mean_width')],[prob,np.sqrt(prob*(1-prob)/N),np.mean((hi-lo)[valid])])
    z=norm.ppf(.975);den=1+z*z/N;mid=(prob+z*z/(2*N))/den;half=z*np.sqrt(prob*(1-prob)/N+z*z/(4*N*N))/den
    near([float(row[x]) for x in ('wilson_lower','wilson_upper')],[mid-half,mid+half])
    if row['target']=='procedure':
        mu=float(refs[row['condition'],row['metric']]['truth']);se=float(refs[row['condition'],row['metric']]['reference_mcse'])
        for sign,label in ((-1,'minus'),(1,'plus')):near(float(row['coverage_reference_'+label+'_3mcse']),np.mean((lo<=mu+sign*3*se)&(mu+sign*3*se<=hi)))
counts['coverage_rows']=128
for row in rows(T/'centered-tests.csv'):
    a=arrays[row['condition']];k=metrics.index(row['metric']);j=('conditional','refit').index(row['algorithm']);pv=a['pvalues'][:,j,k];assert np.isfinite(pv).all();K=int((pv<=.05).sum())
    assert K==int(row['rejected']);near(float(row['rate']),K/1000)
counts['test_rows']=32
for row in rows(T/'centers.csv'):
    a=arrays[row['condition']];k=metrics.index(row['metric']);p=a['point'][:,k];pm=a['intervals'][:,1,k].mean(axis=-1);bm=a['intervals'][:,2,k].mean(axis=-1);shift=pm-p;mu=float(refs[row['condition'],row['metric']]['truth'])
    vals=[p.mean(),p.mean()-mu,p.std(ddof=1),pm.std(ddof=1),bm.std(ddof=1),shift.mean(),np.cov(p,shift,ddof=1)[0,1],np.corrcoef(p,shift)[0,1]]
    fields=('point_mean','point_bias','point_sd','percentile_midpoint_sd','basic_midpoint_sd','midpoint_shift_mean','point_shift_covariance','point_shift_correlation')
    near([float(row[x]) for x in fields],vals)
counts['center_rows']=16
for p in T.glob('*.csv'):assert p.read_bytes()==(ROOT/'simulation/replay-v1'/p.name).read_bytes()
print(json.dumps({'status':'PASS','counts':counts,'maximum_absolute_numeric_difference':max_error,'source_changes':0,'new_scientific_samples':0},indent=2))
