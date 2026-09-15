"""Portable all-outer table/figure replay from the compact saved-array package.

Usage: python summarize_revision_v1.py --input compact-directory --output new-directory
No access to the original experiment workspace is needed, and no random draws occur.
"""
from __future__ import annotations
import os
for _k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_k]='1'
from pathlib import Path
import argparse,csv,gzip,hashlib,json,math
import numpy as np
from scipy.stats import norm

ALGS=['conditional_percentile','refit_percentile','refit_basic','cluster_sandwich_t']
METRICS=['false_success_rate','success_recall']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.ndarray):return clean(v.tolist())
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,float) and not math.isfinite(v):return None
    return v
def mean(v):
    x=np.asarray(v);x=x[np.isfinite(x)];return float(x.mean()) if len(x) else math.nan
def sd(v):
    x=np.asarray(v);x=x[np.isfinite(x)];return float(x.std(ddof=1)) if len(x)>1 else math.nan
def rms(v):return math.sqrt(mean(np.asarray(v)**2))
def corr(x,y):
    x,y=np.asarray(x),np.asarray(y);good=np.isfinite(x)&np.isfinite(y)
    if good.sum()<3 or sd(x[good])==0 or sd(y[good])==0:return math.nan
    return float(np.corrcoef(x[good],y[good])[0,1])
def ratio(x,y):return float(x/y) if math.isfinite(x) and math.isfinite(y) and y!=0 else math.nan
def wilson(k,n):
    if n==0:return [math.nan,math.nan]
    z=float(norm.ppf(.975));p=k/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,mid-half),min(1.,mid+half)]
def rate_fields(prefix,mask,eligible,total):
    valid=np.asarray(eligible,dtype=bool);n=int(valid.sum());k=int((np.asarray(mask,dtype=bool)&valid).sum())
    rate=k/n if n else math.nan;lo,hi=wilson(k,n)
    pl,pu=wilson(k,total)
    return {prefix+'_events':k,prefix+'_valid_n':n,prefix+'_planned_n':total,
      prefix:rate,prefix+'_mcse':math.sqrt(rate*(1-rate)/n) if n else math.nan,
      prefix+'_wilson_lower':lo,prefix+'_wilson_upper':hi,
      prefix+'_planned_denominator_rate':k/total,prefix+'_planned_wilson_lower':pl,prefix+'_planned_wilson_upper':pu}
def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow(clean(r))
def info(s,m):return {'condition':s['id'],'kind':s['kind'],'G_dev':s['G_dev'],'G_eval':s['G_eval'],
    'lambda':s['lambda_'],'metric':METRICS[m]}

