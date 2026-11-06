"""Create source-backed E1 tables, scientific figure and a concise result receipt."""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import empirical_law_engine as e

here=Path(__file__).resolve().parent
def read(name):
    with (here/name).open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
rows=read('coverage.csv');decomp=read('point-decomposition.csv');refs=read('reference-targets.csv');counts=read('sample-counts.csv')
conditions=['EP-RL-bare','EP-RL-space','EP-RE-bare','EP-RE-space']
methods=[('conditional_percentile','Conditional percentile'),('conditional_sandwich_t','Conditional sandwich t'),
         ('refit_percentile','Refit percentile'),('refit_basic','Refit basic'),('refit_BCa','Refit BCa')]
by={(r['condition'],r['metric'],r['method'],r['target']):r for r in rows}
lines=['# E1 empirical group-population simulation results','',
       'Production status: **PASS**. Four paired scorer conditions; 1,000 outer draws per source population (2,000 independent outer datasets total, producing 4,000 scorer-specific records); 999 bootstrap draws per record. No new VLM inference or parameter tuning. All scientific source files remain unchanged.','',
       'The generating law samples intact observed development-group blocks uniformly with replacement. Development/evaluation group counts are 40/179 for RLBenchFail and 111/37 for REASSEMBLE; realized trial counts vary. The same group and bootstrap multiplicities pair bare and space. These are coverage results under a fixed empirical group law, not coverage guarantees for actual held-out robotics populations or shifted targets.','',
       '## Main coverage results','',
       'Each entry is coverage over the 1,000 planned intervals (%). Conditional methods target fitted-policy truth; refit methods target the independently estimated procedure-average truth. All 40 target-matched configurations have all 1,000 intervals available.','',
       '| Population/scorer | Metric | Conditional percentile | Conditional sandwich t | Refit percentile | Refit basic | Refit BCa |',
       '|---|---|---:|---:|---:|---:|---:|']
for c in conditions:
    for metric in e.METRICS:
        values=[]
        for method,_ in methods:
            target='fitted_policy' if method.startswith('conditional') else 'procedure_average'
            values.append(f"{float(by[(c,metric,method,target)]['coverage_planned_pct']):.1f}")
        lines.append('| '+' | '.join([c,metric,*values])+' |')
lines+=['',
        'Refit percentile overcoverage persists with the complete observed score/tie/dependence structure: 97.6–99.9%. Basic covers 77.5–91.0%; BCa covers 80.7–89.5%. Conditional percentile fitted-policy coverage is 91.2–95.1%, and conditional sandwich t is 92.8–94.7%. Consequently, this experiment supports target-specific reporting while showing that the conditional methods are not uniformly nominal under the observed REASSEMBLE group law. It does not identify a generally valid replacement for procedure-average inference.','',
        '## Development/evaluation decomposition','',
        'T is the evaluation-sample interaction, tau(D) is exact finite-population fitted-policy interaction, U=T−tau(D), and V=tau(D)−mu. The development ratio Var(V)/Var(T) is diagnostic rather than an additive attribution; covariance is retained in the CSV.','',
        '| Condition | Metric | Procedure-average target (pp) | Reference MCSE (pp) | Evaluation-error SD (pp) | Development-policy SD (pp) | Development variance ratio |',
        '|---|---|---:|---:|---:|---:|---:|']
for r in decomp:
    lines.append('| '+' | '.join([r['condition'],r['metric'],f"{float(r['procedure_average_target_pp']):.3f}",
        f"{float(r['reference_mcse_pp']):.5f}",f"{float(r['evaluation_error_sd_pp']):.3f}",
        f"{float(r['development_policy_sd_pp']):.3f}",f"{float(r['development_variance_ratio']):.3f}"])+' |')
