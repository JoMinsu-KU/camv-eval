"""Independent numerical verification of frozen outputs; no new draws or source imports."""
from pathlib import Path
import csv, hashlib, json, math, statistics
import numpy as np
from scipy.stats import norm

BASE=Path(__file__).resolve().parents[1]
SIM=BASE/'simulation'
OUT=Path(__file__).resolve().parent/'numerical-verification.json'
def readcsv(name):
    with (SIM/'summary'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
tables={x:readcsv(x) for x in ('coverage.csv','reference-targets.csv','bca-diagnostics.csv','score-features.csv','rejections.csv','centers.csv')}
checks=0; errors=[]; audit=[]; receipts=0; bca_max=0.; oracle_max=0.; mcse_max=0.
def same(actual,expected,where,atol=2e-10):
    global checks
    checks+=1
    if isinstance(expected,str):
        if expected in ('True','False'):expected=expected=='True'
        else:
            try:expected=float(expected)
            except ValueError:pass
    if isinstance(expected,(str,bool)):
        if actual!=expected:errors.append({'where':where,'actual':actual,'expected':expected})
    elif not np.isclose(actual,expected,rtol=2e-11,atol=atol,equal_nan=True):
        errors.append({'where':where,'actual':float(actual),'expected':float(expected)})
def file_sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
freeze=json.loads((SIM/'run/freeze.json').read_text())
for name,digest in freeze['pins'].items():same(file_sha(SIM/name),digest,'frozen '+name)
methods=['conditional_percentile','refit_percentile','refit_basic','conditional_sandwich_t','refit_BCa']
metrics=['FSR','recall']
z=statistics.NormalDist().inv_cdf(.975)
def wilson(k,n):
    p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den;rad=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return 100*(mid-rad),100*(mid+rad)
def load_all(cond,kind,keys):
    global receipts
    files=sorted((SIM/'run'/cond/kind).glob('*.npz')); data={k:[] for k in keys};starts=[]
    for f in files:
        rec=json.loads(f.with_suffix('.json').read_text());receipts+=1
        same(file_sha(f),rec['sha256'],str(f)+' sha')
        same(rec['condition'],cond,str(f)+' condition');same(rec['kind'],kind,str(f)+' kind')
        same(int(f.stem),rec['start'],str(f)+' start')
        starts.append((rec['start'],rec['stop']))
        with np.load(f,allow_pickle=False) as obj:
            for key in keys:
                arr=obj[key];same(len(arr),rec['stop']-rec['start'],str(f)+' length '+key);data[key].append(arr)
    for i,(a,b) in enumerate(starts):same(a,0 if i==0 else starts[i-1][1],cond+kind+' contiguous')
    return {k:np.concatenate(v,axis=0) for k,v in data.items()}
for cond in freeze['conditions']:
    cid=cond['id']; q=cond['step']; sd=math.sqrt(.75)
    if cond['exact_zero']:mu=np.zeros(2);se=np.zeros(2);reference_n=0
    else:
        ref=load_all(cid,'reference',['values'])['values'];reference_n=len(ref)
        same(reference_n,32768,cid+' reference count')
        mu=np.array([v[np.isfinite(v)].mean() for v in ref.T])
        se=np.array([v[np.isfinite(v)].std(ddof=1)/math.sqrt(np.isfinite(v).sum()) for v in ref.T])
        same(int(np.isfinite(ref).all(axis=1).sum()),32768,cid+' reference valid')
        if cond['separation']==0:same(float(np.max(np.abs(ref[:,0]-ref[:,1]))),0,cid+' reference FSR equals recall',atol=0)
    for y,metric in enumerate(metrics):
        r=next(x for x in tables['reference-targets.csv'] if x['condition']==cid and x['metric']==metric)
        for col,val in dict(target_pp=100*mu[y],reference_mcse_pp=100*se[y],reference_planned=reference_n,reference_available=reference_n,exact_zero=cond['exact_zero'],precision_le_005pp=100*se[y]<=.05).items():same(val,r[col],cid+' '+metric+' '+col)
        mcse_max=max(mcse_max,float(100*se[y]))
    dat=load_all(cid,'outer',['point','point_thresholds','fitted_truth','intervals','pvalues','bca_diagnostics','dev_features','eval_features','refit_draws','conditional_draws','jackknife_dev','jackknife_eval','finite_draw_counts'])
    N=len(dat['point']);same(N,1000,cid+' outer count')
    draws=dat['refit_draws'];pts=dat['point'];ints=dat['intervals'];same(draws.shape[1],999,cid+' B')
    same(int(np.isfinite(draws).sum()),N*999*2,cid+' refit finite');same(int(np.isfinite(dat['conditional_draws']).sum()),N*999*2,cid+' conditional finite')
    # All observed draws are finite: reproduce BCa independently with split jackknife vectors.
    u=[]
    for j in ('jackknife_dev','jackknife_eval'):
        jj=dat[j];nn=jj.shape[1];u.append((jj.mean(axis=1,keepdims=True)-jj)*(nn-1)/nn)
    inf=np.concatenate(u,axis=1)
    aa=(inf**3).sum(axis=1)/(6*((inf**2).sum(axis=1)**1.5))
    rank=((draws<pts[:,None,:]).sum(axis=1)+.5*(draws==pts[:,None,:]).sum(axis=1))/draws.shape[1]
    z0=norm.ppf(rank)
    zz=z0[:,:,None]+norm.ppf([.025,.975])[None,None,:]
    denom=1-aa[:,:,None]*zz
    adjusted=norm.cdf(z0[:,:,None]+zz/denom)
    recalculated=np.full((N,2,2),np.nan)
    for i in range(N):
        for y in range(2):
            if np.isfinite(adjusted[i,y]).all() and np.all(denom[i,y]>0) and adjusted[i,y,0]<=adjusted[i,y,1]:
                # Independent linear order-statistic interpolation rather than calling quantile.
                ordered=np.sort(draws[i,:,y]); loc=adjusted[i,y]*(len(ordered)-1);lo=np.floor(loc).astype(int);hi=np.ceil(loc).astype(int)
                recalculated[i,y]=ordered[lo]+(loc-lo)*(ordered[hi]-ordered[lo])
    err=float(np.nanmax(np.abs(recalculated-ints[:,4])));bca_max=max(bca_max,err);same(err,0,cid+' all BCa bounds',atol=2e-12)
    same(int(np.isfinite(recalculated).all(axis=2).sum()),2000,cid+' BCa available')
    for label,v in [('acceleration',aa),('z0',z0),('adjusted_lower',adjusted[:,:,0]),('adjusted_upper',adjusted[:,:,1])]:
        col={'z0':1,'acceleration':2,'adjusted_lower':3,'adjusted_upper':4}[label]
        same(float(np.max(np.abs(v-dat['bca_diagnostics'][:,:,col]))),0,cid+' '+label,atol=2e-12)
    # Independently reconstruct fitted-policy population tail rates from saved thresholds.
    f=dat['point_thresholds'];t=np.stack((np.repeat(f[:,0,None],3,axis=1),f[:,1:4],np.repeat(f[:,4,None],3,axis=1),f[:,5:8]),axis=1)
    if q:t=q*np.ceil(t/q)
    truth=np.zeros((N,2))
    for y in range(2):
        joint=cond['separation']*y+np.array(cond['offset']);late=np.repeat(cond['separation']*y,3)
        rates=norm.sf((t-np.array([joint,joint,late,late])[None,:,:])/sd).mean(axis=2)
        truth[:,y]=rates[:,1]-rates[:,3]-rates[:,0]+rates[:,2]
    oe=float(np.max(np.abs(truth-dat['fitted_truth'])));oracle_max=max(oracle_max,oe);same(oe,0,cid+' fitted oracle',atol=2e-14)
    if cond['separation']==0:same(float(np.max(np.abs(truth[:,0]-truth[:,1]))),0,cid+' fitted FSR equals recall',atol=0)
    # Every available/planned count, coverage, width, MCSE, Wilson limit, and reference sensitivity.
    for r in (x for x in tables['coverage.csv'] if x['condition']==cid):
        m=methods.index(r['method']);y=metrics.index(r['metric']);iv=ints[:,m,y,:]
        valid=np.isfinite(iv).all(axis=1);target=truth[:,y] if r['target']=='fitted_policy' else np.full(N,mu[y]);valid &=np.isfinite(target)
        k=int(np.sum(valid&(iv[:,0]<=target)&(target<=iv[:,1])));av=int(valid.sum());p=k/av
        low,high=wilson(k,av)
        val=dict(planned=N,available=av,covered=k,coverage_available_pct=100*p,covered_planned_pct=100*k/N,wilson_low_pct=low,wilson_high_pct=high,coverage_mcse_pct=100*math.sqrt(p*(1-p)/av),mean_width_pp=100*np.mean(iv[valid,1]-iv[valid,0]))
        for sign,name in [(-1,'coverage_ref_minus3mcse_pct'),(1,'coverage_ref_plus3mcse_pct')]:
            alt=target if r['target']=='fitted_policy' else target+sign*3*se[y]
            val[name]=100*np.sum(valid&(iv[:,0]<=alt)&(alt<=iv[:,1]))/av
        for col,actual in val.items():same(actual,r[col],cid+' '+r['metric']+' '+r['method']+' '+r['target']+' '+col)
    # Zero exclusion and centered resampling tests are checked by distinct computations.
    recomputed_p=[]
    for dv in (dat['conditional_draws'],draws):
        recomputed_p.append((1+(np.abs(dv-pts[:,None,:])>=np.abs(pts[:,None,:])).sum(axis=1))/(dv.shape[1]+1))
    pvs=np.stack(recomputed_p,axis=1)
    same(float(np.max(np.abs(pvs-dat['pvalues']))),0,cid+' pvalue arrays',atol=0)
    for r in (x for x in tables['rejections.csv'] if x['condition']==cid):
        y=metrics.index(r['metric']);pr=r['procedure']
        if pr.endswith('_zero_exclusion'):
            m=methods.index(pr.removesuffix('_zero_exclusion'));iv=ints[:,m,y,:];valid=np.isfinite(iv).all(axis=1);event=(iv[:,0]>0)|(iv[:,1]<0)
        else:
            index=0 if pr.startswith('conditional') else 1;v=pvs[:,index,y];valid=np.isfinite(v);event=v<=.05
        av=int(valid.sum());k=int(np.sum(valid&event));lo,hi=wilson(k,av)
        for col,val in dict(planned=N,available=av,rejected=k,rate_pct=100*k/av,wilson_low_pct=lo,wilson_high_pct=hi).items():same(val,r[col],cid+' '+r['metric']+' '+pr+' '+col)
    for r in (x for x in tables['bca-diagnostics.csv'] if x['condition']==cid):
        y=metrics.index(r['metric']);dg=dat['bca_diagnostics'][:,y,:];available=dg[:,0]==0
        extr=(adjusted[:,y,0]<=.001)|(adjusted[:,y,1]>=.999)
        vals=dict(planned=N,available=int(available.sum()),extreme_adjusted_tails=int(extr.sum()),mean_tie_rank_fraction=float(np.mean(draws[:,:,y]==pts[:,None,y])),acceleration_mean=float(aa[:,y].mean()),acceleration_min=float(aa[:,y].min()),acceleration_max=float(aa[:,y].max()),min_lower_probability=float(adjusted[:,y,0].min()),max_upper_probability=float(adjusted[:,y,1].max()))
        vals.update({f'unavailable_reason_{i}':int((dg[:,0]==i).sum()) for i in range(1,6)})
        for col,val in vals.items():same(val,r[col],cid+' '+r['metric']+' BCa '+col)
    for r in (x for x in tables['score-features.csv'] if x['condition']==cid):
        j=['Joint','Late'].index(r['method']);df=dat['dev_features' if r['split']=='development' else 'eval_features']
        vals=dict(mean_sample_pair_auc=float(df[:,j].mean()),mean_duplicate_excess_pct=float(100*df[:,j+2].mean()),mean_failure_groups=float(df[:,4].mean()),mean_success_groups=float(df[:,5].mean()),mean_pair_tie_probability_pct=float(100*df[:,j+6].mean()),mean_tied_membership_pct=float(100*df[:,j+8].mean()))
        offs=np.array(cond['offset']) if j==0 else np.zeros(3);delta=cond['separation']
        if q==0:
            pair=norm.cdf(delta/(math.sqrt(2)*sd));pool=np.mean(norm.cdf((delta+offs[:,None]-offs[None,:])/(math.sqrt(2)*sd)))
        else:
            grid=np.arange(math.floor((offs.min()-13*sd)/q),math.ceil((offs.max()+delta+13*sd)/q)+1)*q
            m0=norm.cdf((grid[:,None]+q-offs)/sd)-norm.cdf((grid[:,None]-offs)/sd)
            m1=norm.cdf((grid[:,None]+q-offs-delta)/sd)-norm.cdf((grid[:,None]-offs-delta)/sd)
            pair=np.mean(np.sum(m1*(m0.cumsum(axis=0)-.5*m0),axis=0))
            m0=m0.mean(axis=1);m1=m1.mean(axis=1);pool=np.sum(m1*(m0.cumsum()-.5*m0))
        vals.update(population_mean_pair_auc=float(pair),population_pooled_auc=float(pool),separation=delta,quantization_step=q,continuous_pair_auc=norm.cdf(delta/(math.sqrt(2)*sd)))
        for col,val in vals.items():same(val,r[col],cid+' '+r['split']+' '+r['method']+' '+col)
    for r in (x for x in tables['centers.csv'] if x['condition']==cid):
        m=methods.index(r['method']);y=metrics.index(r['metric']);iv=ints[:,m,y];valid=np.isfinite(iv).all(axis=1);mid=iv.mean(axis=1);p=pts[:,y]
        vals=dict(available=int(valid.sum()),point_sd_pp=float(p[valid].std(ddof=1)*100),center_sd_pp=float(mid[valid].std(ddof=1)*100),point_bias_pp=float((p[valid]-mu[y]).mean()*100),midpoint_bias_pp=float((mid[valid]-mu[y]).mean()*100),point_displacement_correlation=float(np.corrcoef(p[valid],(mid-p)[valid])[0,1]))
        for col,val in vals.items():same(val,r[col],cid+' '+r['metric']+' '+r['method']+' '+col)
    bca=ints[:,4,0];bc=(bca[:,0]<=mu[0])&(mu[0]<=bca[:,1]); condcov=(ints[:,0,0,0]<=truth[:,0])&(truth[:,0]<=ints[:,0,0,1])
    audit.append(dict(condition=cid,fsr_target_pp=float(mu[0]*100),reference_mcse_pp=float(se[0]*100),bca_fsr_covered=int(bc.sum()),conditional_fitted_fsr_covered=int(condcov.sum()),bca_fsr_extreme_tails=int(((adjusted[:,0,0]<=.001)|(adjusted[:,0,1]>=.999)).sum())))
    print(json.dumps({'condition':cid,'checks':checks,'errors':len(errors)}),flush=True)

output=dict(status='PASS' if not errors else 'CHECK_FAILED',checks=checks,chunk_receipts_checked=receipts,outer_datasets=8000,reference_datasets=7*32768,new_draws=0,new_model_calls=0,source_modules_imported=False,BCa_max_absolute_bound_difference=bca_max,oracle_max_absolute_difference=oracle_max,maximum_reference_mcse_pp=mcse_max,selected_counts=audit,errors=errors,input_summary_sha256={f:file_sha(SIM/'summary'/f) for f in tables},verified_freeze_sha256=file_sha(SIM/'run/freeze.json'))
with OUT.open('x',encoding='utf-8') as f:json.dump(output,f,indent=2,allow_nan=False)
print(json.dumps({'status':output['status'],'checks':checks,'errors':len(errors),'report':str(OUT)}),flush=True)
