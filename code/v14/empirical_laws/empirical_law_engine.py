"""Finite group-population experiment; all stochastic domains are separated.

Compressed counts refer to independent sampled group occurrences. Repeated
occurrences share data but remain distinct sampling units in sandwich/jackknife.
"""
from pathlib import Path
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
import argparse,csv,gzip,hashlib,itertools,json,math,platform,sys,time
from dataclasses import dataclass
import numpy as np
from scipy.special import expit
from scipy.stats import t as student_t

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'frozen-core'))
import numerics as n
import review_core as rc

ROOT=(20261104,48245,1001)
METHODS=rc.METHODS
METRICS=('FSR','recall')
SOURCE=Path('E:/SoftwareX/camv-eval-study-v1/amendments/score-ties-revision-20260915-v1/scorer/inputs/collections.json.gz')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    temp.replace(path)

def rng(cohort,domain,index=0):
    return np.random.default_rng(np.random.SeedSequence([*ROOT,cohort,domain,index]))

@dataclass
class Population:
    data:n.Data

    def __post_init__(self):
        d=self.data;self.K=d.groups;self.P=d.joint.shape[1]
        self.positive=np.bincount(d.g,weights=d.y,minlength=self.K)
        self.negative=np.bincount(d.g,weights=1-d.y,minlength=self.K)
        self.class_counts=np.stack([self.negative,self.positive],axis=-1)
        self.knots=[];self.positive_tails=[];self.responses=[]
        self.coefficients=np.r_[-1,np.ones(self.P,dtype=int),1,-np.ones(self.P,dtype=int)]
        for score,available in ((d.joint,d.ja),(d.late,d.la)):
            for cols in (list(range(self.P)),*[[p] for p in range(self.P)]):
                ss=score[:,cols];aa=available[:,cols]
                use=aa&(d.y[:,None]==1)&np.isfinite(ss)
                values=np.unique(ss[use])[::-1]
                self.knots.append(values)
                counts=np.zeros((len(values),self.K,2),dtype=float)
                # Cumulative group/class response at each descending positive knot.
                for group in range(self.K):
                    for label in (0,1):
                        use_g=aa&(d.g[:,None]==group)&(d.y[:,None]==label)&np.isfinite(ss)
                        sorted_scores=np.sort(ss[use_g])
                        counts[:,group,label]=len(sorted_scores)-np.searchsorted(sorted_scores,values,side='left')
                self.responses.append(counts)
                self.positive_tails.append(counts[:,:,1])

    def fit_indices(self,multiplicity):
        w=np.atleast_2d(np.asarray(multiplicity,dtype=np.int64))
        if w.shape[1]!=self.K or np.any(w<0):raise ValueError('Invalid group counts')
        pos=w@self.positive;neg=w@self.negative
        valid=(pos>0)&(neg>0)
        out=np.full((len(w),len(self.knots)),-1,dtype=np.int32)
        for j,(knots,tail) in enumerate(zip(self.knots,self.positive_tails)):
            if not len(knots):continue
            pairs=self.P if j in (0,self.P+1) else 1
            target=(.9-1e-12)*pos*pairs
            ok=valid & (np.sum(w*tail[-1],axis=1)>=target)
            lo=np.zeros(len(w),dtype=int);hi=np.full(len(w),len(knots)-1,dtype=int)
            while np.any(lo<hi):
                mid=(lo+hi)//2
                attained=np.sum(w*tail[mid],axis=1)>=target
                hi=np.where(attained,mid,hi)
                lo=np.where(attained,lo,mid+1)
            out[ok,j]=lo[ok]
        return out

    def threshold_values(self,indices):
        idx=np.atleast_2d(indices)
        out=np.full(idx.shape,np.nan)
        for j,knots in enumerate(self.knots):
            use=idx[:,j]>=0
            out[use,j]=knots[idx[use,j]]
        return out

    def numerators(self,indices):
        idx=np.atleast_2d(indices)
        out=np.zeros((len(idx),self.K,2))
        for j,counts in enumerate(self.responses):
            out+=self.coefficients[j]*counts[np.maximum(idx[:,j],0)]
        out[~(idx>=0).all(axis=1)]=np.nan
        return out

    def features(self,indices):
        return self.numerators(indices)/self.P

    def evaluate(self,indices,eval_counts):
        feature=self.numerators(indices)
        counts=np.atleast_2d(eval_counts)
        den=self.P*(counts@self.class_counts)
        with np.errstate(divide='ignore',invalid='ignore'):
            if len(feature)==1:return counts@feature[0]/den
            return np.einsum('bky,bk->by',feature,counts)/den

    def truth(self,indices):
        with np.errstate(divide='ignore',invalid='ignore'):
            return self.numerators(indices).sum(axis=1)/(self.P*self.class_counts.sum(axis=0))

    def sandwich(self,indices,eval_counts,point):
        counts=np.asarray(eval_counts);G=counts.sum()
        feature=self.features(indices)[0]
        N=counts@self.class_counts
        with np.errstate(divide='ignore',invalid='ignore'):
            psi=(feature-self.class_counts*point)/(N/G)
            se=np.sqrt(np.sum(counts[:,None]*psi*psi,axis=0)/(G*(G-1)))
        return point[:,None]+np.array([-1,1])[None,:]*student_t.ppf(.975,G-1)*se[:,None],se

    def jackknife(self,dev_counts,eval_counts,indices):
        dc=np.asarray(dev_counts);ec=np.asarray(eval_counts)
        gd=np.flatnonzero(dc);ge=np.flatnonzero(ec)
        wd=np.repeat(dc[None],len(gd),axis=0);wd[np.arange(len(gd)),gd]-=1
        fd=self.fit_indices(wd)
        jd=self.evaluate(fd,np.repeat(ec[None],len(gd),axis=0))
        feature=self.numerators(indices)[0]
        num=ec@feature;den=self.P*(ec@self.class_counts)
        with np.errstate(divide='ignore',invalid='ignore'):
            je=(num[None]-feature[ge])/(den[None]-self.P*self.class_counts[ge])
        # A repeated source group is multiple independent sample occurrences.
        return np.repeat(jd,dc[gd],axis=0),np.repeat(je,ec[ge],axis=0)

