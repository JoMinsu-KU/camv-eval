"""Three prespecified review sensitivity laws; imports the preserved numeric core."""
import numpy as np
from scipy.special import ndtr, ndtri
import review_core as c
import numerics as n
from pathlib import Path
import json

ROOT=(20260915, 712031)
PROFILES=json.loads((Path(__file__).parent/'group-profiles.json').read_text())
def rng(domain,index):return np.random.default_rng(np.random.SeedSequence([*ROOT,domain,index]))
def conditions():
    base=dict(separation=float(c.SD*np.sqrt(2)*ndtri(.58)),offset=[-.75,0,.75],late_offset=[0,0,0],groups_d=111,groups_e=37,profile=True,exact_zero=False)
    return [dict(base,id='RF_H_C',step=0),dict(base,id='RF_H_Q125',step=.125),
            dict(id='NE_H_C',separation=float(c.SD*np.sqrt(2)*ndtri(.65)),offset=[-.75,0,.75],late_offset=[.75,0,-.75],groups_d=40,groups_e=120,profile=False,exact_zero=True,step=0)]
def generator(law,stage,domain,index):
    r=rng(domain,index);G=law['groups_d' if stage=='dev' else 'groups_e']
    if law['profile']:
        profiles=np.asarray(PROFILES[stage],int)
        sampled=profiles[r.integers(len(profiles),size=G)]
        g=np.repeat(np.arange(G),sampled.sum(axis=1))
        y=np.concatenate([np.r_[np.zeros(f,int),np.ones(s,int)] for f,s in sampled]).astype(np.int8)
    else:
        g=np.repeat(np.arange(G),3);p=r.beta(2,3,size=G)
        y=(r.random(len(g))<p[g]).astype(np.int8)
    h1=r.standard_normal((G,3))@c.CHOL.T;e1=r.standard_normal((len(g),3))@c.CHOL.T
    h2=r.standard_normal((G,3))@c.CHOL.T;e2=r.standard_normal((len(g),3))@c.CHOL.T
    lc=law['separation']*y[:,None]+np.sqrt(.35)*h1[g]+np.sqrt(.65)*e1
    jc=law['separation']*y[:,None]+np.sqrt(.35)*(.5*h1+np.sqrt(.75)*h2)[g]+np.sqrt(.65)*(.5*e1+np.sqrt(.75)*e2)
    late=lc@c.A.T+np.asarray(law['late_offset']);joint=jc@c.A.T+np.asarray(law['offset'])
    if law['step']:
        q=law['step'];late=q*np.floor(late/q);joint=q*np.floor(joint/q)
    return n.Data(y,g,G,joint,late,np.ones_like(joint,bool),np.ones_like(late,bool))
def oracle(law,fits):
    ts=n.thresholds(fits)
    if law['step']:ts=law['step']*np.ceil(ts/law['step'])
    out=np.full((len(ts),4,2),np.nan)
    for y in (0,1):
        jm=law['separation']*y+np.asarray(law['offset'])
        lm=law['separation']*y+np.asarray(law['late_offset'])
        out[:,:,y]=ndtr((np.stack((jm,jm,lm,lm))[None]-ts)/c.SD).mean(axis=-1)
    return out
def outer(law,index,B=999):
    d=generator(law,'dev',10,index);e=generator(law,'eval',20,index)
    gd,ge=d.groups,e.groups
    md=rng(30,index).multinomial(gd,np.full(gd,1/gd),size=B)
    me=rng(40,index).multinomial(ge,np.full(ge,1/ge),size=B)
    plan=n.Plan(d,both_labels=True);fit=plan.fit(np.ones(gd,int))[0]
    policy=n.rates(e,fit,np.ones(ge,int))[0];point=n.interaction(policy)
    cond=n.interaction(n.rates(e,fit,me));refit=np.full((B,2),np.nan)
    for a in range(0,B,32):refit[a:a+32]=n.interaction(n.rates(e,plan.fit(md[a:a+32]),me[a:a+32]))
    ci=np.full((5,2,2),np.nan)
    for y in (0,1):
        ci[0,y]=n.interval(cond[:,y]);ci[1,y]=n.interval(refit[:,y]);ci[2,y]=n.interval(refit[:,y],point[y],True)
    ci[3],se=n.sandwich(e,fit,point)
    jd,je=c.jackknife(plan,e,fit);ci[4],diag=c.bca(point,refit,jd,je)
    pv=np.array([[n.centered_p(point[y],draw[:,y]) for y in (0,1)] for draw in (cond,refit)])
    def counts(data):
        return np.array([len(data.y),data.groups,np.sum(data.y==0),np.sum(data.y==1),
                         np.sum(np.bincount(data.g,weights=data.y==0,minlength=data.groups)>0),
                         np.sum(np.bincount(data.g,weights=data.y==1,minlength=data.groups)>0)])
    return dict(point=point,fitted_truth=n.interaction(oracle(law,fit)[0]),intervals=ci,pvalues=pv,
                bca_diagnostics=diag,refit_draws=refit,conditional_draws=cond,
                counts=np.stack((counts(d),counts(e))))
def reference(law,index):
    d=generator(law,'dev',100,index)
    fit=n.Plan(d,both_labels=True).fit(np.ones(d.groups,int))[0]
    return n.interaction(oracle(law,fit)[0])
