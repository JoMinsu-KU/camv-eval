"""Fixed sensitivity laws and two-sample cluster BCa; no file I/O."""
import math
import numpy as np
from scipy.special import ndtr, ndtri
import numerics as n

ROOT = (20260915, 91573)
SD = math.sqrt(.75)
A = np.array([[.5,.5,0],[.5,0,.5],[0,.5,.5]])
CHOL = np.linalg.cholesky(.5*np.eye(3)+.5*np.ones((3,3)))
METHODS = ('conditional_percentile','refit_percentile','refit_basic','conditional_sandwich_t','refit_BCa')

def conditions():
    rows=[]
    for auc in (.5,.65):
        for step in (0.,.125,.5):
            rows.append(dict(id=f'H{round(100*auc):03d}_{"C" if step==0 else "Q"+str(round(1000*step))}',
                             separation=float(SD*math.sqrt(2)*ndtri(auc)),step=step,
                             offset=[-.75,0.,.75],exact_zero=False,continuous_pair_auc=auc))
    for tag,off in [('N',[0.,0.,0.]),('H',[-.75,0.,.75])]:
        rows.append(dict(id=f'S_{tag}_C',separation=1.5,step=0.,offset=off,exact_zero=tag=='N',
                         continuous_pair_auc=float(ndtr(1.5/(SD*math.sqrt(2))))))
    return rows

def rng(domain,index):
    return np.random.default_rng(np.random.SeedSequence([*ROOT,domain,index]))

def generator(c,groups,domain,index,lam=.5):
    r=rng(domain,index)
    g=np.repeat(np.arange(groups),3)
    p=r.beta(2,3,size=groups)
    y=(r.random(len(g))<p[g]).astype(np.int8)
    h1=r.standard_normal((groups,3))@CHOL.T
    e1=r.standard_normal((len(g),3))@CHOL.T
    h2=r.standard_normal((groups,3))@CHOL.T
    e2=r.standard_normal((len(g),3))@CHOL.T
    lc=c['separation']*y[:,None]+math.sqrt(.35)*h1[g]+math.sqrt(.65)*e1
    jc=c['separation']*y[:,None]+math.sqrt(.35)*(lam*h1+math.sqrt(1-lam**2)*h2)[g]+math.sqrt(.65)*(lam*e1+math.sqrt(1-lam**2)*e2)
    late=lc@A.T
    joint=jc@A.T+np.asarray(c['offset'])
    if c['step']:
        joint=c['step']*np.floor(joint/c['step'])
        late=c['step']*np.floor(late/c['step'])
    return n.Data(y,g,groups,joint,late,np.ones_like(joint,bool),np.ones_like(late,bool))

def oracle(c,fits):
    ts=n.thresholds(fits)
    if c['step']:
        ts=c['step']*np.ceil(ts/c['step'])
    out=np.full((len(ts),4,2),np.nan)
    for y in (0,1):
        jm=c['separation']*y+np.asarray(c['offset'])
        lm=np.full(3,c['separation']*y)
        means=np.stack((jm,jm,lm,lm))
        out[:,:,y]=ndtr((means[None]-ts)/SD).mean(axis=-1)
    return out

def population_auc(c):
    result=[]
    for offsets in (np.array(c['offset']),np.zeros(3)):
        if not c['step']:
            pair=np.full(3,ndtr(c['separation']/(SD*math.sqrt(2))))
            pooled=ndtr((c['separation']+offsets[:,None]-offsets[None,:])/(SD*math.sqrt(2))).mean()
        else:
            q=c['step']; low=int(np.floor((offsets.min()-12*SD)/q)); high=int(np.ceil((offsets.max()+c['separation']+12*SD)/q))
            grid=np.arange(low,high+1)*q
            mass=[]
            for y in (0,1):
                z=(grid[:,None]-offsets[None,:]-c['separation']*y)/SD
                mass.append(ndtr(z+q/SD)-ndtr(z))
            neg,pos=mass
            pair=np.sum(pos*(np.cumsum(neg,axis=0)-.5*neg),axis=0)
            nm=neg.mean(axis=1);pm=pos.mean(axis=1)
            pooled=np.sum(pm*(np.cumsum(nm)-.5*nm))
        result.append(np.r_[pair,pooled])
    return np.array(result)

def empirical_features(d):
    auc=[];dup=[];collision=[];members=[]
    for score in (d.joint,d.late):
        dup.append(np.median([1-len(np.unique(score[d.y==y,p]))/np.sum(d.y==y)
                              for y in (0,1) for p in range(3)]) if 0<d.y.sum()<len(d.y) else np.nan)
        probs=[];tied=[]
        for y in (0,1):
            for p in range(3):
                _,counts=np.unique(score[d.y==y,p],return_counts=True)
                total=counts.sum()
                if total>1:probs.append(np.sum(counts*(counts-1))/(total*(total-1)))
                if total:tied.append(counts[counts>1].sum()/total)
        collision.append(np.median(probs) if probs else np.nan)
        members.append(np.median(tied) if tied else np.nan)
        # Descriptive within-pair AUROC, ties counted as one half.
        cells=[]
        for p in range(3):
            neg=np.sort(score[d.y==0,p]);pos=score[d.y==1,p]
            if len(neg) and len(pos):
                cells.append(np.mean((np.searchsorted(neg,pos,'left')+np.searchsorted(neg,pos,'right'))/(2*len(neg))))
        auc.append(np.mean(cells) if cells else np.nan)
    class_groups=np.array([np.sum(np.bincount(d.g,weights=d.y==y,minlength=d.groups)>0) for y in (0,1)])
    return np.r_[auc,dup,class_groups,collision,members]

