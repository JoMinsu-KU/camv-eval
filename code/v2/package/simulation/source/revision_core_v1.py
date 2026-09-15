"""Reviewer-prespecified dependence sensitivity; imports do not dispatch work."""
from __future__ import annotations
import math
import numpy as np
from scipy.special import ndtr, ndtri
from scipy.optimize import brentq
import multipair_core_v1 as old
from frozen_primitives_v1 import interval, centered_p

ROOT_NAMESPACE=(20260914,91431)

def conditions():
    out=[]
    for kind,offset in [('N',[0.,0.,0.]),('A',[-.75,0.,.75])]:
        for gi,gd in enumerate((40,100)):
            for lam in (0.,.5,.9):
                out.append(dict(id=f'{kind}_G{gd}_L{int(100*lam):03d}',kind=kind,
                    G_dev=gd,G_eval=120,development_size_index=gi,lambda_=lam,rho=.35,
                    joint_pair_offsets=offset,common_target_shift=[0.,0.],
                    joint_success_target_shift=0.,exact_procedure_interaction_null=kind=='N'))
    return out

def generator(scenario,groups,namespace,target=False):
    lam=float(scenario['lambda_'])
    # Exact original operation order at lambda=0, including its RNG consumption.
    if lam==0.:return old.generator(scenario,groups,namespace,target)
    rng=np.random.default_rng(np.random.SeedSequence(namespace))
    prevalence=rng.beta(2.,3.,size=groups)
    y=(rng.random((groups,3))<prevalence[:,None]).astype(np.int8)
    h1=rng.standard_normal((groups,3))@old.CHOLESKY.T
    e1=rng.standard_normal((groups,3,3))@old.CHOLESKY.T
    h2=rng.standard_normal((groups,3))@old.CHOLESKY.T
    e2=rng.standard_normal((groups,3,3))@old.CHOLESKY.T
    rho=float(scenario['rho'])
    cameras=1.5*y[...,None]+math.sqrt(rho)*h1[:,None,:]+math.sqrt(1-rho)*e1
    if lam==1.:
        joint_camera=cameras.copy()
    else:
        hj=lam*h1+math.sqrt(1-lam*lam)*h2
        ej=lam*e1+math.sqrt(1-lam*lam)*e2
        joint_camera=1.5*y[...,None]+math.sqrt(rho)*hj[:,None,:]+math.sqrt(1-rho)*ej
    if target:
        shift=np.asarray(scenario['common_target_shift'])[y]*old.PAIR_SD[0]
        cameras=cameras+shift[...,None];joint_camera=joint_camera+shift[...,None]
    joint=joint_camera@old.A.T+np.asarray(scenario['joint_pair_offsets'])
    if target:joint=joint+y[...,None]*float(scenario['joint_success_target_shift'])*old.PAIR_SD
    return old.Data(y,cameras,joint)

def oracle_fits(scenario):
    means=np.stack((1.5+np.asarray(scenario['joint_pair_offsets']),np.repeat(1.5,3)))
    fits=[]
    for mu in means:
        function=lambda t:float(ndtr((mu-t)/old.PAIR_SD).mean()-.9)
        pooled=brentq(function,float(mu.min()-12*old.PAIR_SD.max()),
                      float(mu.max()+12*old.PAIR_SD.max()),xtol=5e-15,rtol=1e-14)
        fits.extend([pooled,*list(mu+old.PAIR_SD*ndtri(.1))])
    return np.asarray(fits,dtype=np.float64)

def analyze_oracle(scenario,evaluation,me):
    fits=oracle_fits(scenario)
    point=old.weighted_rates(evaluation,fits,np.ones(evaluation.groups,dtype=np.int64))[0]
    draws=old.weighted_rates(evaluation,fits,me)
    pointc,drawc=old.contrasts(point),old.contrasts(draws)
    ci=np.full((2,5,2,2),np.nan)
    pv=np.full((5,2),np.nan)
    for c in range(5):
        for m in range(2):
            ci[0,c,m]=interval(drawc[:,c,m])
            pv[c,m]=centered_p(pointc[c,m],drawc[:,c,m],len(me))
    ci[1],se=old.sandwich(evaluation,fits,pointc)
    truthraw=old.contrasts(old.oracle(scenario,fits)[0])
    truth=truthraw.copy()
    # Exact source-population oracle recall equality; no target shift in this grid.
    truth[:,1]=0.
    if scenario['kind']=='N':truth[:]=0.
    return dict(oracle_point_policy=point,oracle_point_contrasts=pointc,
                oracle_conditional_policy_draws=draws,oracle_thresholds=fits,
                oracle_truth_raw=truthraw,oracle_truth=truth,oracle_intervals=ci,
                oracle_centered_p=pv,oracle_sandwich_se=se)

def outer_record(scenario,outer_index,B=999):
    gi=scenario['development_size_index'];gd=scenario['G_dev'];ge=scenario['G_eval']
    ns=lambda domain:[*ROOT_NAMESPACE,domain,gi,outer_index]
    dev=generator(scenario,gd,ns(10))
    ev=generator(scenario,ge,ns(20),True)
    md=np.random.default_rng(np.random.SeedSequence(ns(30))).multinomial(gd,np.ones(gd)/gd,size=B)
    me=np.random.default_rng(np.random.SeedSequence(ns(40))).multinomial(ge,np.ones(ge)/ge,size=B)
    record=old.analyze_data(scenario,dev,ev,md,me)
    record.update(analyze_oracle(scenario,ev,me))
    record['calibration_valid']=np.array(dev.valid_calibration,dtype=np.bool_)
    record['evaluation_class_counts']=np.array([(ev.y==0).sum(),(ev.y==1).sum()],dtype=np.int64)
    return record
