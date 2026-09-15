"""Read-only N1 audit of saved simulation rows plus bounded deterministic probes.

Run with the E: experiment launcher. No outer() calls and no new Monte Carlo run.
Summary reconstruction does not import scientific modules. The frozen modules are
imported only for the explicitly enumerated generator/calibration probes.
"""
from pathlib import Path
import argparse, csv, hashlib, json, math, platform, sys
import numpy as np
from scipy.special import ndtr
from scipy.stats import norm

DEFAULT_SOURCE = Path('E:/SoftwareX/camv-eval-study-v1/amendments/review-response-20260915-v1/simulation')
METHODS = ['conditional_percentile', 'refit_percentile', 'refit_basic', 'conditional_sandwich_t', 'refit_BCa']
METRICS = ['FSR', 'recall']
RATE_TOL = 2e-14
SCORE_TOL = 2e-14
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', '--source-root', dest='source', type=Path, default=DEFAULT_SOURCE,
                    help='Simulation directory, including run/ and summary-v2/; accepts an extracted v4 supplement.')
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
SRC = args.source.resolve(); OUT = args.output.resolve(); OUT.mkdir(parents=True, exist_ok=True)
assert OUT != SRC and SRC not in OUT.parents, 'Audit output must not modify scientific inputs.'
checks = []; errors = []; receipts = []; comparisons = []; rowproofs = []; refproofs = []; probes = []; bca_proofs = []

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def check(name, ok, detail=None):
    checks.append(name)
    if not bool(ok): errors.append(dict(check=name, detail=detail))
def writecsv(name, rows):
    with (OUT / name).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
def discrepancy(a, b):
    a = np.asarray(a); b = np.asarray(b)
    finite = np.isfinite(a) & np.isfinite(b)
    neq = ~((a == b) | (np.isnan(a) & np.isnan(b)))
    return dict(values=int(a.size), unequal_values=int(neq.sum()),
                bit_identical=bool(a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()),
                max_abs_difference=float(np.max(np.abs(a[finite] - b[finite]))) if finite.any() else 0.,
                finite_pattern_disagreements=int(np.sum(np.isfinite(a) != np.isfinite(b))))
def record_compare(c0, c1, key, metric, a, b, expect_invariant):
    d = discrepancy(a, b)
    comparisons.append(dict(base=c0, comparison=c1, field=key, metric=metric,
                            expect_invariant=expect_invariant, **d))
    if expect_invariant:
        check(f'{c0}/{c1}/{key}/{metric}: invariant',
              d['max_abs_difference'] <= RATE_TOL and d['finite_pattern_disagreements'] == 0, d)
    return d
def load_chunks(cid, kind):
    arrays = {}; prev = 0
    for path in sorted((SRC/'run'/cid/kind).glob('*.npz')):
        rec = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        digest = sha(path)
        check(str(path)+': receipt', digest == rec['sha256'] and rec['condition'] == cid
              and rec['kind'] == kind and rec['start'] == prev and int(path.stem) == prev)
        prev = rec['stop']
        receipts.append(dict(path=str(path), sha256=digest, kind=kind, condition=cid,
                             start=rec['start'], stop=rec['stop']))
        with np.load(path, allow_pickle=False) as z:
            for key in z.files:
                check(str(path)+': shape '+key, len(z[key]) == rec['stop']-rec['start'])
                arrays.setdefault(key, []).append(z[key])
    return {k: np.concatenate(v, axis=0) for k,v in arrays.items()}

freeze_path = SRC/'run/freeze.json'
freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
source_pins = {str(SRC/name): sha(SRC/name) for name in freeze['pins']}
for name,digest in freeze['pins'].items(): check('frozen source '+name, sha(SRC/name) == digest)
check('frozen design', freeze['M'] == 1000 and freeze['B'] == 999 and freeze['reference_n'] == 32768)
data = {}; references = {}; targets = {}; reference_rows = []; summary_rows = []
with (SRC/'summary-v2/coverage.csv').open(encoding='utf-8-sig', newline='') as f:
    published_coverage = {(r['condition'],r['metric'],r['method'],r['target']):r for r in csv.DictReader(f)}