def load_inputs():
    with gzip.open(SOURCE,'rt',encoding='utf-8') as f:collections=json.load(f)
    out={}
    for cohort,key,dataset,G,GE in [('RL','original','rlbenchfail',40,179),('RE','external','reassemble',111,37)]:
        rows=[r for r in collections[key] if r['seed']==29 and r['split']=='dev' and r['dataset']==dataset]
        samples=sorted({r['sample_id'] for r in rows})
        groups=sorted({r['group_id'] for r in rows});assert len(groups)==G
        gi={g:i for i,g in enumerate(groups)}
        byid={s:[] for s in samples}
        for row in rows:byid[row['sample_id']].append(row)
        cameras=sorted({r['cameras'][0] for r in rows if r['method_id']=='single'})
        pairs=list(itertools.combinations(cameras,2))
        y=np.array([byid[s][0]['label'] for s in samples],dtype=np.int8)
        g=np.array([gi[byid[s][0]['group_id']] for s in samples],dtype=np.int32)
        variants={}
        for variant in ('bare','space'):
            sf='score' if variant=='bare' else 'space_score'
            lf='logodds' if variant=='bare' else 'space_logodds'
            j=np.empty((len(samples),len(pairs)));l=np.empty_like(j)
            ja=np.empty(j.shape,dtype=bool);la=np.empty_like(ja)
            for i,sample in enumerate(samples):
                rr=byid[sample]
                assert all(r['label']==int(y[i]) and gi[r['group_id']]==int(g[i]) for r in rr)
                for p,pair in enumerate(pairs):
                    jr=[r for r in rr if r['method_id']=='joint' and r['cameras']==list(pair)]
                    assert len(jr)==1
                    singles=[[r for r in rr if r['method_id']=='single' and r['cameras']==[cam]] for cam in pair]
                    assert all(len(v)==1 for v in singles)
                    aa=bool(jr[0]['available']);bb=all(v[0]['available'] for v in singles)
                    ja[i,p]=aa;la[i,p]=bb
                    j[i,p]=jr[0][sf] if aa else np.nan
                    l[i,p]=expit(np.mean([v[0][lf] for v in singles])) if bb else np.nan
            assert ja.all() and la.all(),'Canonical seed29 availability must be explicit'
            variants[variant]=Population(n.Data(y,g,G,j,l,ja,la))
        assert len(y)==(106 if cohort=='RL' else 1716)
        out[cohort]={'variants':variants,'groups_dev':G,'groups_eval':GE,
                     'samples':samples,'group_ids':groups,'pairs':[list(p) for p in pairs]}
    return out

