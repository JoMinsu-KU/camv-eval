"""Create the one-time production protocol after successful implementation fixtures."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,platform,sys
import numpy as np
import scipy
import empirical_law_engine as e

here=Path(__file__).resolve().parent
dest=here/'frozen-protocol.json'
assert not dest.exists(),'Protocol is already frozen; do not overwrite it'
validation=json.loads((here/'validation.json').read_text())
pilot=json.loads((here/'pilot-runtime.json').read_text())
assert validation['status']==pilot['status']=='PASS'
assert pilot['engine_sha256']==e.sha(here/'empirical_law_engine.py')
files=[e.SOURCE,here/'input-manifest.json',here/'empirical_law_engine.py',here/'run_empirical_laws.py',
       here/'frozen-core'/'numerics.py',here/'frozen-core'/'review_core.py',here/'PROTOCOL.md',
       here/'validation.json',here/'pilot-runtime.json',Path(__file__).resolve()]
p=dict(protocol_id='E1-empirical-group-populations-20261104-v1',created_utc=datetime.now(timezone.utc).isoformat(),
       engine_arithmetic='Exact signed integer count ratio divided by P times class denominator',
       M=1000,B=999,groups={'RL':[40,179],'RE':[111,37]},
       conditions=['EP-RL-bare','EP-RL-space','EP-RE-bare','EP-RE-space'],
       reference_initial_N=65536,reference_cap_N=262144,reference_mcse_max_rate=.0005,
       nominal_confidence=.95,reference_coverage_sensitivity_mcse=3,
       seed_root=list(e.ROOT),max_workers=2,
       environment=dict(python=sys.executable,python_version=sys.version,numpy=np.__version__,scipy=scipy.__version__,
                        platform=platform.platform(),storage='E: SATA HDD',blas_omp_threads=1),
       pinned_files={str(f):e.sha(f) for f in files})
e.dump(dest,p)
print(json.dumps(dict(protocol_sha256=e.sha(dest),engine_sha256=e.sha(here/'empirical_law_engine.py'),runner_sha256=e.sha(here/'run_empirical_laws.py')),indent=2))