with (SRC/'summary-v2/rejections.csv').open(encoding='utf-8-sig', newline='') as f:
    published_rejections = list(csv.DictReader(f))
z975 = norm.ppf(.975)
for cond in freeze['conditions']:
    cid = cond['id']; d = data[cid] = load_chunks(cid, 'outer')
    check(cid+': 1000 saved outer indices', d['point'].shape == (1000,2))
    check(cid+': 999 saved draws', d['refit_draws'].shape == (1000,999,2))
    if cond['exact_zero']:
        mu = np.zeros(2); mcse = np.zeros(2); rn = 0
    else:
        ref = references[cid] = load_chunks(cid, 'reference')['values']
        check(cid+': complete reference', ref.shape == (32768,2) and np.isfinite(ref).all())
        mu = ref.mean(axis=0); mcse = ref.std(axis=0,ddof=1)/math.sqrt(len(ref)); rn = len(ref)
    targets[cid] = mu
    for y,metric in enumerate(METRICS):
        reference_rows.append(dict(condition=cid,metric=metric,target_pp=100*mu[y],
                                   reference_mcse_pp=100*mcse[y],reference_realizations=rn))
    # Independent oracle reconstruction from saved thresholds; no source import.
    f = d['point_thresholds']
    threshold = np.stack((np.repeat(f[:,[0]],3,axis=1),f[:,1:4],
                          np.repeat(f[:,[4]],3,axis=1),f[:,5:8]),axis=1)
    if cond['step']: threshold = cond['step']*np.ceil(threshold/cond['step'])
    reconstructed_truth = np.empty((1000,2))
    for y in (0,1):
        jm = cond['separation']*y+np.asarray(cond['offset'])
        lm = np.full(3,cond['separation']*y)
        rates = norm.sf((threshold-np.array([jm,jm,lm,lm])[None])/math.sqrt(.75)).mean(axis=-1)
        reconstructed_truth[:,y] = (rates[:,1]-rates[:,3])-(rates[:,0]-rates[:,2])
    check(cid+': independent saved-threshold oracle',
          np.allclose(reconstructed_truth,d['fitted_truth'],atol=RATE_TOL,rtol=0))
    # Reconstruct percentile/basic limits and centered p-values from raw draws.
    for di,key in enumerate(('conditional_draws','refit_draws')):
        draw = d[key]
        q = np.quantile(draw,[.025,.975],axis=1,method='linear').transpose(1,2,0)
        check(cid+': '+key+' percentile limits', np.allclose(q,d['intervals'][:,di],atol=RATE_TOL,rtol=0))
        pv = (1+(np.abs(draw-d['point'][:,None]) >= np.abs(d['point'][:,None])).sum(axis=1))/1000
        check(cid+': '+key+' centered p-values', np.array_equal(pv,d['pvalues'][:,di]))
        if di == 1:
            basic = 2*d['point'][:,:,None]-q[:,:,::-1]
            check(cid+': basic reflection',np.allclose(basic,d['intervals'][:,2],atol=RATE_TOL,rtol=0))
    # Independent two-sample BCa reconstruction, including separate jackknife centering.
    uj=[]
    for key in ('jackknife_dev','jackknife_eval'):
        j=d[key];ng=j.shape[1];uj.append((j.mean(axis=1,keepdims=True)-j)*(ng-1)/ng)
    u=np.concatenate(uj,axis=1)
    acceleration=(u**3).sum(axis=1)/(6*(u*u).sum(axis=1)**1.5)
    boot=d['refit_draws'];point=d['point']
    rank=((boot<point[:,None]).sum(axis=1)+.5*(boot==point[:,None]).sum(axis=1))/boot.shape[1]
    bias=norm.ppf(rank);z=bias[:,:,None]+norm.ppf([.025,.975])
    denominator=1-acceleration[:,:,None]*z
    adjusted=norm.cdf(bias[:,:,None]+z/denominator)
    rebuilt=np.full((1000,2,2),np.nan)
    for i in range(1000):
        for y in (0,1):
            if np.isfinite(adjusted[i,y]).all() and np.all(denominator[i,y]>0) and adjusted[i,y,0]<=adjusted[i,y,1]:
                ordered=np.sort(boot[i,:,y]);location=adjusted[i,y]*(len(ordered)-1)
                lo=np.floor(location).astype(int);hi=np.ceil(location).astype(int)
                rebuilt[i,y]=ordered[lo]+(location-lo)*(ordered[hi]-ordered[lo])
    for y,metric in enumerate(METRICS):
        bd=discrepancy(rebuilt[:,y],d['intervals'][:,4,y])
        bca_proofs.append(dict(condition=cid,metric=metric,**bd))
        check(cid+'/'+metric+': independent BCa reconstruction',
              bd['finite_pattern_disagreements']==0 and bd['max_abs_difference']<=2e-12,bd)
        check(cid+'/'+metric+': BCa bias and acceleration',
              np.allclose(bias[:,y],d['bca_diagnostics'][:,y,1],atol=RATE_TOL,rtol=0)
              and np.allclose(acceleration[:,y],d['bca_diagnostics'][:,y,2],atol=RATE_TOL,rtol=0))
    for y,metric in enumerate(METRICS):
        for mi,method in enumerate(METHODS):
            ci = d['intervals'][:,mi,y]
            avail = np.isfinite(ci).all(axis=1)
            for target_name,truth in [('procedure_average',mu[y]),('fitted_policy',d['fitted_truth'][:,y])]:
                covered = avail & (ci[:,0] <= truth) & (truth <= ci[:,1])
                k = int(covered.sum()); n = int(avail.sum()); rate=k/n
                width = float(np.mean(ci[avail,1]-ci[avail,0]))
                den = 1+z975*z975/n; mid=(rate+z975*z975/(2*n))/den
                radius=z975*math.sqrt(rate*(1-rate)/n+z975*z975/(4*n*n))/den
                r = dict(condition=cid,metric=metric,method=method,target=target_name,
                         target_pp=100*mu[y] if target_name=='procedure_average' else '',
                         planned=1000,available=n,covered=k,coverage_pct=100*rate,
                         wilson_lower_pct=100*(mid-radius),wilson_upper_pct=100*(mid+radius),
                         mean_width_pp=100*width,
                         centered_refit_rejections=int((d['pvalues'][:,1,y]<=.05).sum()),
                         centered_refit_rejection_pct=100*np.mean(d['pvalues'][:,1,y]<=.05))
                summary_rows.append(r)
                pr = published_coverage[(cid,metric,method,target_name)]
                check(cid+'/'+metric+'/'+method+'/'+target_name+': saved CSV count',
                      k==int(pr['covered']) and n==int(pr['available']))
                check(cid+'/'+metric+'/'+method+'/'+target_name+': saved CSV width',
                      abs(100*width-float(pr['mean_width_pp'])) < 2e-11)
        rejection=next(r for r in published_rejections if r['condition']==cid
                       and r['metric']==metric and r['procedure']=='refit_centered')
        check(cid+'/'+metric+': saved CSV centered rejection',
              int(np.sum(d['pvalues'][:,1,y]<=.05))==int(rejection['rejected']))
    print('Reaggregated',cid,flush=True)

