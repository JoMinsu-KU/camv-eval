"""Independent endpoint reconstruction and paired summaries from frozen tail outputs."""
from pathlib import Path
import csv,hashlib,json,math,statistics
import numpy as np
from scipy.stats import norm
HERE=Path(__file__).resolve().parent
ROOT=HERE/'tail-check-v2';OUT=ROOT/'summary';COND='H065_Q125'
METHODS=('conditional_percentile','refit_percentile','refit_basic','conditional_sandwich_t','refit_BCa')
METRICS=('FSR','recall');errors=[];checks=0;max_bca_error=0.
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(v,label):
    global checks
    checks+=1
    if not v:errors.append(label)
def load(root):
    chunks=[];end=0
    for p in sorted(root.glob('*.npz')):
        receipt=json.loads(p.with_suffix('.json').read_text())
        check(sha(p)==receipt['sha256'],str(p)+' hash')
        check(receipt['start']==end,str(p)+' contiguous start');end=receipt['stop']
        with np.load(p,allow_pickle=False) as z:chunks.append({k:z[k] for k in z.files})
    check(end==1000,str(root)+' full index range')
    return {k:np.concatenate([r[k] for r in chunks]) for k in chunks[0]}
def outcsv(name,rows):
    with (OUT/name).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def wilson(k,n):
    z=statistics.NormalDist().inv_cdf(.975);p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den;rad=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [100*(mid-rad),100*(mid+rad)]
def linear_quantile(v,p):
    x=np.sort(v[np.isfinite(v)]);at=(len(x)-1)*np.array(p);lo=np.floor(at).astype(int);hi=np.ceil(at).astype(int)
    return x[lo]+(at-lo)*(x[hi]-x[lo])
def paired(a,b,valid):
    aa=a[valid];bb=b[valid];d=bb.astype(float)-aa.astype(float);se=float(d.std(ddof=1)/math.sqrt(len(d)))
    return dict(paired_available=int(valid.sum()),change_pp=float(d.mean()*100),paired_mcse_pp=se*100,
                paired_normal_low_pp=float(100*(d.mean()-1.959963984540054*se)),paired_normal_high_pp=float(100*(d.mean()+1.959963984540054*se)),
                false_to_true=int(np.sum(~aa&bb)),true_to_false=int(np.sum(aa&~bb)))

completion=json.loads((ROOT/'completion.json').read_text());check(completion['status']=='COMPLETE','completed execution')
freeze=json.loads((ROOT/'freeze.json').read_text())
for name,digest in freeze['pins'].items():check(sha(HERE/name)==digest,'frozen '+name)
check(sha(HERE/'summary/reference-targets.csv')==freeze['original_summary_reference_sha256'],'original reference preserved')
with (HERE/'summary/reference-targets.csv').open(encoding='utf-8-sig') as f:refs={r['metric']:r for r in csv.DictReader(f) if r['condition']==COND}
mu=np.array([float(refs[m]['target_pp'])/100 for m in METRICS]);mcse=np.array([float(refs[m]['reference_mcse_pp'])/100 for m in METRICS])
old=load(HERE/'run'/COND/'outer');new=load(ROOT)
for key in ('point','point_policy','point_thresholds','fitted_truth','jackknife_dev','jackknife_eval','dev_features','eval_features'):
    check(np.array_equal(old[key],new[key],equal_nan=True),'identity '+key)
for key in ('refit_draws','conditional_draws'):check(np.array_equal(old[key],new[key][:,:999],equal_nan=True),'exact combined prefix '+key)
check(bool(new['integer_prefix_checked'].all()),'all integer prefixes verified')
check(bool(new['combined_float_prefix_exact'].all()),'all combined prefixes verified')
check(float(new['raw_prefix_max_absolute_difference'].max())<=2e-15,'raw regenerated numerical prefix tolerance')
check(np.array_equal(old['intervals'][:,3],new['intervals'][:,3],equal_nan=True),'sandwich exactly unchanged')
N=len(new['point']);check(N==1000,'paired N1000')

