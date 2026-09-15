"""Read-only audit of stored cohorts; no model calls or inferential simulations.

Run with E:/SoftwareX/Start-GraspExperiment.ps1 -PythonArguments @(this_file).
Outputs are confined to this amendment's empirical directory.
"""
from pathlib import Path
import collections, csv, gzip, hashlib, json, math, platform, sys
import numpy as np

OUT = Path(__file__).resolve().parent
STUDY = OUT.parents[2]
PREV = STUDY / 'amendments/score-ties-revision-20260915-v1/scorer'
PACKAGE = STUDY / 'staging/p0-e2e-20260914-v1/package/release-v6'
MANUSCRIPT = STUDY / 'manuscript/ieee-access-draft-20260915-v5-language'
sys.path.insert(0, str(PACKAGE / 'src'))
import empirical_core_v2 as core

PINS = {}
def source(p):
    p = Path(p)
    PINS[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p
def read(p): return json.loads(source(p).read_text(encoding='utf-8-sig'))
def csvread(p):
    with source(p).open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def writejson(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
def writecsv(name, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f, keys);w.writeheader();w.writerows(rows)
def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def auroc(y,score):
    """Empirical P(score_success > score_failure) + 0.5 P(tie)."""
    y=np.asarray(y);score=np.asarray(score)
    _,ii=np.unique(score,return_inverse=True)
    neg=np.bincount(ii,weights=(y==0).astype(float));pos=np.bincount(ii,weights=(y==1).astype(float))
    return float(np.sum(pos*(np.cumsum(neg)-.5*neg))/(pos.sum()*neg.sum()))

source(Path(core.__file__))
with gzip.open(source(PREV/'inputs/collections.json.gz'), 'rt', encoding='utf-8') as f: collections_in = json.load(f)
cases = read(PREV/'inputs/cases.json')
paper = read(MANUSCRIPT/'evidence/paper-tables.json')
cohort_reference = {(x['dataset'], x['split']):x for x in paper['tables']['cohorts'] if x['variant']=='main'}
cohorts = core.build_cohorts([r for rr in collections_in.values() for r in rr])
metadata = {}
for collection, rows in collections_in.items():
    for r in rows:
        k=(r['dataset'],r['split'],r['sample_id'])
        value={x:r[x] for x in ('group_id','label','task_family')}
        assert k not in metadata or metadata[k]==value
        metadata[k]=value

order=[('rlbenchfail','dev'),('rlbenchfail','confirmation'),('ur5fail','external'),('reassemble','dev'),('reassemble','confirmation')]
pretty={'rlbenchfail':'RLBenchFail','ur5fail':'UR5Fail','reassemble':'REASSEMBLE'}
summaries=[]; groups_out=[]; memberships=[]
for dataset,split in order:
    rows={sample:r for (ds,sp,sample),r in metadata.items() if (ds,sp)==(dataset,split)}
    grouped=collections.defaultdict(list)
    for sample,r in rows.items():
        grouped[r['group_id']].append(r)
        memberships.append(dict(dataset=dataset,split=split,sample_id=sample,**r))
    counts=np.array([[sum(z['label']==y for z in rs) for y in (0,1)] for _,rs in sorted(grouped.items())])
    G=len(grouped); n=len(rows); fail,succ=counts.sum(axis=0).tolist()
    row=dict(dataset=dataset,split=split,trials=n,groups=G,successes=succ,failures=fail,
             failure_prevalence=fail/n,success_prevalence=succ/n,
             accept_all_fsr=1.0,accept_all_recall=1.0,accept_all_accuracy=succ/n,
             accept_all_failure_fraction_among_accepted=fail/n,
             group_size_min=int(counts.sum(axis=1).min()),group_size_max=int(counts.sum(axis=1).max()))
    for y,label in ((0,'failure'),(1,'success')):
        ns=counts[:,y]; total=int(ns.sum()); Gy=int((ns>0).sum())
        row.update({f'{label}_contributing_groups':Gy,
                    f'{label}_kish_class_weight_groups':float(total**2/np.dot(ns,ns)),
                    f'{label}_largest_group_count':int(ns.max()),
                    f'{label}_largest_class_weight':float(ns.max()/total),
                    f'{label}_zero_class_bootstrap_probability':float(((G-Gy)/G)**G),
                    f'{label}_expected_distinct_groups_per_bootstrap':float(Gy*(1-(1-1/G)**G))})
    row['mixed_label_groups']=int(np.all(counts>0,axis=1).sum())
    ref=cohort_reference[(dataset,split)]
    for key,refkey in [('trials','samples'),('groups','groups'),('successes','success_samples'),('failures','failure_samples'),('success_contributing_groups','groups_with_success'),('failure_contributing_groups','groups_with_failure')]:
        assert row[key]==int(ref[refkey]),(dataset,split,key,row[key],ref[refkey])
    summaries.append(row)
    for (gid,rs),cc in zip(sorted(grouped.items()),counts):
        groups_out.append(dict(dataset=dataset,split=split,group_id=gid,trials=len(rs),failure_trials=int(cc[0]),success_trials=int(cc[1]),failure_weight=float(cc[0]/fail),success_weight=float(cc[1]/succ)))

duplicates=[]
for (model,dataset,split,seed),cohort in cohorts.items():
    for method in ('joint','late'):
        p=cohort.pools[method]
        for j,pair in enumerate(cohort.pairs):
            for y in (0,1):
                values=p.scores[(cohort.y==y)&p.available[:,j],j]
                vals,freq=np.unique(values,return_counts=True)
                n=len(values)
                duplicates.append(dict(model=model,dataset=dataset,split=split,seed=seed,method=method,pair=pair,label=y,
                    valid_scores=n,distinct_scores=len(vals),duplicate_excess=1-len(vals)/n,
                    observations_in_ties_fraction=float(freq[freq>1].sum()/n),
                    unordered_pair_tie_probability=float(np.sum(freq*(freq-1))/(n*(n-1))),
                    largest_atom_fraction=float(freq.max()/n)))
duplicate_summary=[]
for dataset,split in order:
    for method in ('joint','late'):
        selected=[r for r in duplicates if (r['dataset'],r['split'],r['method'])==(dataset,split,method)]
        duplicate_summary.append(dict(dataset=dataset,split=split,method=method,cells=len(selected),
            median_duplicate_excess=float(np.median([r['duplicate_excess'] for r in selected])),
            median_observations_in_ties_fraction=float(np.median([r['observations_in_ties_fraction'] for r in selected])),
            median_unordered_pair_tie_probability=float(np.median([r['unordered_pair_tie_probability'] for r in selected]))))

# Operating metrics are paired original analysis results; every scorer/method is retained.
ops = csvread(PREV/'results-v1/operating.csv')
op_index={(r['case'],r['scorer'],r['method'],r['metric']):r for r in ops}
summary_map={(r['dataset'],r['split']):r for r in summaries}
baseline_ops=[]
for c in cases:
    cohort_summary=summary_map[(c['target_dataset'],c['target_split'])]
    for scorer in ('accept_all','bare','space'):
        for method in (('accept_all',) if scorer=='accept_all' else ('joint_pooled','joint_pair','late_pooled','late_pair')):
            if scorer=='accept_all': fsr=recall=1.0
            else:
                fsr=float(op_index[(c['case_id'],scorer,method,'false_success_rate')]['estimate'])
                recall=float(op_index[(c['case_id'],scorer,method,'success_recall')]['estimate'])
            prev=cohort_summary['failure_prevalence']
            baseline_ops.append(dict(case=c['case_id'],dataset=c['target_dataset'],split=c['target_split'],scorer=scorer,method=method,
                target_failure_prevalence=prev,fsr=fsr,success_recall=recall,
                failure_rejection_gain_over_accept_all=1-fsr,success_recall_loss_vs_accept_all=1-recall,
                proportion_all_trials_accepted_failures=prev*fsr,
                fraction_failures_among_accepted=(prev*fsr)/(prev*fsr+(1-prev)*recall),
                status='deterministic_label_free_baseline' if scorer=='accept_all' else 'saved_paired_posthoc_scorer_comparison'))

# Counts from rows, with successful passes and scheduled request records separated.
request_counts=[]
for col,rows in collections_in.items():
    for ds,sp in sorted({(r['dataset'],r['split']) for r in rows}):
        rr=[r for r in rows if (r['dataset'],r['split'])==(ds,sp)]
        request_counts.append(dict(scope=col,dataset=ds,split=sp,planned_request_records=len(rr),successful_stored_forward_passes=sum(bool(r['available']) for r in rr),unavailable_request_records=sum(not r['available'] for r in rr)))
assert sum(r['planned_request_records'] for r in request_counts)==89052
assert sum(r['successful_stored_forward_passes'] for r in request_counts)==89051
cost=csvread(STUDY/'staging/wave3/cost-analysis/final-cpu-recovery-v2/native-execution-totals.csv')
cost_count=[r for r in cost if r['metric']=='calls']
cost_summary=collections.defaultdict(lambda:[0,0])
for r in cost_count:
    key=(r['axis'],r['phase']);cost_summary[key][0]+=int(r['n_native_requests']);cost_summary[key][1]+=int(r['observed_sum'])
native_path=source(STUDY/'staging/wave3/cost-analysis/final-cpu-recovery-v2/native-request-costs.csv.gz')
native_counts=collections.defaultdict(lambda:[0,0,collections.Counter()])
with gzip.open(native_path,'rt',encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        assert r['inference_available'] in ('True','False')
        key=(r['axis'],r['phase']);native_counts[key][0]+=1
        native_counts[key][1]+=r['inference_available']=='True'
        native_counts[key][2][r['status']]+=1
cost_rows=[dict(axis=a,phase=p,scheduled_native_request_records=x[0],recorded_calls_metric_sum=x[1],
               available_stored_outputs=native_counts[(a,p)][1],unavailable_outputs=native_counts[(a,p)][0]-native_counts[(a,p)][1])
           for (a,p),x in sorted(cost_summary.items())]
for r in cost_rows:
    assert r['scheduled_native_request_records']==native_counts[(r['axis'],r['phase'])][0]
    assert r['recorded_calls_metric_sum']==r['available_stored_outputs']
assert sum(x['scheduled_native_request_records'] for x in cost_rows)==89576
assert sum(x['available_stored_outputs'] for x in cost_rows)==89575
diagnostic=csvread(PACKAGE/'extensions/scorer/reference/metrics.csv')
diagnostic=[r for r in diagnostic if r['context'] in ('joint','late')]
paired=csvread(PACKAGE/'extensions/scorer/reference/scorer-pairs.csv')
diag_completion=read(PACKAGE/'extensions/scorer/reference/completion.json')
assert diag_completion['planned_contexts']==288 and diag_completion['planned_branches']==864
assert diag_completion['branch_status_counts']=={'SUCCESS':864}
for fname in ('metrics.csv','scorer-pairs.csv'):
    assert hashlib.sha256((PACKAGE/'extensions/scorer/reference'/fname).read_bytes()).hexdigest()==diag_completion['output_sha256'][fname]
known_duplicate_medians={('rlbenchfail','dev'):(46.591,34.787),('rlbenchfail','confirmation'):(77.247,67.987),('ur5fail','external'):(43.182,31.916),('reassemble','dev'):(86.215,80.115),('reassemble','confirmation'):(71.505,64.987)}
for r in duplicate_summary:
    expected=known_duplicate_medians[(r['dataset'],r['split'])][0 if r['method']=='joint' else 1]
    assert round(100*r['median_duplicate_excess'],3)==expected

# Full-cohort discrimination is descriptive. Scores preserve the original sign,
# exact saved A/B odds, and the same derived mean-log-odds Late construction.
assert auroc([0,0,1,1],[0,0,1,1])==1.0
assert auroc([0,0,1,1],[1,1,0,0])==0.0
assert auroc([0,0,1,1],[0,0,0,0])==0.5
auroc_pair=[];auroc_seed=[];auroc_summary=[]
for scorer in ('bare','space'):
    if scorer=='bare': cc=cohorts
    else:
        new_rows=[dict(r,score=r['space_score'],logodds=r['space_logodds']) for rr in collections_in.values() for r in rr]
        cc=core.build_cohorts(new_rows)
    for (model,dataset,split,seed),cohort in cc.items():
        for method in ('joint','late'):
            pool=cohort.pools[method]; pair_aucs=[]
            for j,pair in enumerate(cohort.pairs):
                valid=pool.available[:,j]&np.isfinite(pool.scores[:,j]);yy=cohort.y[valid];xx=pool.scores[valid,j]
                auc=auroc(yy,xx);pair_aucs.append(auc)
                # Independent direct U statistic for one pair per cohort/seed/method.
                if j==0:
                    neg=np.sort(xx[yy==0]);pos=xx[yy==1]
                    direct=float(np.mean((np.searchsorted(neg,pos,side='left')+np.searchsorted(neg,pos,side='right'))/(2*len(neg))))
                    assert abs(direct-auc)<1e-14
                auroc_pair.append(dict(model=model,dataset=dataset,split=split,scorer=scorer,seed=seed,method=method,pair=pair,
                    planned_trials=len(yy)+int((~valid).sum()),available_trials=int(valid.sum()),successes=int((yy==1).sum()),failures=int((yy==0).sum()),
                    unavailable=int((~valid).sum()),auroc=auc))
            valid=pool.available&np.isfinite(pool.scores);yy=np.broadcast_to(cohort.y[:,None],pool.scores.shape)[valid];xx=pool.scores[valid]
            auroc_seed.append(dict(model=model,dataset=dataset,split=split,scorer=scorer,seed=seed,method=method,
                pairs=len(pair_aucs),mean_within_pair_auroc=float(np.mean(pair_aucs)),within_pair_auroc_min=float(min(pair_aucs)),within_pair_auroc_max=float(max(pair_aucs)),
                pooled_score_auroc=auroc(yy,xx),planned_sample_pairs=pool.scores.size,available_sample_pairs=int(valid.sum()),
                available_success_sample_pairs=int((yy==1).sum()),available_failure_sample_pairs=int((yy==0).sum()),
                unavailable_sample_pairs=int((~valid).sum())))
for dataset,split in order:
    for method in ('joint','late'):
        for scorer in ('bare','space'):
            rows=[r for r in auroc_seed if (r['dataset'],r['split'],r['method'],r['scorer'])==(dataset,split,method,scorer)]
            wp=[r['mean_within_pair_auroc'] for r in rows];pooled=[r['pooled_score_auroc'] for r in rows]
            auroc_summary.append(dict(dataset=dataset,split=split,method=method,scorer=scorer,seeds=len(rows),
                mean_within_pair_auroc=float(np.mean(wp)),within_pair_seed_min=float(min(wp)),within_pair_seed_max=float(max(wp)),
                mean_pooled_score_auroc=float(np.mean(pooled)),pooled_seed_min=float(min(pooled)),pooled_seed_max=float(max(pooled)),
                total_unavailable_sample_pairs_across_seeds=sum(r['unavailable_sample_pairs'] for r in rows),
                inference='descriptive_only_no_new_bootstrap_or_confirmatory_test'))
source(MANUSCRIPT/'main-draft.md');source(MANUSCRIPT/'evidence/methods-appendix.md')
for name,rows in [('cohort-baselines.csv',summaries),('group-class-counts.csv',groups_out),('sample-memberships.csv',memberships),('score-duplication-by-class-pair-seed.csv',duplicates),('score-duplication-summary.csv',duplicate_summary),('operating-points-with-accept-all.csv',baseline_ops),('request-counts.csv',request_counts),('cost-accounting-counts.csv',cost_rows),('development-auroc-all-variants.csv',diagnostic),('development-paired-scorer-comparisons.csv',paired),('full-cohort-auroc-by-pair-seed.csv',auroc_pair),('full-cohort-auroc-by-seed.csv',auroc_seed),('full-cohort-auroc-summary.csv',auroc_summary)]:writecsv(name,rows)

cohort_table=table(['Cohort','Trials (success/failure)','Groups (total/success/failure)','Failure prevalence (%)','Accept-all FSR/recall (%)'],[
    [pretty[r['dataset']]+' '+r['split'],f"{r['trials']} ({r['successes']}/{r['failures']})",f"{r['groups']} / {r['success_contributing_groups']} / {r['failure_contributing_groups']}",f"{100*r['failure_prevalence']:.3f}",'100.000 / 100.000'] for r in summaries])
group_table=table(['Cohort','FSR contributing groups','Failure-weight concentration count','Largest failure-group weight (%)','No-failure bootstrap probability'],[
    [pretty[r['dataset']]+' '+r['split'],r['failure_contributing_groups'],f"{r['failure_kish_class_weight_groups']:.3f}",f"{100*r['failure_largest_class_weight']:.3f}",f"{r['failure_zero_class_bootstrap_probability']:.3e}"] for r in summaries])
re_ops=[r for r in baseline_ops if r['case']=='smolvlm_instruct__reassemble_local']
re_table=table(['Scorer','Policy','FSR (%)','Recall (%)','Failure rejection gain (pp)','Recall loss (pp)'],[[r['scorer'],r['method'],f"{100*r['fsr']:.3f}",f"{100*r['success_recall']:.3f}",f"{100*r['failure_rejection_gain_over_accept_all']:.3f}",f"{100*r['success_recall_loss_vs_accept_all']:.3f}"] for r in re_ops])
(OUT/'suggested-tables.md').write_text('# Cohorts, prevalence, and the accept-all baseline\n\n'+cohort_table+'\n\nCounts of success- and failure-contributing groups overlap when a group contains both outcomes. The accept-all policy accepts every planned trial without consulting a model score, so its FSR and recall are both 100%, including the one unavailable development model request. FSR is the class-conditional false-positive rate; prevalence is the proportion of trials labeled as failure.\n\n# Group contribution and concentration\n\n'+group_table+'\n\nThe concentration count is (sum_g n_g0)^2 / sum_g n_g0^2, where n_g0 is the number of failure trials in group g. It describes class-weight balance; it is not an effective sample size that validates a bootstrap interval and is not used as degrees of freedom. Under the empirical resampling distribution that draws G whole groups uniformly with replacement, the probability of no failure observations is ((G-G0)/G)^G. Small no-class probabilities rule out denominator absence as a common resampling event; they do not establish coverage or account for threshold-selection uncertainty.\n\n# All REASSEMBLE-local bare/space operating points\n\n'+re_table+'\n\nAll four policies and both scorers are included to avoid selecting a favorable operating point. The leading-space scoring comparison is post hoc on the original evaluation cohort, with separate development recalibration; it does not constitute a new independent confirmation set. Its balanced development diagnostic AUROC is reported separately from these complete-cohort operating points.\n',encoding='utf-8')
auc_table=table(['Cohort','Method','Bare mean within-pair AUROC','Space mean within-pair AUROC','Bare / space pooled AUROC'],[
    [pretty[ds]+' '+sp,method,
     f"{next(r for r in auroc_summary if (r['dataset'],r['split'],r['method'],r['scorer'])==(ds,sp,method,'bare'))['mean_within_pair_auroc']:.4f}",
     f"{next(r for r in auroc_summary if (r['dataset'],r['split'],r['method'],r['scorer'])==(ds,sp,method,'space'))['mean_within_pair_auroc']:.4f}",
     ' / '.join(f"{next(r for r in auroc_summary if (r['dataset'],r['split'],r['method'],r['scorer'])==(ds,sp,method,sc))['mean_pooled_score_auroc']:.4f}" for sc in ('bare','space'))]
    for ds,sp in order for method in ('joint','late')])
(OUT/'full-cohort-auroc-table.md').write_text('# Full-cohort descriptive discrimination\n\n'+auc_table+'\n\nAUROC uses the original success-positive score direction, awarding half credit for exact ties. For the mean within-pair estimand, AUROC is calculated separately for each camera pair with equal trial weights, then averaged equally across pairs and the three recorded seeds. The pooled-score estimand combines all sample-pair scores before forming success/failure comparisons; it additionally compares scores from different camera pairs and can reflect pair-location differences. The two summaries answer different descriptive questions. Repeated pairs and seeds do not create independent trials.\n\nAll evaluation scores are available. REASSEMBLE development has one unavailable seed-17 Single-c0 success request, inducing one unavailable success in each of the c0_c1 and c0_c2 Late pairs. These are omitted only from score-ranking AUROC because no score exists; the calibrated-policy analyses retain their original planned denominator and reject unavailable computations. These two sample-pair omissions occur identically for bare and space. The available per-pair class counts are in full-cohort-auroc-by-pair-seed.csv. Seed ranges are recorded in the summary CSV; all AUROCs are seed-identical except the affected REASSEMBLE development Late entries. No AUROC bootstrap interval or new confirmatory test is added.\n\nThe full held-out results show limited discrimination: RLBench mean within-pair AUROC spans 0.491–0.528, UR5 0.384–0.405, and REASSEMBLE 0.557–0.579. REASSEMBLE has a modest descriptive ordering signal on its full evaluation cohort; the development-subset space-AB Joint AUROC of 0.657 is not its held-out AUROC. The fixed original score direction is retained even when AUROC is below 0.5.\n',encoding='utf-8')

for path,h in PINS.items(): assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h, path
source(Path(__file__))
writejson('source-hashes.json',PINS)
writejson('audit-results.json',dict(status='PASS',cohorts=summaries,cohort_metadata_reference_checks=30,
    request_counts=request_counts,cost_counts=cost_rows,source_files_unchanged=len(PINS)-1,
    request_semantics='planned records and available outputs; the calls metric sum equals available outputs but does not prove whether an unavailable orphan executed internally',
    duplicate_excess_table26_checks=10,diagnostic_contexts=288,diagnostic_operations=864,diagnostic_operation_successes=864,
    full_cohort_auroc_summary_rows=len(auroc_summary),full_cohort_auroc_seed_rows=len(auroc_seed),full_cohort_auroc_pair_rows=len(auroc_pair),
    new_model_calls=0,bootstrap_resampling_performed=False,storage='E: SATA HDD',python=sys.executable,
    python_version=platform.python_version(),numpy_version=np.__version__,
    interpretation={'UR5_35_44':'success/failure trials, not contributing groups',
       'UR5_class_groups':'29 success-contributing and 31 failure-contributing groups',
       'effective_group_count':'descriptive Kish class-weight concentration, not inferential effective degrees of freedom',
       'development_diagnostic':'balanced 48-trial subsets; not full evaluation discrimination'}))
print(json.dumps({'status':'PASS','cohorts':summaries,'cost_counts':cost_rows},indent=2))
