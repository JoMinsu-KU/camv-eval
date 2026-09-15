"""Post-hoc interval-centering diagnostics of immutable retained draws."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
NEW=ROOT/'amendments/p0-e2e-20260914-v1/simulation-run-v1'
OLD=ROOT/'verification/final-cpu-recovery-v2/simulation/summary-v1'
refs=json.loads((NEW/'reference-truth.json').read_text())
oldrefs=pd.read_csv(OLD/'procedure-reference-truth.csv')
oldmap=json.loads((OLD/'raw-source-map.json').read_text())
pin={};checks=[];rows=[];summ=[]

def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()

for case in ['N01','N02','N03','N04','A01','A02','A03','A04','S02','S20']:
 legacy=case.startswith('S')
 files=sorted(Path(x['path']) for x in oldmap if f'/{case}/' in x['path'].replace('\\','/')) if legacy else sorted((NEW/'chunks').glob(f'outer-{case}-*.npz'))
 assert len(files)==40,(case,len(files))
 local=[]
 for file in files:
  pin[str(file)]=digest(file)
  with np.load(file,allow_pickle=False) as a:
   ci=0 if legacy else 4
   point=a['point_contrasts'][:,ci,:]
   fitted=a['conditional_truth_contrasts'][:,ci,:]
   bounds=a['intervals'][:,:,ci,:,:]
   if legacy:
    m=a['bootstrap_method_rates']
    draws=m[:,1,:,2,:]-m[:,1,:,3,:]
   else:
    m=a['refit_policy_draws']
    draws=(m[:,:,1,:]-m[:,:,3,:])-(m[:,:,0,:]-m[:,:,2,:])
   q=np.nanquantile(draws,[.025,.975],axis=1,method='linear').transpose(1,2,0)
   assert np.allclose(q,bounds[:,1],atol=1e-14,equal_nan=True)
   width=bounds[:,:,:,1]-bounds[:,:,:,0]
   center=bounds.mean(axis=-1)
   assert np.allclose(width[:,1],width[:,2],atol=1e-14,equal_nan=True)
   assert np.allclose(center[:,1]+center[:,2],2*point,atol=1e-14,equal_nan=True)
   bm=np.nanmean(draws,axis=1);bs=np.nanstd(draws,axis=1,ddof=1)
   for k in range(len(point)):
    oi=int(a['outer_index'][k]) if legacy else int(file.stem.split('-')[2])+k
    for j,metric in enumerate(['false_success_rate','success_recall']):
     if legacy:
      r=oldrefs[(oldrefs.scenario==case)&(oldrefs.contrast=='joint_minus_late')&(oldrefs.metric==metric)].iloc[0]
      mu=float(r.truth_mean);mcse=float(r.truth_mcse)
     else:mu=refs[case]['truth_mean'][4][j];mcse=refs[case]['truth_mcse'][4][j]
     item={'case':case,'contrast':'joint_minus_late' if legacy else 'interaction','metric':metric,'outer':oi,'procedure_truth':mu,'truth_mcse':mcse,'point':point[k,j],'fitted_truth':fitted[k,j],'bootstrap_mean':bm[k,j],'bootstrap_sd':bs[k,j]}
     for alg,name in enumerate(['conditional','percentile','basic','sandwich']):
      item[name+'_center']=center[k,alg,j];item[name+'_width']=width[k,alg,j]
      for target,t in [('procedure',mu),('fitted',fitted[k,j])]:
       item[name+'_coverage_'+target]=float(bounds[k,alg,j,0]<=t<=bounds[k,alg,j,1]) if np.isfinite(bounds[k,alg,j]).all() else np.nan
     item['midpoint_shift']=item['percentile_center']-item['point']
     item['bootstrap_bias']=item['bootstrap_mean']-item['point']
     item['point_error']=item['point']-mu
     local.append(item)
 rows.extend(local)
 print(case,len(local),flush=True)
 checks.append({'case':case,'chunks':len(files),'quantiles_reproduced':True,'percentile_basic_width_equal':True,'centers_reflection_identity':True})

d=pd.DataFrame(rows)
assert len(d)==20000
for (case,metric),g in d.groupby(['case','metric'],sort=False):
 sd=g.point.std(ddof=1);mu=g.procedure_truth.iloc[0]
 s={'case':case,'metric':metric,'n_outer':len(g),'procedure_truth_pp':100*mu,'oracle_mcse_pp':100*g.truth_mcse.iloc[0],
 'point_bias_pp':100*g.point_error.mean(),'point_empirical_sd_pp':100*sd,'point_rmse_pp':100*np.sqrt(np.mean(g.point_error**2)),
 'bootstrap_bias_mean_pp':100*g.bootstrap_bias.mean(),'bootstrap_sd_mean_pp':100*g.bootstrap_sd.mean(),'bootstrap_sd_over_empirical_sd':g.bootstrap_sd.mean()/sd,
 'midpoint_shift_mean_pp':100*g.midpoint_shift.mean(),'midpoint_shift_sd_pp':100*g.midpoint_shift.std(ddof=1),
 'corr_point_error_midpoint_shift':g.point_error.corr(g.midpoint_shift),'absolute_truth_over_empirical_sd':abs(mu)/sd}
 for name in ['conditional','percentile','basic','sandwich']:
  s[name+'_center_bias_pp']=100*(g[name+'_center'].mean()-mu)
  s[name+'_center_sd_pp']=100*g[name+'_center'].std(ddof=1)
  s[name+'_width_mean_pp']=100*g[name+'_width'].mean()
  s[name+'_coverage_procedure_pct']=100*g[name+'_coverage_procedure'].mean()
  s[name+'_coverage_fitted_pct']=100*g[name+'_coverage_fitted'].mean()
 for name,sign in [('percentile',1),('basic',-1)]:
  actual=g[name+'_center'].var(ddof=1)
  predicted=g.point.var(ddof=1)+g.midpoint_shift.var(ddof=1)+sign*2*g[['point','midpoint_shift']].cov().iloc[0,1]
  assert np.isclose(actual,predicted,atol=1e-14)
 summ.append(s)
summary=pd.DataFrame(summ)
d.to_csv(OUT/'outer-centering-diagnostics.csv',index=False)
summary.to_csv(OUT/'centering-summary.csv',index=False)
plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
fig,axs=plt.subplots(1,2,figsize=(7.2,3.3))
for ax,case in zip(axs,['N02','A01']):
 g=d[(d.case==case)&(d.metric=='false_success_rate')]
 s=summary[(summary.case==case)&(summary.metric=='false_success_rate')].iloc[0]
 ax.scatter(100*g.point_error,100*g.midpoint_shift,s=7,alpha=.27,color='#0072B2',rasterized=False)
 ax.axhline(0,lw=.7,color='#999');ax.axvline(0,lw=.7,color='#999')
 ax.set(title=case+(' (procedure null)' if case=='N02' else ' (pair-offset alternative)'),xlabel='Point estimate − procedure truth (pp)',ylabel='Percentile midpoint − point estimate (pp)')
 ax.text(.04,.06,f'Correlation = {s.corr_point_error_midpoint_shift:.2f}\nCenter SD: percentile {s.percentile_center_sd_pp:.2f}, basic {s.basic_center_sd_pp:.2f} pp\nCommon mean width = {s.percentile_width_mean_pp:.2f} pp',transform=ax.transAxes,fontsize=7,bbox={'facecolor':'white','edgecolor':'none','alpha':.85})
fig.tight_layout()
for ext in ['pdf','png','svg']:fig.savefig(OUT/f'interval-centering.{ext}',dpi=220,bbox_inches='tight')
note='''# Stored-draw centering analysis

This is a post hoc description of all eight retained interaction conditions and the two review-named legacy conditions S02/S20. No new model or simulation draws were generated. Units in summary columns ending `_pp` are percentage points.

Let $T$ be the observed contrast and $d=(q_{.025}+q_{.975})/2-T$. The percentile center is $T+d$ and the basic center is $T-d$. Their widths are exactly equal. Consequently their center variances differ by $4\operatorname{Cov}(T,d)$, even when their mean biases are small. The reported correlations and variance identities describe the retained resampling distribution; they are not a causal ablation of calibration or a proof of bootstrap validity.

Bootstrap bias is separately calculated as the mean retained refit draw minus the point estimate. It is not conflated with the midpoint displacement. The absolute procedure-effect/outer-SD ratio is a descriptive signal scale and is not a retrospective estimate of prospective power or a minimum detectable effect.

The scatter figure shows every outer repetition of the prespecified representative N02/A01 FSR conditions. All other conditions and both metrics are retained in the CSV summary. Oracle Monte Carlo uncertainty is separately recorded.
'''
(OUT/'methods-and-interpretation.md').write_text(note,encoding='utf-8')
(OUT/'completion.json').write_text(json.dumps({'status':'complete','outer_metric_rows':len(d),'summary_rows':len(summary),'new_model_calls':0,'new_simulation_draws':0,'source_sha256':pin,'checks':checks,'script_sha256':digest(__file__)},indent=2),encoding='utf-8')
print(summary[summary.case.isin(['N02','A01','S02','S20'])].to_string(index=False))
