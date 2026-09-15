from pathlib import Path
import gzip,json,collections
S=Path('E:/SoftwareX/camv-eval-study-v1')
p=S/'amendments/score-ties-revision-20260915-v1/scorer/inputs/collections.json.gz'
with gzip.open(p,'rt',encoding='utf-8') as f:d=json.load(f)
for col,rows in d.items():
 b=collections.defaultdict(dict)
 for r in rows:b[(r['dataset'],r['split'])][r['sample_id']]=r
 for key,meta in b.items():
  groups=collections.defaultdict(list)
  for r in meta.values():groups[r['group_id']].append(r['label'])
  print(key,'n',len(meta),'G',len(groups),'succ',sum(r['label'] for r in meta.values()),'G_succ',sum(1 in x for x in groups.values()),'G_fail',sum(0 in x for x in groups.values()))