# All 1,000 rows and every stored draw, interval, p-value, and jackknife entry.
pairs = [('H050_C','H065_C',True),('H050_C','S_H_C',True),
         ('H050_Q125','H065_Q125',False),('H050_Q500','H065_Q500',False)]
metric_axes = {'point':1,'point_policy':2,'fitted_truth':1,'intervals':2,'pvalues':2,
               'bca_diagnostics':1,'refit_draws':2,'conditional_draws':2,
               'jackknife_dev':2,'jackknife_eval':2,'finite_draw_counts':2}
conditions = {c['id']:c for c in freeze['conditions']}
for c0,c1,invariant in pairs:
    a=data[c0]; b=data[c1]
    for key,axis in metric_axes.items():
        for y,metric in enumerate(METRICS):
            record_compare(c0,c1,key,metric,np.take(a[key],y,axis=axis),
                           np.take(b[key],y,axis=axis),invariant and y==1)
    delta=conditions[c1]['separation']-conditions[c0]['separation']
    td=discrepancy(a['point_thresholds']+delta,b['point_thresholds'])
    comparisons.append(dict(base=c0,comparison=c1,field='thresholds_after_positive_class_shift',
                            metric='calibration',expect_invariant=invariant,**td))
    if invariant: check(c1+': all selected thresholds translate',td['max_abs_difference']<=SCORE_TOL)
    for y,metric in enumerate(METRICS):
        rd=discrepancy(references[c0][:,y],references[c1][:,y])
        refproofs.append(dict(base=c0,comparison=c1,metric=metric,expect_invariant=invariant and y==1,**rd))
        if invariant and y==1: check(c1+': all 32768 reference recall values invariant',rd['max_abs_difference']<=RATE_TOL)
    for i in range(1000):
        row=dict(base=c0,comparison=c1,outer_index=i,expected_continuous_recall_invariance=invariant,
                 threshold_shift_residual=float(np.max(np.abs(b['point_thresholds'][i]-a['point_thresholds'][i]-delta))),
                 point_recall_difference=float(b['point'][i,1]-a['point'][i,1]),
                 fitted_recall_difference=float(b['fitted_truth'][i,1]-a['fitted_truth'][i,1]),
                 refit_recall_draw_max_difference=float(np.max(np.abs(b['refit_draws'][i,:,1]-a['refit_draws'][i,:,1]))),
                 conditional_recall_draw_max_difference=float(np.max(np.abs(b['conditional_draws'][i,:,1]-a['conditional_draws'][i,:,1]))),
                 recall_interval_max_difference=float(np.max(np.abs(b['intervals'][i,:,1]-a['intervals'][i,:,1]))),
                 recall_pvalue_max_difference=float(np.max(np.abs(b['pvalues'][i,:,1]-a['pvalues'][i,:,1]))),
                 point_fsr_difference=float(b['point'][i,0]-a['point'][i,0]),
                 fsr_interval_max_difference=float(np.max(np.abs(b['intervals'][i,:,0]-a['intervals'][i,:,0]))))
        rowproofs.append(row)
    if not invariant:
        check(c1+': quantized recall actually differs',
              np.any(a['refit_draws'][:,:,1] != b['refit_draws'][:,:,1]))
    check(c1+': FSR negative control differs', np.any(a['point'][:,0] != b['point'][:,0]))

