"""Rebuild all reported summaries from immutable saved interaction draws."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import argparse,csv,hashlib,json,math,sys
import numpy as np
from scipy.stats import norm
import ties_core as t
import numerics as n
HERE=Path(__file__).resolve().parent
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    return x
def dump(p,obj):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(clean(obj),f,indent=2,allow_nan=False)
def csvout(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(clean(rows))
def event(k,N):
    if not N:return {'rate':np.nan,'mcse':np.nan,'wilson_lower':np.nan,'wilson_upper':np.nan}
    p=k/N;z=norm.ppf(.975);den=1+z*z/N;mid=(p+z*z/(2*N))/den;half=z*np.sqrt(p*(1-p)/N+z*z/(4*N*N))/den
    return {'rate':p,'mcse':np.sqrt(p*(1-p)/N),'wilson_lower':mid-half,'wilson_upper':mid+half}
def load_chunks(folder):
    parts={};paths=sorted(folder.glob('*.npz'))
    for p in paths:
        receipt=json.loads(p.with_suffix('.json').read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['sha256']
        with np.load(p,allow_pickle=False) as z:
            for k in z.files:parts.setdefault(k,[]).append(z[k])
    return {k:np.concatenate(v) for k,v in parts.items()}
def summarize(out,replay=False):
    out.mkdir(exist_ok=False);coverage=[];tests=[];centers=[];structure=[];knots=[];refs=[];checks=[]
    algorithms=('conditional_percentile','refit_percentile','refit_basic','cluster_sandwich_t')
    for c in t.conditions():
        a=load_chunks(HERE/'run'/c['id']/'outer');assert a['point'].shape==(1000,2)
        allfit=np.isfinite(a['point_thresholds']).all(axis=1)
        if c['kind']=='N':mu=np.zeros(2);se=np.zeros(2);refvalid=0
        else:
            r=load_chunks(HERE/'run'/c['id']/'reference')['values'];assert r.shape==(65536,2)
            valid=np.isfinite(r).all(axis=1);refvalid=int(valid.sum());mu=r[valid].mean(axis=0);se=r[valid].std(axis=0,ddof=1)/np.sqrt(refvalid)
        for y,metric in enumerate(n.METRICS):
            refs.append(dict(condition=c['id'],metric=metric,truth=mu[y],reference_mcse=se[y],reference_planned=0 if c['kind']=='N' else 65536,reference_valid=refvalid,exact_null=c['kind']=='N'))
            for ai,alg in enumerate(algorithms):
                lo,hi=a['intervals'][:,ai,y,:].T
                for target,tr in [('fitted',a['fitted_truth'][:,y]),('procedure',np.full(1000,mu[y]))]:
                    valid=np.isfinite(lo)&np.isfinite(hi)&np.isfinite(tr);cv=valid&(lo<=tr)&(tr<=hi);N=int(valid.sum());k=int(cv.sum())
                    row=dict(condition=c['id'],metric=metric,algorithm=alg,target=target,planned=1000,available=N,covered=k,**event(k,N),mean_width=float(np.mean((hi-lo)[valid])))
                    if target=='procedure':
                        row['coverage_reference_minus_3mcse']=float(np.mean((lo[valid]<=mu[y]-3*se[y])&(mu[y]-3*se[y]<=hi[valid])))
                        row['coverage_reference_plus_3mcse']=float(np.mean((lo[valid]<=mu[y]+3*se[y])&(mu[y]+3*se[y]<=hi[valid])))
                    coverage.append(row)
            for ai,alg in enumerate(('conditional','refit')):
                p=a['pvalues'][:,ai,y];valid=np.isfinite(p);N=int(valid.sum());k=int(np.sum(p[valid]<=.05))
                tests.append(dict(condition=c['id'],metric=metric,algorithm=alg,event='procedure_null_rejection' if c['kind']=='N' else 'alternative_rejection_power',conditional_cross_target=ai==0,planned=1000,available=N,rejected=k,**event(k,N)))
            x=a['point'][:,y];pm=a['intervals'][:,1,y].mean(axis=-1);bm=a['intervals'][:,2,y].mean(axis=-1);shift=pm-x
            valid=np.isfinite(x)&np.isfinite(pm)&np.isfinite(bm)
            cov=np.cov(x[valid],shift[valid],ddof=1)[0,1]
            corr=np.corrcoef(x[valid],shift[valid])[0,1] if np.std(x[valid])>0 and np.std(shift[valid])>0 else np.nan
            centers.append(dict(condition=c['id'],metric=metric,truth=mu[y],point_mean=float(np.mean(x[valid])),point_bias=float(np.mean(x[valid])-mu[y]),point_sd=float(np.std(x[valid],ddof=1)),percentile_midpoint_sd=float(np.std(pm[valid],ddof=1)),basic_midpoint_sd=float(np.std(bm[valid],ddof=1)),midpoint_shift_mean=float(np.mean(shift[valid])),point_shift_covariance=cov,point_shift_correlation=corr,mean_bootstrap_bias=float(np.nanmean(a['refit_draws'][:,:,y]-x[:,None])),variance_identity_residual=float(np.var(pm[valid],ddof=1)-np.var(bm[valid],ddof=1)-4*cov)))
        # Recompute every reported interval and p-value from the saved draws.
        maxerr=0.
        for i in range(1000):
            for y in (0,1):
                cs=a['conditional_draws'][i,:,y];rs=a['refit_draws'][i,:,y];p=a['point'][i,y]
                expected=np.stack((n.interval(cs),n.interval(rs),n.interval(rs,p,True)))
                np.testing.assert_array_equal(a['intervals'][i,:3,y],expected)
                np.testing.assert_array_equal(a['pvalues'][i,:,y],[n.centered_p(p,cs),n.centered_p(p,rs)])
        np.testing.assert_allclose(a['intervals'][:,1,:,1]-a['intervals'][:,1,:,0],a['intervals'][:,2,:,1]-a['intervals'][:,2,:,0],rtol=0,atol=1e-14,equal_nan=True)
        np.testing.assert_allclose(a['intervals'][:,1].mean(axis=-1)+a['intervals'][:,2].mean(axis=-1),2*a['point'],rtol=0,atol=1e-14,equal_nan=True)
        if replay:
            regenerated=t.outer(c,0)
            for k,v in regenerated.items():np.testing.assert_array_equal(a[k][0],v)
        checks.append(dict(condition=c['id'],point_fits_valid=int(allfit.sum()),outer_records=1000,saved_interval_pvalue_checks=10000,center_identities=True,first_outer_regenerated=replay))
        labels=('dev_trials','eval_trials','dev_positives','eval_positives','dev_group_min','dev_group_max','dev_group_sd','eval_group_min','eval_group_max','eval_group_sd')
        for j,label in enumerate(labels):
            v=a['structure'][:,j];structure.append(dict(condition=c['id'],quantity=label,mean=v.mean(),minimum=v.min(),maximum=v.max()))
        for j in range(8):
            for key in ('positive_empirical_atom','positive_population_atom','development_recall'):
                v=a[key][allfit,j];knots.append(dict(condition=c['id'],policy_threshold=j,quantity=key,valid=len(v),mean=v.mean() if len(v) else np.nan,minimum=v.min() if len(v) else np.nan,maximum=v.max() if len(v) else np.nan))
        compact={k:v for k,v in a.items() if k not in ('conditional_draws','refit_draws')}
        np.savez_compressed(out/(c['id']+'-compact.npz'),**compact)
        print('SUMMARIZED',c['id'],flush=True)
    for file,rows in [('coverage.csv',coverage),('centered-tests.csv',tests),('centers.csv',centers),('group-structure.csv',structure),('threshold-atoms.csv',knots),('reference-targets.csv',refs)]:csvout(out/file,rows)
    dump(out/'checks.json',checks)
    dump(out/'completion.json',{'status':'PASS','conditions':8,'outer_datasets':8000,'coverage_rows':len(coverage),'test_rows':len(tests),'center_rows':len(centers),'all_point_fits_valid':all(r['point_fits_valid']==1000 for r in checks),'first_outer_per_cell_regenerated':replay,'python':sys.executable,'reference_CRN':'Continuous/quantized paired within size law; each reference stream independent of outer streams.'})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--regenerate-first',action='store_true');a=p.parse_args();summarize(a.output,a.regenerate_first)
