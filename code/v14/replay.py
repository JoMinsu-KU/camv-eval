#!/usr/bin/env python3
"""Portable, read-only numerical replay for the v14 empirical-law supplement.

The original frozen engine is preserved byte for byte. Only its SOURCE binding
is redirected, after import, to the explicitly packaged score projection.
"""
from pathlib import Path
import argparse, csv, hashlib, importlib.util, json, os, sys, time

sys.dont_write_bytecode=True
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'

def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1<<20),b''):value.update(block)
    return value.hexdigest()

def rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:return list(csv.DictReader(handle))

def bounded_path(root,relative):
    target=(root/relative).resolve()
    if not target.is_relative_to(root.resolve()):raise ValueError('Manifest path leaves package')
    return target

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fresh-first',action='store_true',help='Also regenerate outer indices 0, 17 and 999, without saving new results.')
    parser.add_argument('--report',type=Path,help='Optional new JSON audit output; never overwrites any package file.')
    parser.add_argument('--deny-source-root',type=Path,help='Portability test: deny reads beneath an external original study root.')
    args=parser.parse_args();started=time.perf_counter();root=Path(__file__).resolve().parent
    sim=root/'empirical_laws';source=root/'inputs/collections.json.gz'
    if args.deny_source_root:
        denied=str(args.deny_source_root.resolve()).casefold().replace('\\','/').rstrip('/')
        allowed=str(root.resolve()).casefold().replace('\\','/').rstrip('/')
        def scientific_read_guard(event,event_args):
            if event!='open' or not event_args or not isinstance(event_args[0],(str,bytes,os.PathLike)):return
            name=os.fsdecode(event_args[0]);norm=str(Path(name).resolve()).casefold().replace('\\','/')
            if (norm==denied or norm.startswith(denied+'/')) and not (norm==allowed or norm.startswith(allowed+'/')):
                raise RuntimeError('Read outside relocated package into denied study root: '+name)
        sys.addaudithook(scientific_read_guard)
    import numpy as np
    import scipy
    from scipy.stats import t as student_t
    manifest=json.loads((root/'MANIFEST-SHA256.json').read_text(encoding='utf-8'))
    for relative,meta in manifest['files'].items():
        path=bounded_path(root,relative)
        assert path.stat().st_size==meta['bytes'],relative
        assert digest(path)==meta['sha256'],relative
    protocol=json.loads((sim/'frozen-protocol.json').read_text(encoding='utf-8'))
    portable=json.loads((root/'PORTABLE_MAP.json').read_text(encoding='utf-8'))
    assert protocol['M']==1000 and protocol['B']==999
    for historical,expected in protocol['pinned_files'].items():
        local=bounded_path(root,portable['frozen_pin_paths'][historical])
        assert digest(local)==expected,historical
    spec=importlib.util.spec_from_file_location('portable_frozen_empirical_law_engine',sim/'empirical_law_engine.py')
    engine=importlib.util.module_from_spec(spec);sys.modules[spec.name]=engine;spec.loader.exec_module(engine)
    engine.SOURCE=source
    assert engine.SOURCE.resolve().is_relative_to(root)
    populations=engine.load_inputs()
    reference=rows(sim/'reference-targets.csv')
    refmap={(r['cohort'],r['scorer'],r['metric']):r for r in reference}
    coverage=rows(sim/'coverage.csv')
    assert len(reference)==8 and len(coverage)==80
    method=list(engine.METHODS);metrics=list(engine.METRICS)
    assert method==['conditional_percentile','refit_percentile','refit_basic','conditional_sandwich_t','refit_BCa']
    report={'status':'RUNNING','package_root':str(root),'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,
            'files_hash_verified':len(manifest['files']),'frozen_protocol_pins_verified':len(protocol['pinned_files']),
            'score_input_sha256':digest(source),'original_engine_bytes_preserved':True,
            'runtime_source_override':str(engine.SOURCE),'denied_source_root':str(args.deny_source_root) if args.deny_source_root else None,
            'saved_records_replayed':0,'ci_endpoint_values_recomputed':0,'raw_summary_fields_compared':0,'coverage_rows_reaggregated':0,
            'reference_rows_reaggregated':0,'fresh_outer_datasets':0,'fresh_scorer_records':0,'max_ci_abs_difference':0.0,
            'no_model_inference':True,'no_existing_results_written':True,'audit_snapshots_not_claimed_fully_recomputed':True}
    for cohort in ('RL','RE'):
        K=populations[cohort]['groups_dev'];GE=populations[cohort]['groups_eval'];cid=0 if cohort=='RL' else 1
        generated_reference_counts=None
        for variant in ('bare','space'):
            pop=populations[cohort]['variants'][variant]
            with np.load(sim/f'summary-arrays-{cohort}-{variant}.npz',allow_pickle=False) as data:
                summaries={key:data[key] for key in data.files}
            kept={key:[] for key in ('point','fitted_truth','intervals')}
            for index in range(1000):
                with np.load(sim/'outer'/cohort/variant/f'{index:04}.npz',allow_pickle=False) as data:
                    x={key:data[key] for key in data.files}
                assert x['conditional_draws'].shape==x['refit_draws'].shape==(999,2)
                assert x['jackknife_dev'].shape==(K,2) and x['jackknife_eval'].shape==(GE,2)
                assert x['dev_multiplicity'].sum()==K and x['eval_multiplicity'].sum()==GE
                np.testing.assert_array_equal(x['dev_multiplicity'],engine.sample_counts(K,K,cid,10,index))
                np.testing.assert_array_equal(x['eval_multiplicity'],engine.sample_counts(K,GE,cid,20,index))
                fit=x['threshold_indices'][None,:];point=pop.evaluate(fit,x['eval_multiplicity'])[0]
                np.testing.assert_allclose(point,x['point'],rtol=0,atol=1e-12,equal_nan=True)
                np.testing.assert_allclose(pop.truth(fit)[0],x['fitted_truth'],rtol=0,atol=1e-12,equal_nan=True)
                np.testing.assert_array_equal(x['counts'],np.stack([x['dev_multiplicity']@pop.class_counts,x['eval_multiplicity']@pop.class_counts]))
                expected=np.full((5,2,2),np.nan)
                for y in (0,1):
                    expected[0,y]=engine.n.interval(x['conditional_draws'][:,y])
                    expected[1,y]=engine.n.interval(x['refit_draws'][:,y])
                    expected[2,y]=engine.n.interval(x['refit_draws'][:,y],x['point'][y],True)
                expected[3],se=pop.sandwich(fit,x['eval_multiplicity'],x['point'])
                expected[4],bcdiag=engine.rc.bca(x['point'],x['refit_draws'],x['jackknife_dev'],x['jackknife_eval'])
                np.testing.assert_allclose(expected,x['intervals'],rtol=0,atol=1e-12,equal_nan=True)
                np.testing.assert_allclose(se,x['sandwich_se'],rtol=0,atol=1e-12,equal_nan=True)
                np.testing.assert_allclose(bcdiag,x['bca_diagnostics'],rtol=0,atol=1e-12,equal_nan=True)
                difference=np.abs(expected-x['intervals']);finite=difference[np.isfinite(difference)]
                if len(finite):report['max_ci_abs_difference']=max(report['max_ci_abs_difference'],float(finite.max()))
                for key in summaries:
                    np.testing.assert_array_equal(x[key],summaries[key][index])
                    report['raw_summary_fields_compared']+=1
                for key in kept:kept[key].append(x[key])
                report['saved_records_replayed']+=1;report['ci_endpoint_values_recomputed']+=20
            kept={key:np.stack(value) for key,value in kept.items()}
            for k,metric in enumerate(metrics):
                ref=refmap[(cohort,variant,metric)];mu=float(ref['target']);mu_se=float(ref['mcse'])
                for j,construction in enumerate(method):
                    ci=kept['intervals'][:,j,k]
                    for target,truth in [('fitted_policy',kept['fitted_truth'][:,k]),('procedure_average',np.full(1000,mu))]:
                        row=next(r for r in coverage if r['cohort']==cohort and r['scorer']==variant and r['metric']==metric and r['method']==construction and r['target']==target)
                        valid=np.isfinite(ci).all(axis=1)&np.isfinite(truth);hit=valid&(ci[:,0]<=truth)&(truth<=ci[:,1])
                        assert int(valid.sum())==int(row['available']) and int(hit.sum())==int(row['covered'])
                        assert abs(100*hit.mean()-float(row['coverage_planned_pct']))<1e-11
                        assert abs(100*hit.sum()/valid.sum()-float(row['coverage_available_pct']))<1e-11
                        assert abs(100*np.nanmean(ci[:,1]-ci[:,0])-float(row['mean_width_pp']))<1e-10
                        z=1.959963984540054;a=hit.mean();den=1+z*z/1000
                        center=(a+z*z/2000)/den;rad=z*np.sqrt(a*(1-a)/1000+z*z/(4*1000**2))/den
                        assert abs(100*(center-rad)-float(row['wilson_low_pct']))<1e-10
                        assert abs(100*(center+rad)-float(row['wilson_high_pct']))<1e-10
                        if target=='procedure_average':
                            for sign,label in [(-1,'minus'),(1,'plus')]:
                                shifted=mu+sign*3*mu_se
                                fraction=100*np.mean(valid&(ci[:,0]<=shifted)&(shifted<=ci[:,1]))
                                assert abs(fraction-float(row[f'reference_{label}3se_coverage_pct']))<1e-11
                        report['coverage_rows_reaggregated']+=1
            with np.load(sim/'reference'/f'{cohort}-{variant}.npz',allow_pickle=False) as data:
                values=data['reference_values'];counts=data['development_multiplicity']
            assert values.shape==(65536,2) and counts.shape==(65536,K)
            if generated_reference_counts is None:generated_reference_counts=engine.rng(cid,100).multinomial(K,np.full(K,1/K),size=65536)
            np.testing.assert_array_equal(counts,generated_reference_counts)
            valid=np.isfinite(values).all(axis=1)
            for k,metric in enumerate(metrics):
                ref=refmap[(cohort,variant,metric)];mean=values[valid,k].mean();mcse=values[valid,k].std(ddof=1)/np.sqrt(valid.sum())
                assert valid.sum()==int(ref['available']) and len(values)==int(ref['planned'])
                assert abs(mean-float(ref['target']))<1e-13 and abs(mcse-float(ref['mcse']))<1e-15
                assert mcse<=.0005
                report['reference_rows_reaggregated']+=1
    if args.fresh_first:
        for cohort in ('RL','RE'):
            for index in (0,17,999):
                generated=engine.outer(populations,cohort,index,999)
                report['fresh_outer_datasets']+=1
                for variant,x in generated.items():
                    with np.load(sim/'outer'/cohort/variant/f'{index:04}.npz',allow_pickle=False) as saved:
                        assert set(saved.files)==set(x)
                        for key in saved.files:np.testing.assert_allclose(x[key],saved[key],rtol=0,atol=1e-12,equal_nan=True)
                    report['fresh_scorer_records']+=1
    assert report['saved_records_replayed']==4000 and report['ci_endpoint_values_recomputed']==80000
    assert report['raw_summary_fields_compared']==28000 and report['coverage_rows_reaggregated']==80 and report['reference_rows_reaggregated']==8
    report.update(status='PASS',elapsed_seconds=time.perf_counter()-started,
        scope='New E1 saved numerical replay and optional first-record regeneration. Empirical/statistical audit CSVs are documented snapshots; old-law raw arrays are in the separate public v12 release. Numerical replay is not a general confidence-coverage guarantee.')
    if args.report:
        path=args.report.resolve()
        if path.exists():raise FileExistsError('Choose a new audit output path')
        if path.is_relative_to(root):raise ValueError('Audit output must be outside the immutable package')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
