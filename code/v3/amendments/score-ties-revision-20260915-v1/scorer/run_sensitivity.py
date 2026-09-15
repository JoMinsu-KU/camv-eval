"""Saved-forward sensitivity, exact original grouping and paired bootstrap."""
from pathlib import Path
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import argparse,csv,gzip,hashlib,importlib.util,json,math,sys,time
import numpy as np
HERE=Path(__file__).resolve().parent; AMEND=HERE.parent; STUDY=AMEND.parents[1]
sys.path.insert(0,str(AMEND));import numerics as n
PACKAGE=STUDY/'staging/p0-e2e-20260914-v1/package/release-v6'
sys.path.insert(0,str(PACKAGE/'src'));import empirical_core_v2 as core
sp=importlib.util.spec_from_file_location('portable_input_loader',PACKAGE/'replay.py')
replay=importlib.util.module_from_spec(sp);sp.loader.exec_module(replay)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,o):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(core.clean(o),f,ensure_ascii=False,indent=2,allow_nan=False)
def csvout(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(core.clean(rows))
def scalar_sigmoid(x):
    if x>=0:return 1/(1+math.exp(-x))
    e=math.exp(x);return e/(1+e)

def prepare():
    out=HERE/'inputs';out.mkdir(exist_ok=False)
    expected=read(STUDY/'manuscript/review-assessment-20260915-v1/availability-audit.json')
    token={};pins={};count=0;failed=0
    with gzip.open(out/'candidate-logprobs.jsonl.gz','wt',encoding='utf-8') as dest:
        for ref in expected['source_files']:
            p=STUDY/ref['file'];h=hashlib.sha256()
            with p.open('rb',buffering=4*1024*1024) as f:
                for line in f:
                    h.update(line);r=json.loads(line);rid=r['request_id'];assert rid not in token
                    item={k:r[k] for k in ('request_id','sample_id','seed','method_id','cameras','input_hash','available','status','score','logodds')}
                    if r['available']:
                        raw=r['raw_output'];lp=dict(zip(raw['top_token_ids'],raw['top_logprobs']))
                        assert 330 in lp and 389 in lp and raw['candidate_token_ids']==[49,50]
                        text=dict(zip(raw['top_token_ids'],raw['top_token_text']));assert text[330]==' A' and text[389]==' B'
                        odds=lp[330]-lp[389]
                        item.update(space_A_logprob=lp[330],space_B_logprob=lp[389],space_logodds=odds,space_score=scalar_sigmoid(odds))
                        assert r['logodds']==raw['candidate_logprobs'][0]-raw['candidate_logprobs'][1]
                        assert r['score']==scalar_sigmoid(r['logodds'])
                    else:item.update(space_logodds=None,space_score=None);failed+=1
                    token[rid]=item;dest.write(json.dumps(item,ensure_ascii=False,allow_nan=False)+'\n');count+=1
            assert h.hexdigest()==ref['sha256'];pins[str(p)]=h.hexdigest()
            print('EXTRACT',p.parent.name,flush=True)
    assert count==89052 and failed==1
    spec=read(PACKAGE/'data/case-manifest.json')
    collections={key:replay.load_collection(spec['collections'][key]) for key in ('original','external')}
    cases=[c for c in spec['cases'] if c['model']=='smolvlm_instruct' and '/main/' in c['key']]
    assert len(cases)==4
    converted={};checks=0
    for name,rows in collections.items():
        new=[]
        for r in rows:
            x=token[r['request_id']]
            for k in ('sample_id','seed','method_id','cameras','input_hash','available','status','score','logodds'):
                assert r[k]==x[k],(k,r['request_id']);checks+=1
            new.append(dict(r,space_logodds=x['space_logodds'],space_score=x['space_score']))
        converted[name]=new
        for k in ('metadata','scores'):p=PACKAGE/spec['collections'][name][k];pins[str(p)]=sha(p)
    assert sum(map(len,converted.values()))==count
    with gzip.open(out/'collections.json.gz','wt',encoding='utf-8') as f:json.dump(converted,f,ensure_ascii=False,allow_nan=False)
    dump(out/'cases.json',cases)
    for p in (HERE/'PROTOCOL.md',HERE/'run_sensitivity.py',AMEND/'numerics.py',PACKAGE/'src/empirical_core_v2.py',PACKAGE/'data/case-manifest.json'):
        pins[str(p)]=sha(p)
    dump(out/'preparation.json',{'status':'PASS','records':count,'failed_original':failed,'original_field_equalities':checks,'pins':pins,'source_visibility':'Previously observed original outcomes; new policy outcomes not calculated before protocol.'})

def asdata(c):return n.Data(c.y,c.group_index,len(c.groups),c.pools['joint'].scores,c.pools['late'].scores,c.pools['joint'].available,c.pools['late'].available)
def cohort(collection,c,role,space):
    ids=set(c[role+'_samples']);rows=[r for r in collection[c[role+'_collection']] if r['sample_id'] in ids]
    if space:rows=[dict(r,score=r['space_score'],logodds=r['space_logodds']) for r in rows]
    cc=core.build_cohorts(rows)
    out=[cc[(c['model'],c[role+'_dataset'],c[role+'_split'],s)] for s in c['seeds']]
    assert all(list(x.samples)==c[role+'_samples'] and list(x.groups)==c[role+'_groups'] for x in out)
    return out

def run(out):
    out.mkdir(exist_ok=False);start=time.perf_counter();prep=read(HERE/'inputs/preparation.json')
    for p in (HERE/'PROTOCOL.md',HERE/'run_sensitivity.py',AMEND/'numerics.py',PACKAGE/'src/empirical_core_v2.py'):assert sha(p)==prep['pins'][str(p)]
    with gzip.open(HERE/'inputs/collections.json.gz','rt',encoding='utf-8') as f:data=json.load(f)
    cases=read(HERE/'inputs/cases.json');ops=[];cons=[];fitsrows=[];disagreements=[];checks=[]
    for c in cases:
        label=c['case_id'];dest=out/label;dest.mkdir();B=2000;S=len(c['seeds'])
        ss,es=np.random.SeedSequence(c['rng_namespace']).spawn(2)
        gd=len(c['source_groups']);ge=len(c['target_groups'])
        md=np.random.default_rng(ss).multinomial(gd,np.ones(gd)/gd,size=B)
        me=np.random.default_rng(es).multinomial(ge,np.ones(ge)/ge,size=B)
        point=np.zeros((2,S,4,2));cond=np.zeros((2,S,B,4,2));refit=np.zeros_like(cond);dec=[]
        for vi,space in enumerate((False,True)):
            ds=cohort(data,c,'source',space);ts=cohort(data,c,'target',space);variant='space' if space else 'bare';vdec=[]
            for si,(dc,tc) in enumerate(zip(ds,ts)):
                d,t=asdata(dc),asdata(tc);sel=[dc.pairs.index(p) for p in tc.pairs];plan=n.Plan(d,sel)
                f=plan.fit(np.ones(gd,dtype=int))[0]
                point[vi,si]=n.rates(t,f,np.ones(ge,dtype=int))[0]
                cond[vi,si]=n.rates(t,f,me)
                vdec.append(n.predictions(t,f)[0])
                slow=core.fit(dc);names,accepted=core.prediction_matrix(tc,slow,list(n.METHODS))
                exp=core.matrix_rates(tc,accepted,np.ones(ge,dtype=int))[0]
                np.testing.assert_allclose(point[vi,si],exp,rtol=0,atol=1e-12,equal_nan=True)
                P=len(sel);K=P+1
                for j,(base,av,score) in enumerate((('joint',d.ja,d.joint),('late',d.la,d.late))):
                    for k,cols in enumerate((list(range(score.shape[1])),*[[z] for z in sel])):
                        tt=f[j*K+k];x=score[:,cols];aa=av[:,cols];pos=d.y==1
                        slowf=core.threshold(x,d.y,np.ones(len(d.y)),aa)['threshold']
                        assert tt==slowf or (np.isnan(tt) and np.isnan(slowf))
                        fitsrows.append(dict(case=label,scorer=variant,seed=dc.seed,method=base,scope='pooled' if k==0 else tc.pairs[k-1],threshold=tt,n_positive=int(pos.sum()),positive_atom_mass=float(np.mean((aa&(x==tt))[pos])),positive_strict_below_mass=float(np.mean((aa&(x<tt))[pos])),achieved_recall=float(np.mean((aa&(x>=tt))[pos]))))
                for b in range(0,B,64):
                    ff=plan.fit(md[b:b+64]);refit[vi,si,b:b+64]=n.rates(t,ff,me[b:b+64])
                    if b==0:
                        for z in range(min(3,len(ff))):
                            w=dc.sample_weights(md[z]);slow=[]
                            for score,av in ((d.joint,d.ja),(d.late,d.la)):
                                for cols in (list(range(score.shape[1])),*[[i] for i in sel]):slow.append(core.threshold(score[:,cols],d.y,w,av[:,cols])['threshold'])
                            np.testing.assert_array_equal(ff[z],slow)
                checks.append({'case':label,'scorer':variant,'seed':dc.seed,'point_and_weighted_knot_checks':'PASS'})
            dec.append(vdec)
        original=PACKAGE/c['reference'];meta=read(original/'metadata.json')
        with np.load(original/'bootstrap-arrays.npz') as old:
            assert np.array_equal(md,old['development_group_multiplicity']) and np.array_equal(me,old['evaluation_group_multiplicity'])
            for name,new in (('point_by_seed',point[0]),('conditional_by_seed',cond[0]),('refit_by_seed',refit[0])):
                for j,method in enumerate(n.METHODS):
                    oi=meta['method_axis'].index(method);target=old[name][...,0,oi,:]
                    np.testing.assert_allclose(new[...,j,:],target,rtol=0,atol=1e-12,equal_nan=True)
                    delta=np.nanmax(np.abs(new[...,j,:]-target));checks.append({'case':label,'check':name+'/'+method,'maximum_absolute_difference':float(delta),'pass':True})
        pm=point.mean(axis=1);cm=cond.mean(axis=1);rm=refit.mean(axis=1)
        for vi,variant in enumerate(('bare','space')):
            for j,method in enumerate(n.METHODS):
                for k,metric in enumerate(n.METRICS):
                    cv=n.interval(cm[vi,:,j,k]);rv=n.interval(rm[vi,:,j,k])
                    ops.append(dict(case=label,scorer=variant,method=method,metric=metric,estimate=pm[vi,j,k],conditional_lower=cv[0],conditional_upper=cv[1],refit_lower=rv[0],refit_upper=rv[1]))
        pi=n.interaction(pm);ci=n.interaction(cm);ri=n.interaction(rm)
        for variant,pp,cc,rr in [('bare',pi[0],ci[0],ri[0]),('space',pi[1],ci[1],ri[1]),('space_minus_bare',pi[1]-pi[0],ci[1]-ci[0],ri[1]-ri[0])]:
            for k,metric in enumerate(n.METRICS):
                cb=n.interval(cc[:,k]);rb=n.interval(rr[:,k]);bb=n.interval(rr[:,k],pp[k],True)
                cons.append(dict(case=label,scorer=variant,metric=metric,estimate=pp[k],conditional_lower=cb[0],conditional_upper=cb[1],refit_lower=rb[0],refit_upper=rb[1],basic_lower=bb[0],basic_upper=bb[1],conditional_valid=int(np.isfinite(cc[:,k]).sum()),refit_valid=int(np.isfinite(rr[:,k]).sum())))
        for si,tc in enumerate(cohort(data,c,'target',False)):
            diff=dec[0][si]!=dec[1][si]
            for j,method in enumerate(n.METHODS):
                for lab,mask in [('all',np.ones(len(tc.y),bool)),('failure',tc.y==0),('success',tc.y==1)]:
                    aa=diff[mask,j];disagreements.append(dict(case=label,seed=tc.seed,method=method,label=lab,trials=int(mask.sum()),pairs=aa.shape[1],differing_decisions=int(aa.sum()),sample_pair_disagreement=float(aa.mean()),trials_with_any_difference=int(aa.any(axis=1).sum())))
        np.savez_compressed(dest/'paired-bootstrap.npz',point_by_scorer_seed=point,conditional_by_scorer_seed=cond,refit_by_scorer_seed=refit,development_group_multiplicity=md,evaluation_group_multiplicity=me)
        print('COMPLETE',label,round(time.perf_counter()-start,2),flush=True)
    for name,rows in [('operating.csv',ops),('interactions.csv',cons),('thresholds.csv',fitsrows),('decision-disagreement.csv',disagreements)]:csvout(out/name,rows)
    dump(out/'checks.json',checks)
    dump(out/'completion.json',{'status':'PASS','cases':4,'bootstrap_B':2000,'operating_rows':len(ops),'interaction_rows':len(cons),'original_comparisons':len(checks),'new_model_calls':0,'elapsed_seconds':time.perf_counter()-start,'storage':'E: SATA HDD','python':sys.executable,'post_results_sensitivity':True,'original_Holm4_unchanged':True})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--output',type=Path);a=p.parse_args()
    prepare() if a.action=='prepare' else run(a.output or HERE/'results-v1')
