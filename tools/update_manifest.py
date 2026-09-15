"""Record the reviewed repository tree; this command does not validate science."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1]
excluded={'.git','.venv','venv','__pycache__','.pytest_cache','.mypy_cache','.cache','downloads','release-assets','outputs'}
files={}
for p in sorted(R.rglob('*')):
    rel=p.relative_to(R)
    if not p.is_file() or any(x in excluded for x in rel.parts) or rel.as_posix()=='MANIFEST.json':continue
    if p.suffix in {'.pyc','.pyo','.zip','.partial'} or p.name=='.env' or p.name.startswith('.env.'):continue
    files[rel.as_posix()]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(R/'MANIFEST.json').write_text(json.dumps({'schema':'camv-repository-sha256-v1','files':files},indent=2)+'\n',encoding='utf-8')
print('Recorded',len(files),'files. This is not a replacement for replay validation.')
