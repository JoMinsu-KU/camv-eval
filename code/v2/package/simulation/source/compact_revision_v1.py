"""Extract sufficient saved arrays for deterministic table replay; no new draws."""
from pathlib import Path
import argparse,hashlib,json,math,os
import numpy as np

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,float) and not math.isfinite(v):return None
    return v
def contrast(v):
    jp,jr,lp,lr=(v[...,i,:] for i in range(4))
    return np.stack([jp-lp,jr-lr,jr-jp,lr-lp,(jr-lr)-(jp-lp)],axis=-2)
def moments(draws):
    vals=contrast(draws);good=np.isfinite(vals)
    count=good.sum(axis=1);total=np.where(good,vals,0).sum(axis=1)
    mean=np.divide(total,count,out=np.full_like(total,np.nan),where=count>0)
    sq=np.where(good,(vals-mean[:,None])**2,0).sum(axis=1)
    sd=np.sqrt(np.divide(sq,count-1,out=np.full_like(total,np.nan),where=count>1))
    q=np.nanquantile(vals,[.025,.5,.975],axis=1,method='linear').transpose(1,2,3,0)
    return mean,sd,count,q

def build(raw,output):
    raw=Path(raw).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('Refusing to replace compact directory')
    completion=json.loads((raw/'computation-completion.json').read_text())
    if not completion['all_fixed_work_complete']:raise ValueError('Raw grid incomplete')
    parent=raw.parent;contract=json.loads((parent/'contract-v1.json').read_text())
    output.mkdir(parents=True)
    keys=['point_policy','point_contrasts','conditional_truth_contrasts','conditional_truth_policy',
      'intervals','centered_p','valid_counts','sandwich_se','point_thresholds','calibration_valid',
      'evaluation_class_counts','oracle_point_policy','oracle_point_contrasts','oracle_thresholds',
      'oracle_truth_raw','oracle_truth','oracle_intervals','oracle_centered_p','oracle_sandwich_se']
    files=[];rawsources=[]
    chunks={Path(r['path']).name:r for r in completion['chunks']}
    for scenario in contract['conditions']:
        parts=[]
        for start in range(0,1000,25):
            name=f"{scenario['id']}-{start:04d}-{start+25:04d}.npz";path=raw/'chunks'/name
            digest=sha(path)
            if digest!=chunks[name]['sha256']:raise ValueError('Raw chunk hash mismatch '+name)
            with np.load(path,allow_pickle=False) as z:
                d={k:z[k] for k in keys};d['outer_index']=np.arange(start,start+25,dtype=np.int64)
                ms=[];sds=[];cts=[];qs=[]
                for key in ['conditional_policy_draws','refit_policy_draws']:
                    m,s,c,q=moments(z[key]);ms.append(m);sds.append(s);cts.append(c);qs.append(q)
                d['bootstrap_mean']=np.stack(ms,axis=1);d['bootstrap_sd']=np.stack(sds,axis=1)
                d['bootstrap_count']=np.stack(cts,axis=1);d['bootstrap_quantiles']=np.stack(qs,axis=1)
                m,s,c,q=moments(z['oracle_conditional_policy_draws'])
                d['oracle_bootstrap_mean']=m;d['oracle_bootstrap_sd']=s
                d['oracle_bootstrap_count']=c;d['oracle_bootstrap_quantiles']=q
                fits=z['refit_thresholds'];d['refit_threshold_mean']=np.nanmean(fits,axis=1)
                d['refit_threshold_sd']=np.nanstd(fits,axis=1,ddof=1)
            parts.append(d);rawsources.append({'file':name,'sha256':digest,'bytes':path.stat().st_size})
        arrays={k:np.concatenate([p[k] for p in parts],axis=0) for k in parts[0]}
        if not np.array_equal(arrays['outer_index'],np.arange(1000)):raise ValueError('Outer census')
        metadata={'condition':scenario,'contract_sha256':sha(parent/'contract-v1.json'),
          'scope':'Saved point/interval/p/moment arrays; no DGM, bootstrap, or reference draws regenerated'}
        arrays['metadata']=np.array(json.dumps(metadata,sort_keys=True))
        out=output/(scenario['id']+'.npz')
        with out.open('xb') as f:np.savez_compressed(f,**arrays)
        files.append({'condition':scenario['id'],'file':out.name,'sha256':sha(out),'bytes':out.stat().st_size,
          'outer_count':1000,'array_keys':[k for k in arrays if k!='metadata']})
        print(json.dumps({'compacted':scenario['id'],'bytes':out.stat().st_size}),flush=True)
    manifest={'schema':'camv-reviewer-simulation-compact-replay-v1','contract':contract,'files':files,
      'raw_chunks':rawsources,'raw_computation_completion_sha256':sha(raw/'computation-completion.json'),
      'extractor_sha256':sha(__file__),'raw_source_bytes':sum(r['bytes'] for r in rawsources),
      'compact_array_bytes':sum(r['bytes'] for r in files),'model_requests':0,'new_scientific_draws':0,
      'replay_scope':'Recompute all new summary tables and figures from all 12000 saved outer point/interval/p/moment arrays. Does not rerun inner bootstrap, DGM, or oracle integration.'}
    (output/'manifest.json').write_text(json.dumps(clean(manifest),indent=2,sort_keys=True,allow_nan=False)+'\n')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result=build(a.raw,a.output)
    print(json.dumps({'complete':True,'compact_array_bytes':result['compact_array_bytes'],'raw_bytes':result['raw_source_bytes']}))