# Reconstruct all non-sandwich endpoints using no production-module functions.
for label,data in [('B999',old),('B4999',new)]:
    B=data['refit_draws'].shape[1];p=data['point'];draw=data['refit_draws']
    inf=[]
    for key in ('jackknife_dev','jackknife_eval'):
        j=data[key];nn=j.shape[1];inf.append((j.mean(axis=1,keepdims=True)-j)*(nn-1)/nn)
    inf=np.concatenate(inf,axis=1);acc=(inf**3).sum(axis=1)/(6*(inf**2).sum(axis=1)**1.5)
    rank=((draw<p[:,None,:]).sum(axis=1)+.5*(draw==p[:,None,:]).sum(axis=1))/B
    z0=norm.ppf(rank);shift=z0[:,:,None]+norm.ppf([.025,.975])[None,None,:];denom=1-acc[:,:,None]*shift
    adjusted=norm.cdf(z0[:,:,None]+shift/denom)
    err=0.;diagerr=0.
    for i in range(N):
        for y in range(2):
            r=draw[i,:,y];co=data['conditional_draws'][i,:,y];ends=linear_quantile(r,[.025,.975])
            check(np.max(np.abs(data['intervals'][i,0,y]-linear_quantile(co,[.025,.975])))<2e-13,label+' conditional '+str(i)+METRICS[y])
            check(np.max(np.abs(data['intervals'][i,1,y]-ends))<2e-13,label+' percentile '+str(i)+METRICS[y])
            check(np.max(np.abs(data['intervals'][i,2,y]-(2*p[i,y]-ends[::-1])))<2e-13,label+' basic '+str(i)+METRICS[y])
            valid=np.isfinite(adjusted[i,y]).all() and np.all(denom[i,y]>0) and adjusted[i,y,0]<=adjusted[i,y,1]
            check(valid==np.isfinite(data['intervals'][i,4,y]).all(),label+' BCa availability '+str(i)+METRICS[y])
            if valid:err=max(err,float(np.max(np.abs(data['intervals'][i,4,y]-linear_quantile(r,adjusted[i,y])))))
    check(err<2e-12,label+' all BCa bounds');max_bca_error=max(max_bca_error,err)
    extreme=(adjusted[:,:,0]<=1/(B+1))|(adjusted[:,:,1]>=B/(B+1))
    check(np.array_equal(extreme,data['bca_diagnostics'][:,:,5].astype(bool)),label+' all BCa extreme flags')
    check(np.max(np.abs(adjusted-data['bca_diagnostics'][:,:,3:5]))<2e-13,label+' all BCa adjusted tails')
    check(np.max(np.abs(acc-data['bca_diagnostics'][:,:,2]))<2e-13,label+' all BCa acceleration')
    for m,key in enumerate(('conditional_draws','refit_draws')):
        dv=data[key];check(np.isfinite(dv).all(),label+' finite '+key)
        pv=(1+(np.abs(dv-p[:,None,:])>=np.abs(p[:,None,:])).sum(axis=1))/(B+1)
        check(np.array_equal(pv,data['pvalues'][:,m]),label+' centered pvalues '+key)

