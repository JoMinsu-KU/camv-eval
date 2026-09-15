"""Independent saved-array arithmetic checks, without regenerating observations."""
from pathlib import Path
import csv,gzip,hashlib,json,math
import numpy as np
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,message):
    if not x:raise ValueError(message)
def close(x,y,tol=1e-12):return bool(np.allclose(x,y,atol=tol,rtol=tol,equal_nan=True))
def interaction(v):return (v[...,1,:]-v[...,3,:])-(v[...,0,:]-v[...,2,:])
def main():
    manifest=json.loads((HERE/'compact-v1/manifest.json').read_text())
    contract=manifest['contract'];summ=HERE/'summary-v1'
    rows=list(csv.DictReader((summ/'coverage-and-diagnostics.csv').open()))
    tests=list(csv.DictReader((summ/'centered-tests.csv').open()))
    checked_rows=0;checked_tests=0;checked_raw_arrays=0;moment_max=0.;loaded={}
    for entry in manifest['files']:
        cid=entry['condition'];path=HERE/'compact-v1'/entry['file']
        need(sha(path)==entry['sha256'],'Compact manifest mismatch')
        with np.load(path,allow_pickle=False) as z:d={k:z[k] for k in z.files if k!='metadata'}
        loaded[cid]=d
        for oi in (0,999):
            lo=(oi//25)*25;name=f'{cid}-{lo:04d}-{lo+25:04d}.npz'
            with np.load(HERE/'run/chunks'/name,allow_pickle=False) as raw:
                j=oi-lo
                for key in ['point_contrasts','conditional_truth_contrasts','intervals','centered_p','point_thresholds',
                   'oracle_point_contrasts','oracle_truth','oracle_intervals','oracle_centered_p']:
                    need(np.array_equal(d[key][oi],raw[key][j],equal_nan=True),'Raw/compact array mismatch '+key)
                    checked_raw_arrays+=1
                for mi,key in enumerate(['conditional_policy_draws','refit_policy_draws']):
                    x=interaction(raw[key][j]);mu=x.mean(axis=0);ss=x.std(axis=0,ddof=1)
                    err=np.max(np.abs(mu-d['bootstrap_mean'][oi,mi,4]));moment_max=max(moment_max,float(err))
                    need(close(mu,d['bootstrap_mean'][oi,mi,4],1e-13),'Bootstrap moment mismatch')
                    need(close(ss,d['bootstrap_sd'][oi,mi,4],1e-13),'Bootstrap SD mismatch')
        for row in [r for r in rows if r['condition']==cid]:
            mi=0 if row['metric']=='false_success_rate' else 1
            if row['arm']=='fixed_population_oracle_thresholds':
                ai=0 if row['algorithm']=='conditional_percentile' else 1
                bounds=d['oracle_intervals'][:,ai,4,mi];truth=d['oracle_truth'][:,4,mi]
                point=d['oracle_point_contrasts'][:,4,mi]
            else:
                ai=['conditional_percentile','refit_percentile','refit_basic','cluster_sandwich_t'].index(row['algorithm'])
                bounds=d['intervals'][:,ai,4,mi];point=d['point_contrasts'][:,4,mi]
                truth=d['conditional_truth_contrasts'][:,4,mi] if row['target']=='fitted_policy' else np.repeat(contract['procedure_reference'][cid]['mean'][mi],1000)
            valid=np.isfinite(bounds).all(axis=1)&np.isfinite(point)&np.isfinite(truth)
            hit=valid&(bounds[:,0]<=truth)&(bounds[:,1]>=truth);mid=(bounds[:,0]+bounds[:,1])/2
            need(int(row['coverage_events'])==int(hit.sum()) and int(row['coverage_valid_n'])==int(valid.sum()),'Coverage count mismatch')
            need(close(float(row['point_bias']),np.mean(point-truth)),'Bias mismatch')
            need(close(float(row['point_empirical_sd']),np.std(point,ddof=1)),'Empirical SD mismatch')
            need(close(float(row['point_rmse']),np.sqrt(np.mean((point-truth)**2))),'RMSE mismatch')
            need(close(float(row['mean_width']),np.mean(bounds[:,1]-bounds[:,0])),'Width mismatch')
            need(close(float(row['midpoint_minus_truth_sd']),np.std(mid-truth,ddof=1)),'Center SD mismatch')
            checked_rows+=1
        for row in [r for r in tests if r['condition']==cid]:
            mi=0 if row['metric']=='false_success_rate' else 1
            pv=d['oracle_centered_p'][:,4,mi] if row['arm']=='fixed_population_oracle_thresholds' else d['centered_p'][:,0 if row['test']=='conditional' else 1,4,mi]
            need(int(row['rejection_events'])==int((np.isfinite(pv)&(pv<=.05)).sum()),'Inclusive rejection mismatch')
            checked_tests+=1
    # Identity control and analytically classified population-oracle targets.
    for cid,d in loaded.items():
        need(np.all(d['oracle_truth'][:,4,1]==0),'Oracle recall truth must be analytic zero')
        if cid.startswith('N'):
            need(np.all(d['oracle_truth'][:,4,:]==0),'Oracle null truth')
            need(np.all(d['oracle_point_contrasts'][:,4,:]==0),'Oracle null interaction degeneracy')
        else:need(np.all(d['oracle_truth'][:,4,0]<0),'Alternative oracle FSR was zeroed')
    pins=json.loads((HERE/'source-manifest-v1.json').read_text())['pins']
    comparisons=[]
    for path,digest in pins.items():
        same=sha(path)==digest;need(same,'Pinned source changed');comparisons.append({'path':path,'unchanged':same})
    result={'all_pass':True,'coverage_diagnostic_rows_recomputed':checked_rows,'test_rows_recomputed':checked_tests,
      'raw_to_compact_exact_array_checks':checked_raw_arrays,'raw_moment_probe_outer_count':24,
      'maximum_bootstrap_mean_probe_error':moment_max,'oracle_null_degeneracy_verified':True,
      'oracle_alternative_FSR_nonzero_verified':True,'source_hash_checks':comparisons,
      'scope':'No new scientific draws: all summary counts and moments checked from saved compact arrays, plus 24 fixed raw-inner probes.'}
    (HERE/'validation-v1.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='source_hash_checks'}))
if __name__=='__main__':main()
