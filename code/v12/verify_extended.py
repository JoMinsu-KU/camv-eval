"""Check saved interval formulas, targets, receipts, and deterministic regeneration."""
from pathlib import Path
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import json,hashlib
import numpy as np
import extended_core as x
R=Path(__file__).parent
freeze=json.loads((R/'run/freeze.json').read_text())
for name,digest in freeze['pins'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==digest
rows=0;max_interval_error=0.;decompositions=[]
for law in x.conditions():
    saved=[]
    for p in sorted((R/'run'/law['id']/'outer').glob('*.npz')):
        with np.load(p) as z:
            point=z['point'];ints=z['intervals'];refit=z['refit_draws'];cond=z['conditional_draws'];diag=z['bca_diagnostics'];pvalues=z['pvalues']
            for draw,ci_index in [(cond,0),(refit,1)]:
                expected=np.quantile(draw,[.025,.975],axis=1,method='linear').transpose(1,2,0)
                err=np.nanmax(abs(expected-ints[:,ci_index]));assert err<1e-13;max_interval_error=max(max_interval_error,float(err))
            np.testing.assert_allclose(ints[:,2],2*point[:,:,None]-ints[:,1,:,::-1],atol=1e-13)
            for i in range(len(point)):
                for y in (0,1):
                    for j,draw in enumerate([cond,refit]):
                        v=draw[i,:,y];v=v[np.isfinite(v)]
                        expected=(1+np.sum(abs(v-point[i,y])>=abs(point[i,y])))/(len(v)+1)
                        assert expected==pvalues[i,j,y]
                    if diag[i,y,0]==0:
                        expected=np.quantile(refit[i,:,y],diag[i,y,3:5],method='linear')
                        np.testing.assert_allclose(expected,ints[i,4,y],atol=1e-13)
            rows+=len(point);saved.append((point.copy(),z['fitted_truth'].copy(),ints[:,1].copy()))
    fresh=x.outer(law,0)
    with np.load(R/'run'/law['id']/'outer/000000.npz') as z:
        for key in fresh:np.testing.assert_array_equal(fresh[key],z[key][0])
    point,truth,interval=(np.concatenate([a[j] for a in saved]) for j in range(3))
    for y,metric in enumerate(['FSR','recall']):
        t=100*point[:,y];v=100*truth[:,y];u=t-v;d=100*interval[:,y].mean(axis=-1)-t
        cv=lambda a,b:np.cov(a,b,ddof=1)[0,1]
        decompositions.append(dict(condition=law['id'],metric=metric,point_sd_pp=np.std(t,ddof=1),evaluation_error_sd_pp=np.std(u,ddof=1),development_policy_sd_pp=np.std(v,ddof=1),
                                   covariance_uv_pp2=cv(u,v),development_variance_fraction=np.var(v,ddof=1)/np.var(t,ddof=1),covariance_T_d_pp2=cv(t,d),covariance_evaluation_d_pp2=cv(u,d),covariance_development_d_pp2=cv(v,d),
                                   correlation_evaluation_d=np.corrcoef(u,d)[0,1],correlation_development_d=np.corrcoef(v,d)[0,1]))
assert rows==3000
import csv
with (R/'summary/decomposition.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,list(decompositions[0]));w.writeheader();w.writerows(decompositions)
report={'status':'PASS','outer_datasets_checked':rows,'independently_recomputed':['conditional percentile limits','refit percentile limits','basic reflection','centered p-values','BCa adjusted-quantile endpoints'],'first_outer_regenerated_per_law':True,'max_percentile_endpoint_error':max_interval_error,'frozen_sources_preserved':True}
(R/'summary/verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