OUT.mkdir(exist_ok=False)
coverage=[];endpoints=[];decisions=[];tails=[]
for y,metric in enumerate(METRICS):
    for m,method in enumerate(METHODS):
        a=old['intervals'][:,m,y];b=new['intervals'][:,m,y];av=np.isfinite(a).all(axis=1);bv=np.isfinite(b).all(axis=1);both=av&bv
        for target,truth in [('fitted_policy',old['fitted_truth'][:,y]),('procedure_average',np.repeat(mu[y],N))]:
            e0=av&np.isfinite(truth);e1=bv&np.isfinite(truth);eligible=e0&e1
            h0=e0&(a[:,0]<=truth)&(truth<=a[:,1]);h1=e1&(b[:,0]<=truth)&(truth<=b[:,1])
            row=dict(condition=COND,metric=metric,method=method,target=target,planned=N,
                     old_available=int(e0.sum()),new_available=int(e1.sum()),old_covered=int(h0.sum()),new_covered=int(h1.sum()),
                     old_coverage_pct=100*h0.sum()/e0.sum(),new_coverage_pct=100*h1.sum()/e1.sum(),
                     old_covered_planned_pct=100*h0.sum()/N,new_covered_planned_pct=100*h1.sum()/N,
                     old_wilson_low_pct=wilson(int(h0.sum()),int(e0.sum()))[0],old_wilson_high_pct=wilson(int(h0.sum()),int(e0.sum()))[1],
                     new_wilson_low_pct=wilson(int(h1.sum()),int(e1.sum()))[0],new_wilson_high_pct=wilson(int(h1.sum()),int(e1.sum()))[1],
                     **paired(h0,h1,eligible))
            for sign,label in [(-1,'minus'),(1,'plus')]:
                t=truth+sign*3*mcse[y] if target=='procedure_average' else truth
                row[f'new_coverage_ref_{label}3mcse_pct']=100*np.sum(e1&(b[:,0]<=t)&(t<=b[:,1]))/e1.sum()
            coverage.append(row)
        w0=a[:,1]-a[:,0];w1=b[:,1]-b[:,0]
        endpoints.append(dict(condition=COND,metric=metric,method=method,paired_available=int(both.sum()),
              old_mean_width_pp=float(w0[av].mean()*100),new_mean_width_pp=float(w1[bv].mean()*100),
              mean_width_change_pp=float((w1-w0)[both].mean()*100),width_change_mcse_pp=float((w1-w0)[both].std(ddof=1)/math.sqrt(both.sum())*100),
              mean_lower_change_pp=float((b[:,0]-a[:,0])[both].mean()*100),mean_upper_change_pp=float((b[:,1]-a[:,1])[both].mean()*100),
              mean_absolute_lower_change_pp=float(np.abs(b[:,0]-a[:,0])[both].mean()*100),mean_absolute_upper_change_pp=float(np.abs(b[:,1]-a[:,1])[both].mean()*100),
              max_absolute_endpoint_change_pp=float(np.abs(b-a)[both].max()*100)))
        hit0=av&((a[:,0]>0)|(a[:,1]<0));hit1=bv&((b[:,0]>0)|(b[:,1]<0))
        decisions.append(dict(condition=COND,metric=metric,procedure=method+'_zero_exclusion',old_rejected=int(hit0.sum()),new_rejected=int(hit1.sum()),
                old_rate_pct=100*hit0.sum()/av.sum(),new_rate_pct=100*hit1.sum()/bv.sum(),**paired(hit0,hit1,both)))
    for m,method in enumerate(('conditional_centered','refit_centered')):
        a=old['pvalues'][:,m,y];b=new['pvalues'][:,m,y];av=np.isfinite(a);bv=np.isfinite(b);h0=av&(a<=.05);h1=bv&(b<=.05)
        decisions.append(dict(condition=COND,metric=metric,procedure=method,old_rejected=int(h0.sum()),new_rejected=int(h1.sum()),
             old_rate_pct=100*h0.sum()/av.sum(),new_rate_pct=100*h1.sum()/bv.sum(),**paired(h0,h1,av&bv)))
    for B,data in [(999,old),(4999,new)]:
        dg=data['bca_diagnostics'][:,y];av=dg[:,0]==0
        tails.append(dict(condition=COND,metric=metric,B=B,available=int(av.sum()),extreme_adjusted_tails=int(dg[av,5].sum()),
             extreme_pct=float(dg[av,5].mean()*100),min_lower_probability=float(dg[av,3].min()),max_upper_probability=float(dg[av,4].max()),
             mean_bias_correction=float(dg[av,1].mean()),mean_acceleration=float(dg[av,2].mean()),mean_tie_fraction=float(dg[av,6].mean()),
             lower_quantile_resolution=1/(B+1),upper_quantile_resolution=B/(B+1)))