# Bounded deterministic generator/calibration probes, never production outer().
sys.path.insert(0,str(SRC))
import review_core as core
import numerics as numerical
check('imported frozen generator',Path(core.__file__).resolve()==SRC/'review_core.py')
check('imported frozen calibration',Path(numerical.__file__).resolve()==SRC/'numerics.py')
probe_indices=[0,137,999]
for index in probe_indices:
    c0=conditions['H050_C']; base_d=core.generator(c0,40,10,index);base_e=core.generator(c0,120,20,index)
    weights=core.rng(30,index).multinomial(40,np.full(40,1/40),size=16)
    weights=np.vstack((np.ones(40,dtype=int),weights))
    plan0=numerical.Plan(base_d,both_labels=True);fit0=plan0.fit(weights)
    pred0=numerical.predictions(base_e,fit0)
    for cid in ('H065_C','S_H_C'):
        c=conditions[cid];delta=c['separation'];dev=core.generator(c,40,10,index);ev=core.generator(c,120,20,index)
        score_max=0.; labels_groups_same=True
        for base,new in ((base_d,dev),(base_e,ev)):
            labels_groups_same &= np.array_equal(base.y,new.y) and np.array_equal(base.g,new.g)
            for key in ('joint','late'):
                score_max=max(score_max,float(np.max(np.abs(getattr(new,key)-getattr(base,key)-delta*base.y[:,None]))))
        plan=numerical.Plan(dev,both_labels=True);fit=plan.fit(weights);pred=numerical.predictions(ev,fit)
        entry_groups_same=all(np.array_equal(x[1],y[1]) and np.array_equal(x[2],y[2])
                              for x,y in zip(plan0.entries,plan.entries))
        entry_shift_max=max(float(np.max(np.abs(y[0]-x[0]-delta))) for x,y in zip(plan0.entries,plan.entries))
        positive_equal=np.array_equal(pred0[:,base_e.y==1],pred[:,ev.y==1])
        negative_changes=int(np.count_nonzero(pred0[:,base_e.y==0] != pred[:,ev.y==0]))
        saved_fit_error=float(np.max(np.abs(fit[0]-data[cid]['point_thresholds'][index])))
        fitshift=float(np.max(np.abs(fit-fit0-delta)))
        r=dict(index=index,base='H050_C',comparison=cid,development_groups=40,evaluation_groups=120,
               calibration_weight_vectors=len(weights),labels_and_groups_identical=bool(labels_groups_same),
               score_shift_max_error=score_max,positive_order_group_ids_and_tie_boundaries_identical=entry_groups_same,
               sorted_positive_score_shift_max_error=entry_shift_max,
               fitted_threshold_shift_max_error=fitshift,positive_predictions_identical=positive_equal,
               negative_prediction_changes=negative_changes,saved_point_threshold_max_error=saved_fit_error)
        probes.append(r)
        check(cid+': deterministic translation probe '+str(index),labels_groups_same and entry_groups_same
              and positive_equal and negative_changes>0 and max(score_max,entry_shift_max,fitshift,saved_fit_error)<=SCORE_TOL,r)
