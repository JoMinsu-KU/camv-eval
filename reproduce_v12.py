"""Offline replay of the v12 numerical release in a new output directory."""
from pathlib import Path
import argparse,json,subprocess,sys,os
import reproduce as original
ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();asset=a.asset.resolve()
    if out.exists() or out.is_relative_to(ROOT):p.error('Choose a new output directory outside the repository.')
    original.verify_repository()
    expected=json.loads((ROOT/'v12-assets.json').read_text())['assets'][0]
    if asset.stat().st_size!=expected['bytes'] or original.sha(asset)!=expected['sha256']:raise ValueError('Numerical archive does not match v12-assets.json')
    out.mkdir(parents=True)
    original.safe_extract(asset,out/'evidence')
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
    subprocess.run([sys.executable,str(out/'evidence/reproduce.py'),'--output',str(out/'results')],check=True,env=env)
    result=json.loads((out/'results/replay-completion.json').read_text())
    assert result['status']=='PASS'
    (out/'completion.json').write_text(json.dumps({'status':'PASS','release':'v12-repro-1','asset_sha256':expected['sha256'],'matching_csvs':result['matching_csvs'],'new_model_calls':0},indent=2))
    print('PASS: v12 archive replay, 10 CSV comparisons, and limited regeneration.')
if __name__=='__main__':main()