def sample_counts(K,G,cohort,domain,index):
    return rng(cohort,domain,index).multinomial(G,np.full(K,1/K))

def bootstrap_counts(outer_counts,B,cohort,domain,index):
    G=int(np.sum(outer_counts))
    return rng(cohort,domain,index).multinomial(G,outer_counts/G,size=B)

def outer(populations,cohort,index,B=999):
    spec=populations[cohort];cid=0 if cohort=='RL' else 1
    K=spec['groups_dev'];GD=K;GE=spec['groups_eval']
    dc=sample_counts(K,GD,cid,10,index);ec=sample_counts(K,GE,cid,20,index)
    db=bootstrap_counts(dc,B,cid,30,index);eb=bootstrap_counts(ec,B,cid,40,index)
    results={}
    for variant,pop in spec['variants'].items():
        fit=pop.fit_indices(dc)
        point=pop.evaluate(fit,ec)[0]
        cond=pop.evaluate(fit,eb)
        bfits=pop.fit_indices(db);refit=pop.evaluate(bfits,eb)
        intervals=np.full((5,2,2),np.nan)
        for y in (0,1):
            intervals[0,y]=n.interval(cond[:,y]);intervals[1,y]=n.interval(refit[:,y]);intervals[2,y]=n.interval(refit[:,y],point[y],True)
        intervals[3],se=pop.sandwich(fit,ec,point)
        jd,je=pop.jackknife(dc,ec,fit)
        intervals[4],bcdiag=rc.bca(point,refit,jd,je)
        # Invariance to exact repeated origin counts is checked independently.
        counts=np.stack([dc@pop.class_counts,ec@pop.class_counts])
        results[variant]=dict(point=point,fitted_truth=pop.truth(fit)[0],intervals=intervals,
              conditional_draws=cond,refit_draws=refit,bca_diagnostics=bcdiag,
              jackknife_dev=jd,jackknife_eval=je,
              threshold_indices=fit[0],threshold_values=pop.threshold_values(fit)[0],
              sandwich_se=se,counts=counts,dev_multiplicity=dc,eval_multiplicity=ec,
              finite_draw_counts=np.stack([np.isfinite(cond).sum(axis=0),np.isfinite(refit).sum(axis=0)]))
    return results

def reference(populations,cohort,N=65536):
    spec=populations[cohort];cid=0 if cohort=='RL' else 1
    K=spec['groups_dev'];r=rng(cid,100)
    counts=r.multinomial(K,np.full(K,1/K),size=N)
    values={}
    for variant,pop in spec['variants'].items():
        batches=[]
        for i in range(0,N,512):batches.append(pop.truth(pop.fit_indices(counts[i:i+512])))
        values[variant]=np.concatenate(batches)
    return counts,values

def expanded_data(d,counts):
    ix=[]
    for g in np.repeat(np.arange(d.groups),counts):
        ix.extend(np.flatnonzero(d.g==g))
    ix=np.asarray(ix)
    occurrence=np.repeat(np.arange(counts.sum()),np.repeat(np.bincount(d.g,minlength=d.groups),counts))
    return n.Data(d.y[ix],occurrence,int(counts.sum()),d.joint[ix],d.late[ix],d.ja[ix],d.la[ix])

