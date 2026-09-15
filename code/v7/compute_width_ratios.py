"""Compute a descriptive Gaussian width benchmark from stored outer records.

Initial extraction: run in the study workspace. Portable replay: copy this file
and width-audit/inputs/outer-widths.csv.gz, then pass --input and --output.
No resampling, model inference, or scientific-source mutation occurs.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,json
import numpy as np
from scipy.stats import norm
P=argparse.ArgumentParser();P.add_argument('--input',type=Path);P.add_argument('--output',type=Path)
args=P.parse_args();A=Path(__file__).resolve().parent;S=A.parents[1]
OUT=args.output or A/'width-audit';OUT.mkdir(exist_ok=True,parents=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
pins={};records=[]
if args.input:
    with gzip.open(args.input,'rt',encoding='utf-8',newline='') as f:records=list(csv.DictReader(f))
else:
    old=S/'amendments/reviewer-revision-20260914-v1/existing-bootstrap/outer-centering-diagnostics.csv'
    pins[str(old)]=sha(old)
    with old.open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            records.append(dict(experiment='original',condition=r['case'],metric='FSR' if r['metric']=='false_success_rate' else 'recall',outer=r['outer'],point=r['point'],width_refit=r['percentile_width'],width_bca=''))
    run=S/'amendments/review-response-20260915-v1/simulation/run'
    for cond in json.loads((run/'freeze.json').read_text())['conditions']:
        start=0
        for p in sorted((run/cond['id']/'outer').glob('*.npz')):
            digest=sha(p);assert digest==json.loads(p.with_suffix('.json').read_text())['sha256'];pins[str(p)]=digest
            with np.load(p,allow_pickle=False) as z:
                point=z['point'];intervals=z['intervals']
                for i in range(len(point)):
                    for y,metric in enumerate(['FSR','recall']):
                        records.append(dict(experiment='weak_discrimination',condition=cond['id'],metric=metric,outer=start+i,point=point[i,y],width_refit=np.diff(intervals[i,1,y])[0],width_bca=np.diff(intervals[i,4,y])[0]))
            start+=len(point)
        assert start==1000
    (OUT/'inputs').mkdir(exist_ok=True)
    with gzip.open(OUT/'inputs/outer-widths.csv.gz','wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    (OUT/'source-pins.json').write_text(json.dumps(pins,indent=2),encoding='utf-8')
group={}
for r in records:group.setdefault((r['experiment'],r['condition'],r['metric']),[]).append(r)
rows=[]
for (ex,cond,metric),rs in group.items():
    point=np.array([float(r['point']) for r in rs]);sd=point.std(ddof=1)
    width=np.array([float(r['width_refit']) for r in rs]);assert len(rs)==1000 and np.isfinite(point).all() and np.isfinite(width).all()
    bca=np.array([float(r['width_bca']) for r in rs]) if rs[0]['width_bca']!='' else None
    rows.append(dict(experiment=ex,condition=cond,metric=metric,outer=len(rs),point_sd_pp=100*sd,
                     refit_mean_width_pp=100*width.mean(),refit_gaussian_width_ratio=width.mean()/(3.92*sd),
                     bca_mean_width_pp=100*bca.mean() if bca is not None else '',bca_gaussian_width_ratio=bca.mean()/(3.92*sd) if bca is not None else ''))
assert len(records)==36000 and len(rows)==36
with (OUT/'width-ratios.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
if not args.input:
    for p,h in pins.items():assert sha(p)==h
    original=S/'amendments/reviewer-revision-20260914-v1/existing-bootstrap/centering-summary.csv'
    with original.open(encoding='utf-8',newline='') as f:
        orig={(r['case'],'FSR' if r['metric']=='false_success_rate' else 'recall'):r for r in csv.DictReader(f)}
    for r in rows:
        if r['experiment']!='original':continue
        q=orig[r['condition'],r['metric']]
        np.testing.assert_allclose([r['point_sd_pp'],r['refit_mean_width_pp']],[float(q['point_empirical_sd_pp']),float(q['percentile_width_mean_pp'])],rtol=0,atol=1e-11)
s=np.sqrt(.75);t=1.5+s*norm.ppf(.1);h0=t-s*norm.ppf(1-(norm.cdf(-t/s)-.05))
note={'status':'PASS','outer_metric_records':len(records),'summary_rows':len(rows),'new_simulation_draws':0,'new_model_calls':0,
      'definition':'mean interval width / (3.92 * sample SD of outer point estimates), ddof=1; dimensionless descriptive normal-width benchmark, not a coverage validity test',
      'S20_source_failure_shift':float(h0),'S20_evaluation_success_shift':float(.5*s),
      'summary_sha256':sha(OUT/'width-ratios.csv'),'storage':'E: SATA HDD'}
(OUT/'verification.json').write_text(json.dumps(note,indent=2),encoding='utf-8')
print(json.dumps(note))
for r in rows:
    if r['metric']=='FSR':print(r['condition'],round(r['refit_gaussian_width_ratio'],4),round(r['bca_gaussian_width_ratio'],4) if r['bca_gaussian_width_ratio']!='' else '')