def summarize(input_dir,output_dir,figures=True):
    inp=Path(input_dir).resolve();out=Path(output_dir).resolve()
    if out.exists():raise ValueError('Output directory exists; replay into a fresh directory')
    manifest=json.loads((inp/'manifest.json').read_text());contract=manifest['contract']
    out.mkdir(parents=True);os.environ['MPLCONFIGDIR']=str(out/'mplconfig')
    coverage=[];tests=[];identities=[];datasets={};cell_arrays={};moments=[]
    for item in manifest['files']:
        path=inp/item['file']
        if sha(path)!=item['sha256']:raise ValueError('Compact hash mismatch: '+item['file'])
        with np.load(path,allow_pickle=False) as z:d={k:z[k] for k in z.files if k!='metadata'}
        s=next(x for x in contract['conditions'] if x['id']==item['condition']);datasets[s['id']]=(s,d)
        n=len(d['outer_index']);reference=contract['procedure_reference'][s['id']]
        if n!=1000 or not np.array_equal(d['outer_index'],np.arange(1000)):raise ValueError('Outer census mismatch')
        for m in range(2):
            T=d['point_contrasts'][:,4,m];tau=d['conditional_truth_contrasts'][:,4,m]
            mu=float(reference['mean'][m]);muse=float(reference['mcse'][m])
            pct=d['intervals'][:,1,4,m];basic=d['intervals'][:,2,4,m]
            widerr=np.diff(pct,axis=1).ravel()-np.diff(basic,axis=1).ravel()
            reflect=pct.mean(axis=1)+basic.mean(axis=1)-2*T
            identities.append({**info(s,m),'max_abs_percentile_basic_width_difference':float(np.nanmax(np.abs(widerr))),
              'max_abs_reflected_midpoint_identity_error':float(np.nanmax(np.abs(reflect))),
              'oracle_raw_truth':float(d['oracle_truth_raw'][0,4,m]),'oracle_truth_used':float(d['oracle_truth'][0,4,m]),
              'calibration_valid_n':int(d['calibration_valid'].sum()),'planned_n':n})
            for a,alg in enumerate(ALGS):
                bounds=d['intervals'][:,a,4,m];mid=bounds.mean(axis=1);width=np.diff(bounds,axis=1).ravel()
                mode=0 if a in (0,3) else 1
                bm=d['bootstrap_mean'][:,mode,4,m];bs=d['bootstrap_sd'][:,mode,4,m]
                se=d['sandwich_se'][:,4,m] if a==3 else bs
                for target,truth,intended in [('fitted_policy',tau,a in (0,3)),
                   ('procedure_average_given_valid_calibration',np.repeat(mu,n),a in (1,2))]:
                    good=np.isfinite(bounds).all(axis=1)&np.isfinite(truth)&np.isfinite(T)
                    covered=(bounds[:,0]<=truth)&(truth<=bounds[:,1]);error=T-truth
                    key=(s['id'],METRICS[m],target,alg);cell_arrays[key]=(covered,good,width)
                    row={**info(s,m),'arm':'fitted_development_thresholds','algorithm':alg,'target':target,'intended_target':intended,
                      'procedure_truth':mu,'reference_mcse':muse,'mean_fitted_truth':mean(tau),
                      **rate_fields('coverage',covered,good,n),'availability':good.mean(),
                      'point_bias':mean(error),'point_bias_mcse':ratio(sd(error),math.sqrt(np.isfinite(error).sum())),
                      'point_empirical_sd':sd(T),'point_target_error_sd':sd(error),'point_rmse':rms(error),
                      'mean_width':mean(width),'width_sd':sd(width),'mean_bootstrap_se':mean(bs),'mean_interval_se':mean(se),
                      'bootstrap_mean_minus_point':mean(bm-T),'bootstrap_mean_minus_point_sd':sd(bm-T),
                      'midpoint_minus_point':mean(mid-T),'midpoint_minus_point_sd':sd(mid-T),
                      'midpoint_minus_truth':mean(mid-truth),'midpoint_minus_truth_sd':sd(mid-truth),
                      'midpoint_truth_rmse':rms(mid-truth),'midpoint_shift_point_error_correlation':corr(mid-T,error),
                      'absolute_effect_to_mean_se':ratio(abs(mu) if target.startswith('procedure') else mean(np.abs(tau)),mean(se)),
                      'absolute_effect_to_empirical_sd':ratio(abs(mu) if target.startswith('procedure') else mean(np.abs(tau)),sd(T)),
                      'mean_valid_bootstrap_draws':mean(d['bootstrap_count'][:,mode,4,m])}
                    if target.startswith('procedure'):
                        low=mu-3*muse;high=mu+3*muse
                        row['reference_3mcse_coverage_lower']=mean(((bounds[:,0]<=low)&(bounds[:,1]>=high))[good])
                        row['reference_3mcse_coverage_upper']=mean(((bounds[:,0]<=high)&(bounds[:,1]>=low))[good])
                    coverage.append(row)
                for i in range(n):
                    moments.append({**info(s,m),'outer_index':i,'arm':'fitted_development_thresholds','algorithm':alg,
                      'point':T[i],'fitted_truth':tau[i],'procedure_truth':mu,'reference_mcse':muse,
                      'interval_lower':bounds[i,0],'interval_upper':bounds[i,1],'midpoint':mid[i],'width':width[i],
                      'bootstrap_mean':bm[i],'bootstrap_sd':bs[i],'interval_se':se[i]})
            for mode,name in enumerate(['conditional','refit']):
                pv=d['centered_p'][:,mode,4,m];good=np.isfinite(pv)
                tests.append({**info(s,m),'arm':'fitted_development_thresholds','test':name,
                    'target':'procedure_average_given_valid_calibration','cross_target':mode==0,
                    'event_type':'type_I' if s['kind']=='N' else 'power','truth':mu,'reference_mcse':muse,
                    **rate_fields('rejection',pv<=.05,good,n),
                    'mean_p':mean(pv),'fitted_exact_zero_truth_n':int(np.sum(tau==0)),
                    'nonconfirmatory':True,'multiplicity_family':'none'})
            # Fixed population-threshold arm; never evaluated against fitted-procedure mean.
            OT=d['oracle_point_contrasts'][:,4,m];truth=float(d['oracle_truth'][0,4,m]);rawtruth=float(d['oracle_truth_raw'][0,4,m])
            om=d['oracle_bootstrap_mean'][:,4,m];obs=d['oracle_bootstrap_sd'][:,4,m]
            for ai,alg in enumerate(['conditional_percentile','cluster_sandwich_t']):
                bounds=d['oracle_intervals'][:,ai,4,m];mid=bounds.mean(axis=1);width=np.diff(bounds,axis=1).ravel()
                se=obs if ai==0 else d['oracle_sandwich_se'][:,4,m]
                good=np.isfinite(bounds).all(axis=1)&np.isfinite(OT);covered=(bounds[:,0]<=truth)&(truth<=bounds[:,1])
                error=OT-truth
                coverage.append({**info(s,m),'arm':'fixed_population_oracle_thresholds','algorithm':alg,
                  'target':'fixed_population_oracle_policy','intended_target':True,'oracle_truth':truth,'oracle_raw_truth':rawtruth,
                  **rate_fields('coverage',covered,good,n),'availability':good.mean(),
                  'point_bias':mean(error),'point_bias_mcse':ratio(sd(error),math.sqrt(good.sum())),
                  'point_empirical_sd':sd(OT),'point_target_error_sd':sd(error),'point_rmse':rms(error),
                  'mean_width':mean(width),'width_sd':sd(width),'mean_bootstrap_se':mean(obs),'mean_interval_se':mean(se),
                  'bootstrap_mean_minus_point':mean(om-OT),'bootstrap_mean_minus_point_sd':sd(om-OT),
                  'midpoint_minus_point':mean(mid-OT),'midpoint_minus_point_sd':sd(mid-OT),
                  'midpoint_minus_truth':mean(mid-truth),'midpoint_minus_truth_sd':sd(mid-truth),
                  'midpoint_truth_rmse':rms(mid-truth),'midpoint_shift_point_error_correlation':corr(mid-OT,error),
                  'absolute_effect_to_mean_se':ratio(abs(truth),mean(se)),
                  'absolute_effect_to_empirical_sd':ratio(abs(truth),sd(OT)),
                  'mean_valid_bootstrap_draws':mean(d['oracle_bootstrap_count'][:,4,m])})
                for i in range(n):
                    moments.append({**info(s,m),'outer_index':i,'arm':'fixed_population_oracle_thresholds','algorithm':alg,
                      'point':OT[i],'fitted_truth':truth,'procedure_truth':None,'reference_mcse':0.,
                      'interval_lower':bounds[i,0],'interval_upper':bounds[i,1],'midpoint':mid[i],'width':width[i],
                      'bootstrap_mean':om[i],'bootstrap_sd':obs[i],'interval_se':se[i]})
            pv=d['oracle_centered_p'][:,4,m]
            tests.append({**info(s,m),'arm':'fixed_population_oracle_thresholds','test':'conditional',
                'target':'fixed_population_oracle_policy','cross_target':False,
                'event_type':'type_I' if truth==0. else 'power','truth':truth,'raw_truth':rawtruth,'reference_mcse':0.,
                **rate_fields('rejection',pv<=.05,np.isfinite(pv),n),'mean_p':mean(pv),
                'nonconfirmatory':True,'multiplicity_family':'none'})
    # Paired lambda contrasts on the frozen common-random-number streams.
    controls=[]
    for key,(hit,valid,width) in cell_arrays.items():
        cid,metric,target,alg=key;s=datasets[cid][0]
        if s['lambda_']==0.:continue
        base=f"{s['kind']}_G{s['G_dev']}_L000";h0,v0,w0=cell_arrays[(base,metric,target,alg)]
        good=valid&v0;delta=hit[good].astype(float)-h0[good].astype(float);dw=width[good]-w0[good]
        controls.append({'condition':cid,'baseline_condition':base,'metric':metric,'target':target,'algorithm':alg,
          'paired_n':int(good.sum()),'coverage_difference':mean(delta),'coverage_difference_mcse':ratio(sd(delta),math.sqrt(len(delta))),
          'mean_width_difference':mean(dw),'mean_width_difference_mcse':ratio(sd(dw),math.sqrt(len(dw))),
          'comparison':'paired_CRN_lambda_sensitivity','nonconfirmatory':True})
    write_csv(out/'coverage-and-diagnostics.csv',coverage);write_csv(out/'centered-tests.csv',tests)
    write_csv(out/'identity-and-availability.csv',identities);write_csv(out/'paired-lambda-controls.csv',controls)
    fields=list(dict.fromkeys(k for r in moments for k in r))
    with gzip.open(out/'outer-diagnostics.csv.gz','wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in moments:w.writerow(clean(row))
    packet={'schema':'camv-reviewer-simulation-summary-v1','source_manifest_sha256':sha(inp/'manifest.json'),
      'summary_code_sha256':sha(__file__),'conditions':12,'outer_total':12000,'bootstrap_B':999,
      'new_draws':0,'coverage_rows':len(coverage),'test_rows':len(tests),'moment_rows':len(moments),
      'all_intervals_available':all(r['coverage_valid_n']==1000 for r in coverage),
      'max_equal_width_error':max(r['max_abs_percentile_basic_width_difference'] for r in identities),
      'max_reflection_error':max(r['max_abs_reflected_midpoint_identity_error'] for r in identities),
      'tables':{'coverage':coverage,'tests':tests,'identities':identities,'paired_controls':controls},
      'replay_scope':manifest['replay_scope']}
    (out/'summary.json').write_text(json.dumps(clean(packet),indent=2,sort_keys=True,allow_nan=False)+'\n')
    if figures:make_figures(out,coverage,tests)
    narrative(out,coverage,tests,packet)
    artifacts=[{'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()]
    (out/'replay-completion.json').write_text(json.dumps({'complete':True,'input_manifest_sha256':sha(inp/'manifest.json'),
        'new_scientific_draws':0,'artifacts':artifacts,'source_code_sha256':sha(__file__)},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'summary_complete':True,'coverage_rows':len(coverage),'test_rows':len(tests),'moment_rows':len(moments)}),flush=True)
    return packet

def select(rows,**criteria):
    return [r for r in rows if all(r.get(k)==v for k,v in criteria.items())]
def make_figures(out,rows,tests):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'savefig.dpi':180})
    colors={'conditional_percentile':'#3376a8','refit_percentile':'#00876c','refit_basic':'#d45b45','cluster_sandwich_t':'#805ba3'}
    labels={'conditional_percentile':'Conditional','refit_percentile':'Refit percentile','refit_basic':'Refit basic','cluster_sandwich_t':'Sandwich t'}
    for kind in ('N','A'):
        fig,axes=plt.subplots(2,2,figsize=(9,6),sharex=True,sharey=True)
        for mi,metric in enumerate(METRICS):
            for gi,gd in enumerate((40,100)):
                ax=axes[mi,gi]
                for alg in ALGS:
                    rr=sorted(select(rows,kind=kind,G_dev=gd,metric=metric,algorithm=alg,target='procedure_average_given_valid_calibration'),key=lambda r:r['lambda'])
                    ax.plot([r['lambda'] for r in rr],[r['coverage']*100 for r in rr],marker='o',label=labels[alg],color=colors[alg])
                ax.axhline(95,color='.4',ls='--',lw=.8);ax.set_ylim(30,102);ax.set_xticks([0,.5,.9]);ax.grid(alpha=.15)
                ax.set_title(f"{'FSR' if mi==0 else 'Recall'}; development groups {gd}")
                if gi==0:ax.set_ylabel('Procedure-target coverage (%)')
                if mi==1:ax.set_xlabel('Cross-method latent correlation λ')
        h,l=axes[0,0].get_legend_handles_labels();fig.legend(h,l,loc='lower center',ncol=4,frameon=False)
        fig.suptitle(('Exchangeable null' if kind=='N' else 'Pair-offset alternative')+'; evaluation groups fixed at 120')
        fig.tight_layout(rect=[0,.065,1,.95]);fig.savefig(out/f'coverage-dependence-{kind}.pdf');fig.savefig(out/f'coverage-dependence-{kind}.png');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(9,6),sharex=True)
    for mi,metric in enumerate(METRICS):
        for gi,gd in enumerate((40,100)):
            ax=axes[mi,gi]
            for alg,label,col in [('refit_percentile','Percentile midpoint','#00876c'),('refit_basic','Basic midpoint','#d45b45')]:
                rr=sorted(select(rows,kind='A',G_dev=gd,metric=metric,algorithm=alg,target='procedure_average_given_valid_calibration'),key=lambda r:r['lambda'])
                ax.plot([r['lambda'] for r in rr],[r['midpoint_minus_truth_sd']*100 for r in rr],marker='o',label=label,color=col)
            rr=sorted(select(rows,kind='A',G_dev=gd,metric=metric,algorithm='refit_percentile',target='procedure_average_given_valid_calibration'),key=lambda r:r['lambda'])
            ax.plot([r['lambda'] for r in rr],[r['point_empirical_sd']*100 for r in rr],marker='s',label='Point estimator',color='#333333')
            ax.set_title(f"{'FSR' if mi==0 else 'Recall'}; development groups {gd}");ax.set_xticks([0,.5,.9]);ax.grid(alpha=.15)
            if gi==0:ax.set_ylabel('Across-outer standard deviation (pp)')
            if mi==1:ax.set_xlabel('Cross-method latent correlation λ')
    h,l=axes[0,0].get_legend_handles_labels();fig.legend(h,l,loc='lower center',ncol=3,frameon=False)
    fig.suptitle('Equal-width intervals have different center dispersion: pair-offset alternatives')
    fig.tight_layout(rect=[0,.065,1,.95]);fig.savefig(out/'interval-center-dispersion.pdf');fig.savefig(out/'interval-center-dispersion.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(9,3.7),sharex=True)
    for gi,gd in enumerate((40,100)):
        ax=axes[gi]
        for arm,alg,label,col in [('fitted_development_thresholds','refit_percentile','Refit percentile','#00876c'),
          ('fitted_development_thresholds','conditional_percentile','Conditional, estimated thresholds','#3376a8'),
          ('fixed_population_oracle_thresholds','conditional_percentile','Conditional, oracle thresholds','#d45b45')]:
            rr=sorted(select(rows,kind='A',G_dev=gd,metric='false_success_rate',algorithm=alg,arm=arm,
                target='fixed_population_oracle_policy' if arm.startswith('fixed_population') else ('procedure_average_given_valid_calibration' if alg.startswith('refit') else 'fitted_policy')),key=lambda r:r['lambda'])
            ax.plot([r['lambda'] for r in rr],[r['mean_width']*100 for r in rr],marker='o',label=label,color=col)
        ax.set_title(f'Development groups {gd}');ax.set_xlabel('Cross-method latent correlation λ');ax.set_xticks([0,.5,.9]);ax.grid(alpha=.15)
        if gi==0:ax.set_ylabel('Mean FSR interaction interval width (pp)')
    h,l=axes[0].get_legend_handles_labels();fig.legend(h,l,loc='lower center',ncol=1,frameon=False)
    fig.suptitle('Fixed population-threshold control; distinct interval targets are labeled')
    fig.tight_layout(rect=[0,.22,1,.92]);fig.savefig(out/'oracle-threshold-control.pdf');fig.savefig(out/'oracle-threshold-control.png');plt.close(fig)

def narrative(out,rows,tests,packet):
    def pct(x):return f'{100*x:.1f}'
    lines=['# Reviewer revision simulation: complete fixed sensitivity study','',
      'All 12 prespecified conditions completed 1,000 outer datasets and 999 bootstrap draws. Evaluation groups remain 120. This is a Gaussian latent-correlation sensitivity, not a fit of the latent correlation to observed VLM Spearman coefficients. It retains three overlapping pairs, not the RLBench four-camera/six-pair census.','',
      'The fixed population-threshold arm has its own exact fixed-policy truth. It is not assessed against the mean of finite-development calibration procedures. Existing A01/A04 reference means and Monte Carlo errors are reused by the marginal-law/common-validity proof in PROTOCOL.md.','',
      '## Procedure interaction results','',
      '| Condition | FSR C/R/B coverage (%) | Recall C/R/B coverage (%) | Refit FSR rejection (%) | Refit recall rejection (%) |',
      '|---|---:|---:|---:|---:|']
    condition_ids=list(dict.fromkeys(r['condition'] for r in rows))
    for cid in condition_ids:
        vals=[]
        for m in METRICS:
            vals.append(' / '.join(pct(select(rows,condition=cid,metric=m,target='procedure_average_given_valid_calibration',algorithm=a)[0]['coverage']) for a in ALGS[:3]))
        pp=[select(tests,condition=cid,metric=m,arm='fitted_development_thresholds',test='refit')[0]['rejection'] for m in METRICS]
        lines.append(f'| {cid} | {vals[0]} | {vals[1]} | {pct(pp[0])} | {pct(pp[1])} |')
    lines += ['', 'C denotes a conditional percentile interval applied cross-target to the procedure average; R is refit percentile; B is refit basic. Null rejection is a procedure-target Type I frequency, alternative rejection is two-sided interaction-test power, and there is no new Holm or confirmatory family. FSR and recall power must be read with their different true effects and effect-to-SE ratios.','',
      '## Interval location and fixed-threshold control','',
      '| Condition | FSR point SD (pp) | Percentile midpoint SD (pp) | Basic midpoint SD (pp) | Bootstrap mean − point (pp) | Percentile mean width (pp) | Oracle conditional mean width (pp) |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for cid in condition_ids:
        if not cid.startswith('A'):continue
        p=select(rows,condition=cid,metric='false_success_rate',target='procedure_average_given_valid_calibration',algorithm='refit_percentile')[0]
        b=select(rows,condition=cid,metric='false_success_rate',target='procedure_average_given_valid_calibration',algorithm='refit_basic')[0]
        o=select(rows,condition=cid,metric='false_success_rate',target='fixed_population_oracle_policy',algorithm='conditional_percentile')[0]
        lines.append('| '+cid+' | '+' | '.join(f'{100*x:.3f}' for x in [p['point_empirical_sd'],p['midpoint_minus_truth_sd'],b['midpoint_minus_truth_sd'],p['bootstrap_mean_minus_point'],p['mean_width'],o['mean_width']])+' |')
    lines += ['',f"The maximum absolute percentile/basic width-identity residual is {packet['max_equal_width_error']:.3g}, and the reflected-midpoint identity residual is {packet['max_reflection_error']:.3g}. Equal widths do not imply equal interval locations or the same across-outer center variability. The CSV includes bias, target-error SD, RMSE, midpoint error, midpoint-shift/error correlation, and effect-to-SE ratios for every condition and metric. These are descriptive diagnostics, with the fixed-threshold arm supplying a controlled calibration-estimation contrast only within this specified synthetic mechanism.",'',
      f"All intervals available: {packet['all_intervals_available']}. Coverage and rejection rows include numerators, valid and planned denominators, Monte Carlo standard errors, and 95% Wilson intervals. Reference plus/minus-three-MCSE bounds are reported as integration sensitivity, not simultaneous confidence limits. Fixed streams and all unfavorable results are retained.",'',
      '## Reproduction scope','',
      'Run `python summarize_revision_v1.py --input compact-directory --output fresh-directory`. This recomputes every new table and figure from all 12,000 saved outer points, intervals, p-values, and bootstrap moments. It does not regenerate the inner draws or oracle reference. Full generator/controller sources and compressed raw chunks are separately retained. This is internal same-OS numerical replay, not external researcher reproduction.']
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--no-figures',action='store_true');a=p.parse_args()
    summarize(a.input,a.output,not a.no_figures)