def jackknife(plan,e,fit):
    nd=plan.d.groups;ne=e.groups
    wd=np.ones((nd,nd),int)-np.eye(nd,dtype=int)
    fd=plan.fit(wd)
    jd=n.interaction(n.rates(e,fd,np.ones((nd,ne),int)))
    we=np.ones((ne,ne),int)-np.eye(ne,dtype=int)
    je=n.interaction(n.rates(e,fit,we))
    return jd,je

def bca(point,draws,jd,je):
    """SciPy-style independent-sample BCa with whole-group jackknife.

    Status: 0=available, 1=insufficient finite bootstrap/point,
    2=invalid jackknife, 3=zero jackknife variance, 4=infinite z0,
    5=nonfinite or nonmonotone adjusted tails.
    No clipping, replacement, or interval fallback.
    """
    bounds=np.full((2,2),np.nan);diag=np.full((2,7),np.nan)
    for y in (0,1):
        v=draws[:,y];v=v[np.isfinite(v)]
        diag[y,0]=1
        if len(v)<math.ceil(.95*len(draws)) or not np.isfinite(point[y]):continue
        if not np.isfinite(jd[:,y]).all() or not np.isfinite(je[:,y]).all():
            diag[y,0]=2;continue
        u=np.concatenate([((len(j)-1)/len(j))*(j[:,y].mean()-j[:,y]) for j in (jd,je)])
        den=np.sum(u*u)
        if den==0:
            diag[y,0]=3;continue
        acceleration=np.sum(u**3)/(6*den**1.5)
        rank=(np.sum(v<point[y])+np.sum(v<=point[y]))/(2*len(v))
        z0=ndtri(rank)
        diag[y,1:3]=[z0,acceleration]
        if not np.isfinite(z0):
            diag[y,0]=4;continue
        z=ndtri([.025,.975])
        denom=1-acceleration*(z0+z)
        adjusted=ndtr(z0+(z0+z)/denom)
        diag[y,3:5]=adjusted
        if not np.isfinite(adjusted).all() or np.any(denom<=0) or adjusted[0]>adjusted[1]:
            diag[y,0]=5;continue
        bounds[y]=np.quantile(v,adjusted,method='linear')
        diag[y,0]=0
        diag[y,5]=float(np.any((adjusted<=1/(len(v)+1))|(adjusted>=len(v)/(len(v)+1))))
        diag[y,6]=np.mean(v==point[y])
    return bounds,diag

def outer(c,i,B=999):
    d=generator(c,40,10,i);e=generator(c,120,20,i)
    md=rng(30,i).multinomial(40,np.full(40,1/40),size=B)
    me=rng(40,i).multinomial(120,np.full(120,1/120),size=B)
    plan=n.Plan(d,both_labels=True);fit=plan.fit(np.ones(40,int))[0]
    policy=n.rates(e,fit,np.ones(120,int))[0];point=n.interaction(policy)
    cond=n.interaction(n.rates(e,fit,me));refit=np.full((B,2),np.nan)
    for a in range(0,B,64):
        refit[a:a+64]=n.interaction(n.rates(e,plan.fit(md[a:a+64]),me[a:a+64]))
    ci=np.full((5,2,2),np.nan)
    for y in (0,1):
        ci[0,y]=n.interval(cond[:,y]);ci[1,y]=n.interval(refit[:,y]);ci[2,y]=n.interval(refit[:,y],point[y],True)
    ci[3],se=n.sandwich(e,fit,point)
    jd,je=jackknife(plan,e,fit)
    ci[4],bcdiag=bca(point,refit,jd,je)
    pv=np.array([[n.centered_p(point[y],v[:,y]) for y in (0,1)] for v in (cond,refit)])
    return dict(point=point,point_policy=policy,point_thresholds=fit,
                fitted_truth=n.interaction(oracle(c,fit)[0]),intervals=ci,pvalues=pv,
                bca_diagnostics=bcdiag,dev_features=empirical_features(d),eval_features=empirical_features(e),
                refit_draws=refit,conditional_draws=cond,jackknife_dev=jd,jackknife_eval=je,
                finite_draw_counts=np.array([np.isfinite(cond).sum(axis=0),np.isfinite(refit).sum(axis=0)]))

def reference(c,i):
    d=generator(c,40,100,i)
    fit=n.Plan(d,both_labels=True).fit(np.ones(40,int))[0]
    return n.interaction(oracle(c,fit)[0])
