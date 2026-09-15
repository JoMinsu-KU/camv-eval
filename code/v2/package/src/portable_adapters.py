"""Versioned path adapters: preserve frozen numerical functions, validate local projections.

Governance receipts remain verbatim lineage; old absolute-path execution gates are
not represented as newly replayed. This adapter validates the included score
projection and numerical analysis, using only package-relative inputs.
"""
from pathlib import Path
import csv,gzip,hashlib,importlib.util,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def readj(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def cohorts(case,data,core):
 result=[]
 for role in ('source','target'):
  ids=set(case[role+'_samples']);rs=[r for r in data[case[role+'_collection']] if r['model_id']==case['model'] and r['sample_id'] in ids]
  cs=core.build_cohorts(rs);values=[cs[(case['model'],case[role+'_dataset'],case[role+'_split'],s)] for s in case['seeds']]
  assert all(list(c.samples)==case[role+'_samples'] and list(c.groups)==case[role+'_groups'] for c in values)
  result.append(values)
 return result
def run_transfer(out,spec,data,frozen,core,empirical_out):
 m=load(ROOT/'transfer/run_transfer_sensitivity_v1.py','review_transfer')
 m.PACKAGE=ROOT;m.core=core;m.np=np
 cases=[]
 for c in spec['cases']:
  x=dict(c);x['reference']=str((empirical_out/c['key']).resolve());cases.append(x)
 revised=dict(spec,cases=cases);out.mkdir(parents=True,exist_ok=False)
 m.audit_historical(revised,data,frozen,out)
 rows=[];contrasts=[]
 for key in m.CASE_KEYS:
  c=next(c for c in cases if c['key']==key);r,s,_=m.run_case(c,data,frozen,out);rows.extend(r);contrasts.extend(s)
 m.writecsv(out/'operating-summary.csv',rows);m.writecsv(out/'contrasts.csv',contrasts)
 m.extract_existing(revised,out);m.describe_structure(revised,data,out)
def run_scorer(out):
 m=load(ROOT/'scorer/analyze_stored_scorers_v2.py','review_scorer');m.STUDY=ROOT
 def projected_inputs(_):
  source=ROOT/'data/scorer/per-trial-scores.csv';protocol=readj(ROOT/'scorer/protocol.json')
  m.check(sha(source)==protocol['input']['sha256'],'original_per_trial_score_hash')
  labels=[json.loads(s) for s in (ROOT/'data/scorer/diagnostic-labels.jsonl').read_text(encoding='utf-8-sig').splitlines() if s]
  events=[json.loads(s) for s in (ROOT/'data/scorer/raw-score-events.jsonl').read_text(encoding='utf-8').splitlines() if s]
  labmap={r['sample_id']:r for r in labels};rawmap={}
  for r in events:
   for name,z in r['output']['scores'].items():
    key=(r['request']['sample_id'],r['request']['context'],name)
    m.check(key not in rawmap,'unique_raw_score_projection');rawmap[key]=z
  with source.open(encoding='utf-8',newline='') as f:flat=list(csv.DictReader(f))
  m.check(len(flat)==1536,'row_count_1536');mapping={}
  for row in flat:
   key=(row['sample_id'],row['context'],row['scorer']);m.check(key not in mapping,'unique_trial_context_scorer')
   row['label']=int(row['label'])
   for k in ('score','logodds'):row[k]=float(row[k]);m.check(math.isfinite(row[k]),'finite_scores')
   row['candidate_mass']=float(row['candidate_mass']) if row['candidate_mass'] else None
   m.check(row['available']=='True','all_available');lab=labmap[row['sample_id']]
   m.check(all(row[k]==lab[k] for k in ('dataset','group_id')) and row['label']==int(lab['label']),'labels_and_groups')
   if row['context']=='late':
    value=(rawmap[(key[0],'single0',key[2])]['logodds']+rawmap[(key[0],'single1',key[2])]['logodds'])/2
    m.check(row['logodds']==value and row['score']==float(np.exp(-np.logaddexp(0,-value))),'late_exact_mean_logodds')
   else:
    z=rawmap[key];m.check(row['logodds']==z['logodds'] and row['score']==z['score'],'projected_raw_score_exact')
    m.check(row['candidate_mass']==z['vocabulary_mass'],'projected_raw_mass_exact')
   mapping[key]=row
  for key,allowed in [('dataset',m.DS),('context',m.CT),('scorer',m.SC)]:m.check(set(r[key] for r in flat)==set(allowed),'complete_'+key)
  pins={str(p):sha(p) for p in [source,ROOT/'data/scorer/diagnostic-labels.jsonl',ROOT/'data/scorer/raw-score-events.jsonl',ROOT/'scorer/protocol.json',ROOT/'src/empirical_core_v2.py']}
  return protocol,flat,mapping,pins
 m.prepare_inputs=projected_inputs;m.analyze(out)
def run_centering(out):
 import pandas as pd
 import matplotlib.pyplot as plt
 out.mkdir(parents=True,exist_ok=False)
 d=pd.read_csv(ROOT/'data/centering/outer-centering-diagnostics.csv.gz');summ=[]
 assert len(d)==20000 and set(d.case)=={'N01','N02','N03','N04','A01','A02','A03','A04','S02','S20'}
 for (case,metric),g in d.groupby(['case','metric'],sort=False):
  assert len(g)==1000
  sd=g.point.std(ddof=1);mu=g.procedure_truth.iloc[0]
  s={'case':case,'metric':metric,'n_outer':len(g),'procedure_truth_pp':100*mu,'oracle_mcse_pp':100*g.truth_mcse.iloc[0],
   'point_bias_pp':100*g.point_error.mean(),'point_empirical_sd_pp':100*sd,'point_rmse_pp':100*np.sqrt(np.mean(g.point_error**2)),
   'bootstrap_bias_mean_pp':100*g.bootstrap_bias.mean(),'bootstrap_sd_mean_pp':100*g.bootstrap_sd.mean(),'bootstrap_sd_over_empirical_sd':g.bootstrap_sd.mean()/sd,
   'midpoint_shift_mean_pp':100*g.midpoint_shift.mean(),'midpoint_shift_sd_pp':100*g.midpoint_shift.std(ddof=1),
   'corr_point_error_midpoint_shift':g.point_error.corr(g.midpoint_shift),'absolute_truth_over_empirical_sd':abs(mu)/sd}
  for name in ['conditional','percentile','basic','sandwich']:
   s[name+'_center_bias_pp']=100*(g[name+'_center'].mean()-mu)
   s[name+'_center_sd_pp']=100*g[name+'_center'].std(ddof=1);s[name+'_width_mean_pp']=100*g[name+'_width'].mean()
   s[name+'_coverage_procedure_pct']=100*g[name+'_coverage_procedure'].mean();s[name+'_coverage_fitted_pct']=100*g[name+'_coverage_fitted'].mean()
  for name,sign in [('percentile',1),('basic',-1)]:
   actual=g[name+'_center'].var(ddof=1)
   predicted=g.point.var(ddof=1)+g.midpoint_shift.var(ddof=1)+sign*2*g[['point','midpoint_shift']].cov().iloc[0,1]
   assert np.isclose(actual,predicted,atol=1e-14)
  summ.append(s)
 summary=pd.DataFrame(summ);summary.to_csv(out/'centering-summary.csv',index=False)
 fig,axs=plt.subplots(1,2,figsize=(7.2,3.3))
 for ax,case in zip(axs,['N02','A01']):
  g=d[(d.case==case)&(d.metric=='false_success_rate')]
  ax.scatter(100*g.point_error,100*g.midpoint_shift,s=7,alpha=.27,color='#0072B2')
  ax.axhline(0,lw=.7,color='#999');ax.axvline(0,lw=.7,color='#999')
  ax.set(title=case,xlabel='Point estimate − procedure truth (pp)',ylabel='Percentile midpoint − point estimate (pp)')
 fig.tight_layout();fig.savefig(out/'interval-centering-replayed.pdf');plt.close(fig)
 (out/'scope.json').write_text(json.dumps({'scope':'Summary replay from all saved 20,000 outer/metric records. Inner-bootstrap quantiles and oracle integrations are not regenerated.','inner_draws_reconstructed':False,'outer_rows':len(d)},indent=2),encoding='utf-8')
