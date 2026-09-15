"""Eight fixed laws and exact population tails; pure numerical operations."""
from pathlib import Path
import sys,math
import numpy as np
from scipy.special import ndtr
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numerics as n
ROOT=(20260915,91551)
A=np.array([[.5,.5,0],[.5,0,.5],[0,.5,.5]])
CHOL=np.linalg.cholesky(.5*np.eye(3)+.5*np.ones((3,3)))
SD=math.sqrt(.75)
def conditions():
    return [dict(id=f'{kind}_{"Q" if q else "C"}_{"UQ" if u else "EQ"}',kind=kind,quantized=q,unequal=u,G_dev=40,G_eval=120,offset=[0.,0.,0.] if kind=='N' else [-.75,0.,.75])
            for kind in ('N','A') for q in (False,True) for u in (False,True)]
def rng(domain,u,index,extra=0):return np.random.default_rng(np.random.SeedSequence([*ROOT,domain,int(u),index,extra]))
def generator(c,groups,domain,index,lam=.5):
    rs=rng(domain,c['unequal'],index,77)
    sizes=rs.choice([1,3,9],size=groups,p=[.5,1/3,1/6]) if c['unequal'] else np.full(groups,3)
    g=np.repeat(np.arange(groups),sizes);r=rng(domain,c['unequal'],index)
    p=r.beta(2,3,size=groups);y=(r.random(len(g))<p[g]).astype(np.int8)
    h1=r.standard_normal((groups,3))@CHOL.T;e1=r.standard_normal((len(g),3))@CHOL.T
    h2=r.standard_normal((groups,3))@CHOL.T;e2=r.standard_normal((len(g),3))@CHOL.T
    lc=1.5*y[:,None]+math.sqrt(.35)*h1[g]+math.sqrt(.65)*e1
    if lam==1.:jc=lc.copy()
    else:jc=1.5*y[:,None]+math.sqrt(.35)*(lam*h1+math.sqrt(1-lam**2)*h2)[g]+math.sqrt(.65)*(lam*e1+math.sqrt(1-lam**2)*e2)
    late=lc@A.T;joint=jc@A.T+np.asarray(c['offset'])
    if c['quantized']:joint=.5*np.floor(joint/.5);late=.5*np.floor(late/.5)
    return n.Data(y,g,groups,joint,late,np.ones_like(joint,bool),np.ones_like(late,bool))
def oracle(c,fits):
    ts=n.thresholds(fits)
    if c['quantized']:ts=.5*np.ceil(ts/.5)
    out=np.full((len(ts),4,2),np.nan)
    for y in (0,1):
        jm=1.5*y+np.asarray(c['offset']);lm=np.full(3,1.5*y)
        means=np.stack((jm,jm,lm,lm))
        out[:,:,y]=ndtr((means[None]-ts)/SD).mean(axis=-1)
    return out
def atoms(c,d,fits):
    emp=[];pop=[];rec=[];K=4
    for j,score in enumerate((d.joint,d.late)):
        mu=1.5+(np.asarray(c['offset']) if j==0 else np.zeros(3))
        for k,cols in enumerate(([0,1,2],[0],[1],[2])):
            t=fits[j*K+k];pos=score[d.y==1][:,cols]
            emp.append(float(np.mean(pos==t)) if len(pos) else np.nan)
            rec.append(float(np.mean(pos>=t)) if len(pos) else np.nan)
            pop.append(float(np.mean(ndtr((t+.5-mu[cols])/SD)-ndtr((t-mu[cols])/SD))) if c['quantized'] else 0.)
    return np.array(emp),np.array(pop),np.array(rec)
def outer(c,i,B=999):
    d=generator(c,40,10,i);e=generator(c,120,20,i)
    md=rng(30,c['unequal'],i).multinomial(40,np.full(40,1/40),size=B)
    me=rng(40,c['unequal'],i).multinomial(120,np.full(120,1/120),size=B)
    plan=n.Plan(d,both_labels=True);fit=plan.fit(np.ones(40,int))[0]
    point=n.rates(e,fit,np.ones(120,int))[0];p=n.interaction(point)
    cond=n.interaction(n.rates(e,fit,me));refit=np.full((B,2),np.nan)
    for a in range(0,B,64):
        f=plan.fit(md[a:a+64]);refit[a:a+64]=n.interaction(n.rates(e,f,me[a:a+64]))
    ci=np.full((4,2,2),np.nan);pv=np.full((2,2),np.nan)
    for y in (0,1):
        ci[0,y]=n.interval(cond[:,y]);ci[1,y]=n.interval(refit[:,y]);ci[2,y]=n.interval(refit[:,y],p[y],True)
        pv[0,y]=n.centered_p(p[y],cond[:,y]);pv[1,y]=n.centered_p(p[y],refit[:,y])
    ci[3],se=n.sandwich(e,fit,p)
    emp,pop,rec=atoms(c,d,fit)
    szd=np.bincount(d.g,minlength=40);sze=np.bincount(e.g,minlength=120)
    return dict(point_policy=point,point=p,fitted_truth=n.interaction(oracle(c,fit)[0]),point_thresholds=fit,
                conditional_draws=cond,refit_draws=refit,intervals=ci,pvalues=pv,sandwich_se=se,
                positive_empirical_atom=emp,positive_population_atom=pop,development_recall=rec,
                population_policy=oracle(c,fit)[0],structure=np.array([len(d.y),len(e.y),d.y.sum(),e.y.sum(),szd.min(),szd.max(),szd.std(),sze.min(),sze.max(),sze.std()],float))
def reference(c,i):
    d=generator(c,40,100,i);f=n.Plan(d,both_labels=True).fit(np.ones(40,int))[0]
    return n.interaction(oracle(c,f)[0])
