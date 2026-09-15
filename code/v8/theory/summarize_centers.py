"""Summarize already verified CSV evidence for the bounded final-review audit.
No random draws, scientific source imports, or model calls.
"""
from pathlib import Path
import csv, hashlib, json

OUT=Path(__file__).resolve().parent
BASE=OUT.parents[1]
SIM=BASE/'review-response-20260915-v1/simulation'
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
paths={k:SIM/'summary-v2'/k for k in ('centers.csv','coverage.csv','bca-diagnostics.csv','reference-targets.csv')}
paths.update({k:SIM/'tail-check-v2/summary'/k for k in ('paired-coverage.csv','paired-endpoints.csv','bca-tail-diagnostics.csv')})
tables={k:read(p) for k,p in paths.items()}
ci={(r['condition'],r['metric'],r['method'],r['target']):r for r in tables['coverage.csv']}
centers={(r['condition'],r['metric'],r['method']):r for r in tables['centers.csv']}
keys=list(dict.fromkeys((r['condition'],r['metric']) for r in tables['centers.csv']))
rows=[]
for cond,metric in keys:
    t=float(centers[(cond,metric,'refit_percentile')]['point_sd_pp'])
    row=dict(condition=cond,metric=metric,point_sd_pp=t)
    for label,method in [('percentile','refit_percentile'),('basic','refit_basic'),('bca','refit_BCa')]:
        c=centers[(cond,metric,method)]
        v=ci[(cond,metric,method,'procedure_average')]
        row[label+'_center_sd_pp']=float(c['center_sd_pp'])
        row[label+'_center_to_point_sd']=float(c['center_sd_pp'])/t
        row[label+'_width_pp']=float(v['mean_width_pp'])
        row[label+'_gaussian_width_ratio']=float(v['mean_width_pp'])/(3.92*t)
        row[label+'_procedure_coverage_pct']=float(v['covered_planned_pct'])
    row['bca_minus_percentile_width_pp']=row['bca_width_pp']-row['percentile_width_pp']
    row['bca_relative_width_change_pct']=100*(row['bca_width_pp']/row['percentile_width_pp']-1)
    rows.append(row)
with (OUT/'center-and-width-evidence.csv').open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def extent(field,metric=None):
    selected=[r for r in rows if metric is None or r['metric']==metric]
    return [min(r[field] for r in selected),max(r[field] for r in selected)]
summary=dict(rows=len(rows),new_random_draws=0,new_model_calls=0,
             basic_center_sd_above_point_sd=sum(r['basic_center_to_point_sd']>1 for r in rows),
             bca_center_sd_above_point_sd=sum(r['bca_center_to_point_sd']>1 for r in rows),
             percentile_center_sd_below_point_sd=sum(r['percentile_center_to_point_sd']<1 for r in rows),
             bca_width_shorter_than_percentile=sum(r['bca_minus_percentile_width_pp']<0 for r in rows),
             bca_width_longer_than_percentile=sum(r['bca_minus_percentile_width_pp']>0 for r in rows),
             ratios={label:{metric:extent(label+'_center_to_point_sd',None if metric=='both' else metric)
                             for metric in ('both','FSR','recall')} for label in ('percentile','basic','bca')},
             percentile_gaussian_width_ratio_range=extent('percentile_gaussian_width_ratio'),
             bca_gaussian_width_ratio_range=extent('bca_gaussian_width_ratio'),
             bca_minus_percentile_width_pp_range=extent('bca_minus_percentile_width_pp'),
             bca_relative_width_change_pct_range=extent('bca_relative_width_change_pct'),
             finite_B_bca_width=[r for r in tables['paired-endpoints.csv'] if r['method']=='refit_BCa'],
             finite_B_bca_procedure_coverage=[r for r in tables['paired-coverage.csv'] if r['method']=='refit_BCa' and r['target']=='procedure_average'],
             q125_q500_recall_targets=[r for r in tables['reference-targets.csv'] if r['metric']=='recall' and ('Q125' in r['condition'] or 'Q500' in r['condition'])],
             input_files=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths.values()],
             script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(OUT/'numerical-evidence.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ('input_files','finite_B_bca_width','finite_B_bca_procedure_coverage','q125_q500_recall_targets')},indent=2))
