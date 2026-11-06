"""Verify, extract and replay the separate v14 numerical asset."""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys, zipfile

ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fresh-first',action='store_true')
    args=p.parse_args();asset=args.asset.resolve();out=args.output.resolve()
    if out.exists() or out==ROOT or ROOT in out.parents:
        p.error('Output must be a new directory outside this checkout.')
    catalog=json.loads((ROOT/'v14-assets.json').read_text(encoding='utf-8'))
    expected=next(x for x in catalog['assets'] if x['file']=='CAMV-Eval_v14_Reproduction.zip')
    digest=hashlib.sha256(asset.read_bytes()).hexdigest()
    if asset.stat().st_size!=expected['bytes'] or digest!=expected['sha256']:
        p.error('Asset size or SHA-256 differs from the version-fixed catalog.')
    with zipfile.ZipFile(asset) as z:
        for member in z.infolist():
            dest=(out/member.filename).resolve()
            if out not in dest.parents or (member.external_attr>>16)&0o170000==0o120000:
                p.error('Unsafe path or symlink in archive.')
        out.mkdir(parents=True)
        z.extractall(out)
    package=out/'CAMV-Eval_v14_Reproduction'
    report=out/'replay-report.json'
    cmd=[sys.executable,str(package/'replay.py'),'--report',str(report)]
    if args.fresh_first:cmd.append('--fresh-first')
    subprocess.run(cmd,check=True,cwd=package)
    result=json.loads(report.read_text(encoding='utf-8'))
    if result['status']!='PASS':raise RuntimeError('Numerical replay did not pass.')
    receipt=dict(status='PASS',release_tag='v14-repro-1',asset_sha256=digest,
                 replay_report=str(report),saved_records_replayed=result['saved_records_replayed'],
                 fresh_outer_datasets=result['fresh_outer_datasets'],no_model_inference=True)
    (out/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
