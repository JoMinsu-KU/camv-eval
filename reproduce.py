"""Run the frozen CAMV-Eval numerical replays from one public entry point.

No model inference or network access. All output paths must be new and outside
this repository. Full mode needs the three release assets listed in assets.json.
"""
from pathlib import Path, PurePosixPath
import argparse, csv, hashlib, json, os, platform, stat, subprocess, sys, time, zipfile

ROOT=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def readj(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def writej(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')

def verify_repository():
    manifest=readj(ROOT/'MANIFEST.json')
    for name,record in manifest['files'].items():
        p=(ROOT/name).resolve()
        if not p.is_relative_to(ROOT) or not p.is_file() or sha(p)!=record['sha256']:
            raise ValueError('Repository file failed integrity check: '+name)
    return len(manifest['files'])

def safe_extract(archive,dest):
    """Validate every name before writing; never overwrite or accept symlinks."""
    dest=dest.resolve()
    if dest.exists():raise ValueError('Extraction directory already exists: '+str(dest))
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist(); names=set(); total=sum(i.file_size for i in infos)
        if total>2*1024**3:raise ValueError('Unexpected uncompressed archive size')
        for info in infos:
            n=info.filename;rel=PurePosixPath(n);mode=info.external_attr>>16
            if '\\' in n or ':' in n or rel.is_absolute() or '..' in rel.parts or stat.S_ISLNK(mode):
                raise ValueError('Unsafe archive member: '+n)
            if n.casefold() in names:raise ValueError('Duplicate archive member: '+n)
            names.add(n.casefold())
            if not dest.joinpath(*rel.parts).resolve().is_relative_to(dest):raise ValueError(n)
        dest.mkdir(parents=True)
        for info in infos:
            p=dest.joinpath(*PurePosixPath(info.filename).parts)
            if info.is_dir():p.mkdir(parents=True,exist_ok=True);continue
            p.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as src,p.open('xb') as target:
                for b in iter(lambda:src.read(4*1024*1024),b''):target.write(b)

def run(command,label,out,receipts):
    print('START '+label,flush=True);start=time.perf_counter()
    env=os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',PYTHONUTF8='1',
               OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    log=out/'logs'/(label+'.log')
    with log.open('w',encoding='utf-8') as f:
        process=subprocess.run([sys.executable,'-X','utf8',*map(str,command)],cwd=ROOT,
                               env=env,stdout=f,stderr=subprocess.STDOUT)
    receipts.append(dict(stage=label,exit_code=process.returncode,elapsed_seconds=time.perf_counter()-start,
                         command=[sys.executable,'-X','utf8',*map(str,command)],log=str(log.relative_to(out))))
    if process.returncode:raise RuntimeError(label+' failed; see '+str(log))
    print('PASS '+label+f' ({time.perf_counter()-start:.1f}s)',flush=True)

def compare_file(expected,actual,checks):
    ok=sha(expected)==sha(actual)
    checks.append(dict(item=actual.name,passed=ok,sha256=sha(actual)))
    if not ok:raise AssertionError('Output differs: '+str(actual))

def require_receipt(path,accepted,receipts):
    result=readj(path)
    if result.get('status') not in accepted:raise ValueError('Nonpassing receipt: '+str(path))
    receipts.append(dict(receipt=str(path),sha256=sha(path),status=result['status'],
                         checks=result.get('check_count',result.get('comparisons',result.get('checks')))))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['quick','all'],default='quick')
    parser.add_argument('--assets-dir',type=Path,help='Directory containing all three immutable release ZIPs')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists() or out.is_relative_to(ROOT):parser.error('--output must be a new directory outside the repository')
    # Check assets before creating output, so a missing download is harmless.
    assets=readj(ROOT/'assets.json')['assets'];locations={}
    if args.mode=='all':
        if args.assets_dir is None:parser.error('--mode all requires --assets-dir')
        for a in assets:
            p=args.assets_dir.resolve()/a['file']
            if not p.is_file() or p.stat().st_size!=a['bytes'] or sha(p)!=a['sha256']:
                parser.error('Missing or changed release asset: '+str(p))
            locations[a['id']]=p
    count=verify_repository();out.mkdir(parents=True);(out/'logs').mkdir()
    receipts=[];checks=[];start=time.perf_counter()
    status='FAILED'
    try:
        quick=out/'results/table5'
        run([ROOT/'examples/table5/extract_table5.py','--output',quick],'table5',out,receipts)
        for name in ['table5-intervals.csv','table5-rows.md']:
            compare_file(ROOT/'examples/table5/expected'/name,quick/name,checks)
        v=readj(quick/'verification.json')
        if not v['passed'] or v['check_count']!=64:raise AssertionError('Table5 verification')
        if args.mode=='all':
            inputs=out/'inputs';inputs.mkdir()
            for label in ['v4','v7','v8']:safe_extract(locations[label],inputs/label)
            # Each nested archive is authenticated by its already verified parent.
            v3zip=inputs/'v4/baseline/CAMV-Eval_Review_Supplement_v3.zip'
            parent=readj(inputs/'v4/manifest.json')['sha256']
            if sha(v3zip)!=parent['baseline/CAMV-Eval_Review_Supplement_v3.zip']:raise AssertionError('v3 lineage')
            safe_extract(v3zip,inputs/'v3')
            v2zip=inputs/'v3/baseline/CAMV-Eval_Review_Supplement_v2.zip'
            parent=readj(inputs/'v3/manifest.json')['sha256']
            if sha(v2zip)!=parent['baseline/CAMV-Eval_Review_Supplement_v2.zip']:raise AssertionError('v2 lineage')
            safe_extract(v2zip,inputs/'v2')
            for label,script in [('original-and-review-v2',inputs/'v2/package/replay_review.py'),
                                 ('scorer-and-ties-v3',inputs/'v3/replay_revision.py'),
                                 ('weak-discrimination-bca-v4',inputs/'v4/replay_review_v4.py')]:
                dest=out/'results'/label
                run([script,'--output',dest],label,out,receipts)
                require_receipt(dest/'completion.json',{'COMPLETE','PASS'},receipts)
            sim=inputs/'v4/amendments/review-response-20260915-v1/simulation'
            n1=out/'results/translation-audit'
            run([inputs/'v7/n1-audit/audit_n1.py','--source-root',sim,'--output',n1],'translation-audit',out,receipts)
            require_receipt(n1/'audit-result.json',{'PASS'},receipts)
            widths=out/'results/widths'
            run([inputs/'v7/compute_width_ratios.py','--input',inputs/'v7/width-audit/inputs/outer-widths.csv.gz','--output',widths],
                'width-diagnostics',out,receipts)
            compare_file(ROOT/'results/width-ratios.csv',widths/'width-ratios.csv',checks)
            # S43 uses saved SDs; it is a summary consistency check, not new data.
            with (sim/'summary-v2/centers.csv').open(encoding='utf-8',newline='') as f:centers=list(csv.DictReader(f))
            with (ROOT/'results/tableS43-centers.csv').open(encoding='utf-8',newline='') as f:expected=list(csv.DictReader(f))
            for row in expected:
                records={r['method']:r for r in centers if (r['condition'],r['metric'])==(row['condition'],row['metric'])}
                vals={'point_sd_pp':float(records['refit_percentile']['point_sd_pp'])}
                vals.update({m+'_midpoint_sd_pp':float(records[m]['center_sd_pp']) for m in ['refit_percentile','refit_basic','refit_BCa']})
                for k,val in vals.items():
                    ok=val==float(row[k]);checks.append(dict(item='S43/'+row['condition']+'/'+row['metric']+'/'+k,passed=ok))
                    if not ok:raise AssertionError('S43 mismatch')
            for a in assets:
                if sha(locations[a['id']])!=a['sha256']:raise AssertionError('Asset changed during replay')
        if verify_repository()!=count:raise AssertionError('Repository changed')
        status='PASS'
    finally:
        writej(out/'completion.json',dict(status=status,mode=args.mode,elapsed_seconds=time.perf_counter()-start,
              repository_files_verified=count,stages=receipts,comparisons=checks,new_model_calls=0,
              full_monte_carlo_regeneration=False,new_scientific_conditions=0,
              environment=dict(python=sys.version,platform=platform.platform(),executable=sys.executable,
                               storage=os.environ.get('CAMV_STORAGE_NOTE','User-selected storage')),
              limitations='Existing-interpreter numerical replay; not fresh-OS, cross-platform, or external-researcher validation.'))
    print(json.dumps(dict(status=status,mode=args.mode,elapsed_seconds=time.perf_counter()-start,output=str(out))),flush=True)

if __name__=='__main__':main()