for index in (0,137,32767):
    for cid in ('H050_C','H065_C','S_H_C'):
        c=conditions[cid];dev=core.generator(c,40,100,index)
        fit=numerical.Plan(dev,both_labels=True).fit(np.ones(40,dtype=int))[0]
        value=numerical.interaction(core.oracle(c,fit)[0])
        error=float(np.max(np.abs(value-references[cid][index])))
        check(cid+': deterministic reference contribution '+str(index),error<=RATE_TOL,error)
for path,digest in source_pins.items():check('source preserved '+path,sha(Path(path))==digest)

writecsv('table8-reaggregated.csv',[r for r in summary_rows if r['metric']=='recall' and r['target']=='procedure_average'])
writecsv('all-coverage-reaggregated.csv',summary_rows)
writecsv('reference-targets-reaggregated.csv',reference_rows)
writecsv('cross-condition-array-comparison.csv',comparisons)
writecsv('all-outer-index-proof.csv',rowproofs)
writecsv('all-reference-values-proof.csv',refproofs)
writecsv('deterministic-translation-probes.csv',probes)
writecsv('independent-bca-reconstruction.csv',bca_proofs)
writecsv('input-chunk-hashes.csv',receipts)
invariant_fields=[r for r in comparisons if r['expect_invariant'] and r['metric']=='recall']
ref_invariant=[r for r in refproofs if r['expect_invariant']]
result=dict(status='PASS' if not errors else 'FAIL',checks=len(checks),errors=errors,
            source=str(SRC),output=str(OUT),source_hashes=source_pins,freeze_sha256=sha(freeze_path),
            script_sha256=sha(Path(__file__)),chunk_receipts_checked=len(receipts),
            all_saved_outer_datasets_reaggregated=8000,focus_continuous_conditions=['H050_C','H065_C','S_H_C'],
            paired_outer_comparisons=2000,continuous_paired_recall_draw_values_compared_per_draw_construction=1998000,
            paired_reference_recall_values_compared=65536,deterministic_generator_calibration_probe_indices=probe_indices,
            deterministic_reference_probe_indices=[0,137,32767],new_outer_simulations=0,new_monte_carlo_experiments=0,
            new_model_calls=0,rate_comparison_tolerance=RATE_TOL,score_comparison_tolerance=SCORE_TOL,
            maximum_continuous_recall_saved_array_difference=max(r['max_abs_difference'] for r in invariant_fields),
            maximum_continuous_recall_reference_difference=max(r['max_abs_difference'] for r in ref_invariant),
            independently_reconstructed_bca_intervals=16000,
            independent_bca_max_endpoint_difference=max(r['max_abs_difference'] for r in bca_proofs),
            environment=dict(python=sys.executable,platform=platform.platform(),numpy=np.__version__,storage='E: SATA HDD'))
(OUT/'audit-result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2,ensure_ascii=False))
if errors:sys.exit(1)
