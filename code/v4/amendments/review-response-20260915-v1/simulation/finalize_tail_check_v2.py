"""Finalize already-written verified outputs after a stdout-only encoding exception."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'tail-check-v2/summary'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((OUT/'validation.json').read_text(encoding='utf-8'))
assert report['status']=='PASS' and not report['errors']
assert report['checks']==16201 and report['paired_outer_datasets']==1000
for name,digest in report['summary_sha256'].items():assert sha(OUT/name)==digest
text=(OUT/'results.md').read_text(encoding='utf-8')
assert '86.3' in text and '85.9' in text and '85.7' in text
failure=dict(status='POST_OUTPUT_DISPLAY_EXCEPTION_RESOLVED',exception='UnicodeDecodeError: cp949 could not decode UTF-8 Markdown during final stdout read',
             source='summarize_tail_check_v2.py: final print after validation.json and results.md were written',
             numerical_outputs_affected=False,scientific_rerun=False,
             original_summary_script_sha256=sha(ROOT/'summarize_tail_check_v2.py'),
             resolution='Read already-written artifacts explicitly as UTF-8 and verify their hashes; use Python -X utf8 for future execution of the preserved summarizer.')
with (OUT/'display-exception.json').open('x',encoding='utf-8') as f:json.dump(failure,f,indent=2)
receipt=dict(status='COMPLETE_VERIFIED',scientific_execution='COMPLETE',independent_numerical_verification='PASS',checks=16201,
             paired_outer_datasets=1000,old_B=999,new_B=4999,new_outer_datasets=0,new_reference_datasets=0,new_model_calls=0,
             display_exception_resolved=True,files={p.name:sha(p) for p in OUT.iterdir() if p.is_file()})
with (OUT/'completion.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
print(json.dumps(dict(status=receipt['status'],checks=receipt['checks'],summary=str(OUT)),ensure_ascii=True),flush=True)