def validate(populations):
    checks=[]
    for cohort,spec in populations.items():
        K=spec['groups_dev'];cid=0 if cohort=='RL' else 1
        dc=sample_counts(K,K,cid,901,0);ec=sample_counts(K,spec['groups_eval'],cid,902,0)
        # Explicitly expanded occurrence implementation is the independent slow fixture.
        for variant,pop in spec['variants'].items():
            de=expanded_data(pop.data,dc);ee=expanded_data(pop.data,ec)
            fit=pop.fit_indices(dc);threshold=pop.threshold_values(fit)
            slowplan=n.Plan(de,both_labels=True);slowfit=slowplan.fit(np.ones(de.groups,int))
            np.testing.assert_array_equal(threshold,slowfit)
            value=pop.evaluate(fit,ec)[0]
            slow=n.interaction(n.rates(ee,slowfit,np.ones(ee.groups,int)))[0]
            np.testing.assert_allclose(value,slow,rtol=0,atol=3e-15)
            ci,se=pop.sandwich(fit,ec,value)
            ci2,se2=n.sandwich(ee,slowfit[0],slow)
            np.testing.assert_allclose(ci,ci2,rtol=0,atol=3e-15)
            np.testing.assert_allclose(se,se2,rtol=0,atol=3e-15)
            jd,je=pop.jackknife(dc,ec,fit)
            sd,sej=rc.jackknife(slowplan,ee,slowfit[0])
            np.testing.assert_allclose(jd,sd,rtol=0,atol=3e-15)
            np.testing.assert_allclose(je,sej,rtol=0,atol=3e-15)
            # Weights can be arbitrary bootstrap counts, not only initial outer counts.
            w=rng(cid,903).multinomial(K,np.full(K,1/K),size=17)
            fi=pop.fit_indices(w);nf=n.Plan(pop.data,both_labels=True).fit(w)
            np.testing.assert_array_equal(pop.threshold_values(fi),nf)
            vv=pop.evaluate(fi,np.repeat(ec[None],len(w),axis=0))
            nv=n.interaction(n.rates(pop.data,nf,np.repeat(ec[None],len(w),axis=0)))
            np.testing.assert_allclose(vv,nv,rtol=0,atol=3e-15)
            # Exact count-ratio arithmetic preserves mathematical ties in BCa ranks.
            repeated=pop.evaluate(np.repeat(fit,3,axis=0),np.stack([ec,ec,2*ec]))
            np.testing.assert_array_equal(repeated,np.repeat(value[None],3,axis=0))
            checks.append(dict(cohort=cohort,variant=variant,samples=len(pop.data.y),groups=K,pairs=pop.P,
                exact_thresholds=True,max_point_difference=float(np.max(np.abs(value-slow))),
                sandwich_occurrences=True,jackknife_occurrences=True,weighted_bootstrap_fixture=True,
                exact_count_ratio_ties_preserved=True))
        base=spec['variants']['bare'].data
        identical=Population(n.Data(base.y,base.g,base.groups,base.joint,base.joint,base.ja,base.ja))
        fi=identical.fit_indices(np.stack([dc,np.ones(K,dtype=int)]))
        exact=identical.evaluate(fi,np.stack([ec,ec]))
        np.testing.assert_array_equal(exact,np.zeros((2,2)))
        checks.append(dict(cohort=cohort,identical_methods_zero_control=True,
                           exact_zero_interaction=True))
    return checks

def prepare():
    start=time.perf_counter();data=load_inputs()
    checks=validate(data)
    dump(HERE/'validation.json',dict(status='PASS',checks=checks,elapsed_seconds=time.perf_counter()-start))
    manifest={'source':str(SOURCE),'sha256':sha(SOURCE),'canonical_seed':29,
      'availability':'All selected canonical seed29 forward Joint and Single records are available; seed17 known failure is not deleted or reinterpreted.',
      'cohorts':{c:{'groups_dev':v['groups_dev'],'groups_eval':v['groups_eval'],
           'n_population':len(v['variants']['bare'].data.y),'pairs':v['pairs'],
           'class_counts':v['variants']['bare'].class_counts.sum(axis=0).tolist(),
           'sample_ids':v['samples'],'group_ids':v['group_ids']} for c,v in data.items()}}
    dump(HERE/'input-manifest.json',manifest)
    elapsed=[]
    for c in data:
        t=time.perf_counter()
        for i in range(10):
            rr=outer(data,c,i,999)
            for v,row in rr.items():
                dest=HERE/'pilot'/c/v;dest.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(dest/f'outer-{i:04}.npz',**row)
        elapsed.append({'cohort':c,'outer_count':10,'variants':2,'B':999,
                        'elapsed_seconds':time.perf_counter()-t})
        print('PILOT',c,elapsed[-1],flush=True)
    dump(HERE/'pilot-runtime.json',dict(status='PASS',records=elapsed,python=sys.executable,
         platform=platform.platform(),storage='E: SATA HDD',engine_sha256=sha(__file__),
         total_elapsed_seconds=time.perf_counter()-start))
    print(json.dumps({'validation':'PASS','pilot':elapsed},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare']);a=p.parse_args()
    if a.action=='prepare':prepare()