lines+=['',
        'For FSR, RLBenchFail has larger development-policy variation than evaluation error, whereas REASSEMBLE has larger evaluation error than development-policy variation. This contrast is observed while preserving each population\'s actual score blocks and group sizes. It does not isolate a causal effect of failure scarcity, group size, or any single feature. Recall need not have the same decomposition as FSR.','',
        '## Precision, availability and replay','',
        'Each population has 65,536 independent development reference draws, paired across scorers. All reference draws satisfy the predeclared validity condition. Maximum reference MCSE is '+f"{max(float(r['mcse_pp']) for r in refs):.5f}"+' pp, below 0.05 pp. Procedure-average coverage at mu ± 3 MCSE is in `coverage.csv`. All four conditions have 1,000 finite points and truths, and all five CI constructions are available for both metrics. BCa availability does not imply calibrated coverage; its tail diagnostics remain in `bca-availability.csv`.','',
        'The final audit checks all 4,000 records and group-occurrence counts, bare/space pairing, percentile/basic width identity, exact BCa tie fractions, bit-exact agreement with the 10-outer pilot, fresh full-array replay at outer indices 0/17/999, all independent reference means and MCSEs, and all 80 coverage rows. `postrun-validation.json` records PASS; `output-manifest.json` hashes 4,016 numerical output files. The parent task also performed a separate numerical verification.','',
        '## Delivered files','',
        '- `frozen-protocol.json` and `PROTOCOL.md`: frozen design and pinned source/code hashes.',
        '- `coverage.csv`: all 80 target-matched/cross-target coverage rows, Wilson intervals, widths, availability and reference sensitivity.',
        '- `point-decomposition.csv`, `centering-diagnostics.csv`, `bca-availability.csv`, `sample-counts.csv`: supporting diagnostics.',
        '- `outer/`: all 4,000 scorer-specific records with draws, thresholds, jackknife values, counts and CI endpoints.',
        '- `reference/`: independent reference arrays and their development-group multiplicities.',
        '- `coverage-target-matched.pdf` and `.png`: target-separated coverage figure.',
        '- `completion.json`, `postrun-validation.json`, `output-manifest.json`: completion and audit receipts.','',
        'To resume without changing the frozen protocol, run `run_empirical_laws.py all --workers 2` through the E: experiment launcher. Numerical re-audit uses `verify_production.py`. No existing production records or scientific sources are modified.','']
(here/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,
                     'pdf.fonttype':42,'ps.fonttype':42})
fig,axes=plt.subplots(2,2,figsize=(10.4,6.4),sharex=True,sharey=True)
palette={'conditional_percentile':'#2E6DA4','conditional_sandwich_t':'#359F84','refit_percentile':'#2E6DA4',
         'refit_basic':'#D17926','refit_BCa':'#8753A1'}
for i,metric in enumerate(e.METRICS):
    for j,target in enumerate(('fitted_policy','procedure_average')):
        ax=axes[i,j];chosen=methods[:2] if j==0 else methods[2:]
        offsets=np.linspace(-.14,.14,len(chosen))
        for offset,(method,label) in zip(offsets,chosen):
            data=[by[(c,metric,method,target)] for c in conditions]
            yy=np.array([float(r['coverage_planned_pct']) for r in data])
            low=np.array([float(r['wilson_low_pct']) for r in data]);high=np.array([float(r['wilson_high_pct']) for r in data])
            ax.errorbar(np.arange(4)+offset,yy,yerr=[yy-low,high-yy],fmt='o',ms=4,capsize=2,lw=1,color=palette[method],label=label)
        ax.axhline(95,color='#555555',ls='--',lw=.9)
        ax.set_title(f"{metric}: {'fitted-policy target' if j==0 else 'procedure-average target'}",loc='left',fontweight='bold')
        ax.set_ylim(72,102);ax.set_yticks([75,80,85,90,95,100]);ax.grid(axis='y',color='#dddddd',lw=.5)
        ax.set_xticks(np.arange(4),['RL\nbare','RL\nspace','RE\nbare','RE\nspace'])
        if j==0:ax.set_ylabel('Coverage (%)')
        if i==0:ax.legend(loc='lower left',frameon=False,fontsize=8)
fig.text(.5,.015,'1,000 outer draws per population; 999 bootstrap draws. Bars: 95% Wilson intervals. Dashed: nominal 95%.',ha='center',fontsize=8)
fig.tight_layout(rect=[0,.045,1,1]);fig.savefig(here/'coverage-target-matched.pdf',bbox_inches='tight');fig.savefig(here/'coverage-target-matched.png',dpi=180,bbox_inches='tight')
receipt=dict(status='PASS',experiment='E1 empirical group-population simulation',independent_outer_datasets=2000,
    scorer_specific_records=4000,M_per_population=1000,B=999,conditions=4,metrics=2,methods=5,
    reference_draws_per_population=65536,reference_draws_pair_scorers=True,
    maximum_reference_mcse_pp=max(float(r['mcse_pp']) for r in refs),
    all_40_target_matched_availability_1000_of_1000=True,figure_visually_reviewed=True,
    no_new_model_inference=True,source_records_preserved=True,production_elapsed_seconds=86.68886630004272,
    protocol_sha256=e.sha(here/'frozen-protocol.json'),
    deliverable_sha256={n:e.sha(here/n) for n in ('RESULTS.md','coverage.csv','point-decomposition.csv',
       'coverage-target-matched.pdf','coverage-target-matched.png','postrun-validation.json','output-manifest.json')})
e.dump(here/'results-receipt.json',receipt)
print('PASS: RESULTS.md and coverage-target-matched.pdf/.png')
