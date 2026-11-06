"""Explicit clustered trial arrays; no file I/O or stochastic side effects."""
from dataclasses import dataclass
import math
import numpy as np
from scipy.stats import t as student_t

METHODS=('joint_pooled','joint_pair','late_pooled','late_pair')
METRICS=('false_success_rate','success_recall')

@dataclass
class Data:
    y: np.ndarray
    g: np.ndarray
    groups: int
    joint: np.ndarray
    late: np.ndarray
    ja: np.ndarray
    la: np.ndarray

class Plan:
    def __init__(self,d,selected=None,both_labels=False):
        self.d=d; self.both_labels=both_labels
        self.positive=np.bincount(d.g,weights=d.y,minlength=d.groups)
        self.negative=np.bincount(d.g,weights=1-d.y,minlength=d.groups)
        self.entries=[]
        selected=list(range(d.joint.shape[1])) if selected is None else list(selected)
        self.pairs=len(selected)
        for score,available in ((d.joint,d.ja),(d.late,d.la)):
            for cols in (list(range(score.shape[1])),*[[i] for i in selected]):
                ss=score[:,cols]; aa=available[:,cols]; p=len(cols)
                use=aa & np.isfinite(ss) & (d.y[:,None]==1)
                vv=ss[use]; gg=np.broadcast_to(d.g[:,None],ss.shape)[use]
                order=np.argsort(-vv,kind='stable');vv=vv[order];gg=gg[order]
                ends=np.r_[np.flatnonzero(vv[:-1]!=vv[1:]),len(vv)-1] if len(vv) else np.array([],int)
                self.entries.append((vv,gg,ends,p))

    def fit(self,multiplicity):
        w=np.atleast_2d(np.asarray(multiplicity,dtype=np.int64))
        if w.shape[1]!=self.d.groups or np.any(w<0):raise ValueError('Invalid multiplicity')
        pos=w@self.positive
        valid=pos>0
        if self.both_labels:valid &= w@self.negative>0
        out=np.full((len(w),len(self.entries)),np.nan)
        for i,(values,groups,ends,p) in enumerate(self.entries):
            if not len(values):continue
            cs=np.cumsum(w[:,groups]/p,axis=1)[:,ends]
            with np.errstate(divide='ignore',invalid='ignore'):attained=cs/pos[:,None]+1e-12>=.9
            ok=valid & attained.any(axis=1)
            which=np.argmax(attained,axis=1)
            out[ok,i]=values[ends[which[ok]]]
        return out

def thresholds(fits):
    f=np.atleast_2d(fits);p=f.shape[1]//2-1;k=p+1
    return np.stack((np.repeat(f[:,[0]],p,axis=1),f[:,1:k],
                     np.repeat(f[:,[k]],p,axis=1),f[:,k+1:]),axis=1)

def predictions(d,fits):
    ts=thresholds(fits)
    ss=np.stack((d.joint,d.joint,d.late,d.late),axis=1)
    aa=np.stack((d.ja,d.ja,d.la,d.la),axis=1)
    pred=aa[None] & np.isfinite(ts[:,None]) & (ss[None]>=ts[:,None])
    return pred

def rates(d,fits,multiplicity):
    w=np.atleast_2d(multiplicity)[:,d.g].astype(float)
    pred=predictions(d,fits).mean(axis=-1)
    valid=np.isfinite(thresholds(fits)).all(axis=-1)
    pred=np.where(valid[:,None,:],pred,np.nan)
    out=np.full((len(w),4,2),np.nan)
    for y in (0,1):
        select=d.y==y;ww=w[:,select];den=ww.sum(axis=1)
        with np.errstate(divide='ignore',invalid='ignore'):
            if len(pred)==1:out[:,:,y]=(ww@pred[0,select])/den[:,None]
            else:out[:,:,y]=(ww[:,:,None]*pred[:,select]).sum(axis=1)/den[:,None]
    return out

def interaction(r):
    return (r[...,1,:]-r[...,3,:])-(r[...,0,:]-r[...,2,:])

def interval(v,point=None,basic=False):
    v=np.asarray(v);x=v[np.isfinite(v)]
    if len(x)<math.ceil(.95*len(v)):return np.full(2,np.nan)
    q=np.quantile(x,[.025,.975],method='linear')
    return 2*point-q[::-1] if basic else q

def centered_p(point,draws):
    a=np.asarray(draws);v=a[np.isfinite(a)]
    if len(v)<math.ceil(.95*len(a)) or not np.isfinite(point):return np.nan
    return (1+np.sum(np.abs(v-point)>=abs(point)))/(len(v)+1)

def sandwich(d,fits,point):
    pred=predictions(d,fits)[0].mean(axis=-1)
    c=(pred[:,1]-pred[:,3])-(pred[:,0]-pred[:,2])
    result=np.full((2,2),np.nan);se=np.full(2,np.nan)
    if not np.isfinite(fits).all():return result,se
    critical=student_t.ppf(.975,d.groups-1)
    for y in (0,1):
        mask=d.y==y
        n=np.bincount(d.g,weights=mask,minlength=d.groups)
        x=np.bincount(d.g,weights=mask*c,minlength=d.groups)
        if n.sum()==0:continue
        psi=(x-n*point[y])/n.mean()
        se[y]=np.sqrt(np.sum(psi**2)/(d.groups*(d.groups-1)))
        result[y]=point[y]+np.array([-1.,1.])*critical*se[y]
    return result,se