outcsv('paired-coverage.csv',coverage);outcsv('paired-endpoints.csv',endpoints);outcsv('paired-decisions.csv',decisions);outcsv('bca-tail-diagnostics.csv',tails)
report=dict(status='PASS' if not errors else 'FAILED',checks=checks,errors=errors,paired_outer_datasets=N,
       old_B=999,new_B=4999,original_float_prefix_exact=True,all_integer_prefix_checks_passed=bool(new['integer_prefix_checked'].all()),
       raw_regenerated_prefix_max_absolute_difference=float(new['raw_prefix_max_absolute_difference'].max()),
       raw_regenerated_prefix_mismatches=int(new['raw_prefix_mismatch_counts'].sum()),
       raw_prefix_mismatch_counts_conditional_FSR_recall=new['raw_prefix_mismatch_counts'][:,0,:].sum(axis=0).tolist(),
       raw_prefix_mismatch_counts_refit_FSR_recall=new['raw_prefix_mismatch_counts'][:,1,:].sum(axis=0).tolist(),
       reconstructed_BCa_max_bound_error=max_bca_error,reference_reused=True,new_model_calls=0,
       source_imports_used_for_independent_verification=False,
       original_reference_sha256=sha(HERE/'summary/reference-targets.csv'),freeze_sha256=sha(ROOT/'freeze.json'),
       summary_sha256={p.name:sha(p) for p in OUT.glob('*.csv')})
with (OUT/'validation.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False)
lines=['# Paired finite-B sensitivity: H065_Q125','',
       'Post hoc numerical sensitivity using the same 1,000 outer datasets and reference target. B=4,999 retains the exact saved B=999 floating-point prefix and adds 4,000 paired bootstrap replicates per outer dataset. Original B=999 results remain unchanged.','',
       '| Metric | Interval | Procedure-average coverage: B999 → B4999 | Paired change (MCSE), pp | Mean width: B999 → B4999, pp |',
       '|---|---|---|---|---|']
for row in coverage:
    if row['target']!='procedure_average':continue
    e=next(x for x in endpoints if x['metric']==row['metric'] and x['method']==row['method'])
    lines.append(f"| {row['metric']} | {row['method']} | {row['old_coverage_pct']:.1f} → {row['new_coverage_pct']:.1f}% | {row['change_pp']:+.1f} ({row['paired_mcse_pp']:.2f}) | {e['old_mean_width_pp']:.2f} → {e['new_mean_width_pp']:.2f} |")
lines+=['','| Metric | BCa adjusted tails beyond empirical resolution: B999 → B4999 |','|---|---|']
for metric in METRICS:
    rows=[x for x in tails if x['metric']==metric]
    lines.append(f"| {metric} | {rows[0]['extreme_adjusted_tails']}/1000 → {rows[1]['extreme_adjusted_tails']}/1000 |")
lines+=['',f"Independent verification: {report['status']}; {checks} checks. Maximum raw prefix roundoff before explicit reuse: {report['raw_regenerated_prefix_max_absolute_difference']:.3g} over {report['raw_regenerated_prefix_mismatches']} differing values. Exact integer prefixes and exact combined floating-point prefixes were verified for all 1,000 outer indices.",'',
        'Coverage changes and endpoint differences describe finite Monte Carlo sensitivity in this condition. These two B values do not prove convergence to infinite-B limits. Interval zero exclusion and centered-test rejection are reported separately in paired-decisions.csv.','']
(OUT/'results.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'status':report['status'],'checks':checks,'errors':errors,'report':str(OUT/'validation.json')}),flush=True)
print((OUT/'results.md').read_text(),flush=True)
