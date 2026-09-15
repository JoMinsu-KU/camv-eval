"""Read-only numeric comparison of v4 new tables with verified CSVs."""
from pathlib import Path
import csv,re,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];STUDY=ROOT.parents[1]
V4=STUDY/'manuscript/ieee-access-draft-20260915-v4';V3=STUDY/'manuscript/ieee-access-draft-20260914-v3'
def text(p):return p.read_text(encoding='utf-8-sig')
def tables(s):return {int(k):v for k,v in re.findall(r'\*\*Table (\d+)\.[^\n]*\n\n((?:\|[^\n]*\n)+)',s)}
def data(t):return [[c.strip() for c in line.strip('|').split('|')] for line in t.strip().splitlines()[2:]]
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
main=text(V4/'main-draft.md');app=text(V4/'evidence/methods-appendix.md');tt=tables(main)|tables(app)
oldm=tables(text(V3/'main-draft.md'));olda=tables(text(V3/'evidence/methods-appendix.md'))
for j in range(2,15):assert tt[j]==oldm[j],('oldmain',j)
for j in [15,*range(17,26)]:
    a=data(olda[j]);b=data(tt[j+4]);assert all(r in b for r in a),('oldappendix',j)
S=ROOT/'scorer/results-v1';T=ROOT/'simulation/summary-v1'
ops={(r['case'],r['scorer'],r['method'],r['metric']):r for r in rows(S/'operating.csv')}
it={(r['case'],r['scorer'],r['metric']):r for r in rows(S/'interactions.csv')}
cv={(r['condition'],r['metric'],r['algorithm'],r['target']):r for r in rows(T/'coverage.csv')}
tr={(r['condition'],r['metric'],r['algorithm']):r for r in rows(T/'centered-tests.csv')}
rf={(r['condition'],r['metric']):r for r in rows(T/'reference-targets.csv')}
ct={(r['condition'],r['metric']):r for r in rows(T/'centers.csv')}
kt={(r['condition'],int(r['policy_threshold']),r['quantity']):r for r in rows(T/'threshold-atoms.csv')}
dg=rows(S/'decision-disagreement.csv')
casemap={a:'smolvlm_instruct__'+b for a,b in [('RLBench','rlbenchfail'),('UR5 transfer','ur5fail'),('REASSEMBLE local','reassemble_local'),('RLBench→REASSEMBLE','reassemble_rl_transfer')]}
met={'FSR':'false_success_rate','Recall':'success_recall'};ncomp=0;nrows=0
def chk(cells,expected,precision=3):
    global ncomp,nrows
    nums=re.findall(r'[-+]?\d+(?:\.\d+)?',' '.join(cells));assert len(nums)==len(expected),(cells,nums,expected)
    digs=[precision]*len(nums) if isinstance(precision,int) else precision
    for a,b,d in zip(nums,expected,digs):assert abs(float(a)-float(b))<=.500001*10**(-d),(cells,a,b,d)
    ncomp+=len(nums);nrows+=1
pol=('joint_pooled','joint_pair','late_pooled','late_pair')
for r in data(tt[15]):chk(r[1:],[100*float(ops[casemap[r[0]],'space',p,m]['estimate']) for p in pol for m in met.values()])
for tid,m in ((16,'false_success_rate'),(30,'success_recall')):
    for r in data(tt[tid]):chk(r[1:],[100*float(it[casemap[r[0]],v,m][k]) for v in ('bare','space','space_minus_bare') for k in ('estimate','refit_lower','refit_upper')])
for tid,m in ((17,'false_success_rate'),(18,'success_recall')):
    for r in data(tt[tid]):
        c=r[0];e=[100*float(rf[c,m][k]) for k in ('truth','reference_mcse')]
        e += [100*float(cv[c,m,'conditional_percentile',target]['rate']) for target in ('fitted','procedure')]
        e += [100*float(cv[c,m,a,'procedure']['rate']) for a in ('refit_percentile','refit_basic')]
        e += [100*float(cv[c,m,'refit_percentile','procedure']['mean_width']),100*float(tr[c,m,'refit']['rate'])]
        chk(r[1:],e,[4,4,1,1,1,1,3,1])
for r in data(tt[31]):chk(r[2:],[100*float(cv[r[0],met[r[1]],a,target]['rate']) for a in ('conditional_percentile','refit_percentile','refit_basic','cluster_sandwich_t') for target in ('fitted','procedure')],1)
for r in data(tt[32]):chk(r[2:],[100*float(tr[r[0],met[r[1]],a][k]) for a in ('conditional','refit') for k in ('rate','wilson_lower','wilson_upper')],[1,2,2,1,2,2])
for r in data(tt[33]):
    a=ct[r[0],met[r[1]]];kk=('point_sd','percentile_midpoint_sd','basic_midpoint_sd','point_shift_correlation','point_bias','mean_bootstrap_bias')
    chk(r[2:],[float(a[k])*(1 if k=='point_shift_correlation' else 100) for k in kk])
for r in data(tt[34]):
    c=r[0];e=[100*float(kt[c,j,k]['mean']) for k in ('positive_empirical_atom','positive_population_atom','development_recall') for j in (0,4)]
    with np.load(T/(c+'-compact.npz'),allow_pickle=False) as z:e += [100*z['population_policy'][:,j,1].mean() for j in (0,2)]
    chk(r[1:],e,2)
for r in data(tt[35]):
    case=casemap[r[0]];method=r[1].replace(' ','_');e=[]
    for lab in ('all','failure','success'):e.append(100*np.mean([float(a['sample_pair_disagreement']) for a in dg if a['case']==case and a['method']==method and a['label']==lab]))
    chk(r[2:],e,2)
print(json.dumps({'status':'PASS','new_tables':[15,16,17,18,30,31,32,33,34,35],'new_data_rows':nrows,'numeric_components':ncomp,'old_main_tables_exact':list(range(2,15)),'old_appendix_scientific_rows_preserved_with_plus4_renumbering':[15,*range(17,26)],'timing_table16_to20':'Prose stage labels updated; September15 provenance added','source_hashes':{str(p.relative_to(V4)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (V4/'main-draft.md',V4/'evidence/methods-appendix.md')}},indent=2))
