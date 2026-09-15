"""Download published release assets by exact name and verify SHA-256.

The repository owner/name is supplied by the user after publication; no public
repository URL is assumed or advertised by this local preparation package.
"""
from pathlib import Path
import argparse, json, os, re, urllib.parse, urllib.request
from reproduce import sha

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',required=True,help='Actual GitHub owner/repository')
    parser.add_argument('--tag',default='v8-repro-1')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repository):parser.error('Expected owner/repository')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',args.tag):parser.error('Invalid release tag')
    args.output.mkdir(parents=True,exist_ok=True)
    assets=json.loads((Path(__file__).resolve().parent/'assets.json').read_text())['assets']
    for a in assets:
        target=args.output/a['file']
        if target.exists():
            if target.stat().st_size==a['bytes'] and sha(target)==a['sha256']:
                print('Already verified '+target.name);continue
            raise ValueError('Existing asset differs; choose a new output directory: '+str(target))
        temp=target.with_suffix(target.suffix+'.partial')
        if temp.exists():raise ValueError('Partial download exists: '+str(temp))
        url='https://github.com/'+args.repository+'/releases/download/'+urllib.parse.quote(args.tag,safe='')+'/'+a['file']
        print('Downloading '+a['file'],flush=True);total=0
        with urllib.request.urlopen(url,timeout=60) as response,temp.open('xb') as f:
            while True:
                block=response.read(1024*1024)
                if not block:break
                total+=len(block)
                if total>a['bytes']:raise ValueError('Download exceeds manifest size')
                f.write(block)
        if total!=a['bytes'] or sha(temp)!=a['sha256']:raise ValueError('Asset checksum mismatch; partial file retained: '+str(temp))
        os.replace(temp,target)
        print('Verified '+target.name,flush=True)

if __name__=='__main__':main()
