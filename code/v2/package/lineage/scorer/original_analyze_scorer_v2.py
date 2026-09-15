"""Portable descriptive analysis of fixed dev-only scorer diagnostics."""
from pathlib import Path
from collections import Counter
import argparse,csv,hashlib,json,math,re
import numpy as np

SCORERS=['ab_bare','ab_space','word_bare','word_space']
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines() if s]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(x):return None if not np.isfinite(x) else float(x)
def ratio(w,v,mask):
    n=w[:,mask].sum(axis=1)
    return np.divide(w[:,mask]@v[mask],n,out=np.full(len(w),np.nan),where=n>0)
def auroc(w,s,y):
    use=np.isfinite(s);p=use&(y==1);n=use&(y==0)
    comp=(s[p,None]>s[None,n]).astype(float)+.5*(s[p,None]==s[None,n])
    den=w[:,p].sum(axis=1)*w[:,n].sum(axis=1)
    num=np.einsum('bi,ij,bj->b',w[:,p],comp,w[:,n],optimize=True)
    return np.divide(num,den,out=np.full(len(w),np.nan),where=den>0)
def summarize(point,boots,prefix):
    valid=np.isfinite(boots);n=int(valid.sum());okay=n>=.95*len(boots)
    qs=np.quantile(boots[valid],[.025,.975]) if okay else [np.nan,np.nan]
    return {prefix:finite(point),prefix+'_lo':finite(qs[0]),prefix+'_hi':finite(qs[1]),prefix+'_valid_bootstrap':n}
def writecsv(path,rs):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def pinned_basename(pins, name):
    found=[h for p,h in pins.items() if p.replace('\\','/').rsplit('/',1)[-1]==name]
    assert len(found)==1, ('Ambiguous or absent pin',name)
    return found[0]
def preflight(args):
    out=Path(args.output)
    assert not out.exists(), 'Analysis output must be fresh; preserve prior attempts'
    paths={key:Path(getattr(args,key)) for key in
        ['raw','labels','requests','plan','run_completion','run_identity','protocol','gate']}
    readj=lambda key:json.loads(paths[key].read_text(encoding='utf-8'))
    completion=readj('run_completion');identity=readj('run_identity')
    protocol=readj('protocol');gate=readj('gate');plan=readj('plan')
    assert completion['status']=='ATTEMPTS_COMPLETE'
    assert completion['planned_contexts']==288 and completion['planned_branches']==864
    assert gate['status']=='APPROVED_FOR_DIAGNOSTIC_EXECUTION' and gate['logical_operation_cap']==864
    assert protocol['planned_trials']==96 and protocol['planned_contexts']==288
    pins={str(p):sha(p) for p in paths.values()}
    assert completion['raw_sha256']==sha(paths['raw'])
    assert completion['protocol_sha256']==sha(paths['protocol'])==gate['protocol_sha256']==identity['protocol_sha256']
    assert completion['code_pins']==gate['code_pins']==identity['code_pins']
    assert identity['gate_sha256']==sha(paths['gate'])
    assert identity['extra_input_pins']==gate['extra_input_pins']
    assert identity['input_pins']==protocol['input_pins']
    assert sha(paths['labels'])==protocol['label_file_pin']
    assert sha(paths['requests'])==pinned_basename(protocol['input_pins'],'requests.jsonl')==identity['planned_requests_sha256']
    assert sha(paths['plan'])==pinned_basename(gate['extra_input_pins'],'analysis-plan-v1.json')
    run_id=identity['run_identity']
    assert run_id==hashlib.sha256(json.dumps({k:v for k,v in identity.items() if k!='run_identity'},sort_keys=True).encode()).hexdigest()
    assert completion['new_test_inference']==0 and completion['no_scientific_retry'] is True
    assert not completion['label_firewall_denials']
    raw=rows(paths['raw']);labels=rows(paths['labels']);requests=rows(paths['requests'])
    assert len(labels)==96 and len({r['sample_id'] for r in labels})==96
    labelmap={r['sample_id']:r for r in labels}
    assert {r['dataset'] for r in labels}=={'rlbenchfail','reassemble'}
    for ds,expected in protocol['sample_counts'].items():
        subset=[r for r in labels if r['dataset']==ds]
        assert len(subset)==expected['trials']==48
        assert Counter(int(r['label']) for r in subset)=={0:24,1:24}
        assert all(r['split']=='dev' for r in subset)
        assert dict(Counter(r['group_id'] for r in subset))==expected['group_counts']
    assert len(requests)==288 and len({r['request_id'] for r in requests})==288
    assert Counter((r['sample_id'],r['context']) for r in requests)==Counter(
        (sid,c) for sid in labelmap for c in ['joint','single0','single1'])
    for r in requests:
        pair=labelmap[r['sample_id']]['pair']
        assert len(pair)==2 and len(set(pair))==2
        assert r['camera_order']==(pair if r['context']=='joint' else [pair[int(r['context'][-1])]])
    expected={(r['request_id'],b):r for r in requests for b in ['ab_forward','ab_generation','word_forward']}
    assert len(raw)==864 and len({(r['request_id'],r['branch']) for r in raw})==864
    assert {(r['request_id'],r['branch']) for r in raw}==set(expected)
    assert dict(Counter(r['status'] for r in raw))==completion['branch_status_counts']
    for r in raw:
        assert r['run_identity']==run_id and r['request']==expected[(r['request_id'],r['branch'])]
        assert r['status'] in {'SUCCESS','TIMEOUT','OOM','EXECUTION_FAILURE','INFRA_FAILURE'}
        if r['status']!='SUCCESS':continue
        if r['branch']=='ab_generation':
            n=r['native'];clean=n['text'].strip();ids=n['generated_token_ids']
            assert n['new_tokens']==len(ids) and 0<=len(ids)<=16
            assert n['stop_reason']==('eos' if 49154 in ids else ('cap' if len(ids)>=16 else 'other'))
            cap=n['stop_reason']=='cap';m=re.fullmatch(r'([AB])[.!]?',clean)
            assert n['strict_label']==(None if cap else (1 if clean=='A' else (0 if clean=='B' else None)))
            assert n['secondary_label']==(None if cap or m is None else int(m.group(1)=='A'))
            assert n['generation_config']==protocol['native_generation']
        else:
            names={'ab_bare','ab_space'} if r['branch']=='ab_forward' else {'word_bare','word_space'}
            assert set(r['output']['scores'])==names
            for name,z in r['output']['scores'].items():
                contract=protocol['candidate_contracts'][name]
                assert z['strings']==contract['strings'] and z['token_ids']==contract['ids']
                assert z['token_count']==[1,1] and z['eos_included'] is False
                assert z['mean_logprobs']==z['sum_logprobs']
                assert len(z['sum_logprobs'])==2 and all(math.isfinite(x) and x<=0 for x in z['sum_logprobs'])
                assert math.isfinite(z['logodds']) and 0<=z['score']<=1 and 0<=z['vocabulary_mass']<=1
                assert z['decision_at_half']==int(z['logodds']>=0)
                assert math.isclose(z['vocabulary_mass'],sum(math.exp(x) for x in z['sum_logprobs']),rel_tol=1e-14,abs_tol=1e-16)
    return paths,pins,raw,labels,requests,plan
def analyze(args):
    paths,pins,raw,labels,requests,plan=preflight(args)
    assert len(labels)==96 and len(requests)==288 and len(raw)==864
    requestmap={r['request_id']:r for r in requests};assert len(requestmap)==288
    recordmap={};scoremap={};nativemap={}
    for r in raw:
        k=(r['request_id'],r['branch']);assert k not in recordmap and k[0] in requestmap
        recordmap[k]=r;request=requestmap[k[0]]
        assert r['request']==request
        if r['status']!='SUCCESS':continue
        sid,context=request['sample_id'],request['context']
        if r['branch']=='ab_generation':nativemap[(sid,context)]=r['native'];continue
        for name,z in r['output']['scores'].items():
            a,b=z['sum_logprobs'];expected=a-b
            assert np.isclose(z['logodds'],expected,rtol=0,atol=0)
            assert np.isclose(z['score'],np.exp(-np.logaddexp(0,-expected)),rtol=0,atol=2e-16)
            scoremap[(sid,context,name)]=z
    metrics=[];native=[];agreement=[];scorer_pairs=[];flat=[]
    bootstrap_seed=plan['bootstrap']['seed'];B=plan['bootstrap']['B']
    for dataset in ['rlbenchfail','reassemble']:
        labs=sorted([r for r in labels if r['dataset']==dataset],key=lambda x:x['sample_id'])
        assert len(labs)==48
        ids=[r['sample_id'] for r in labs];y=np.array([int(r['label']) for r in labs])
        groups=sorted({r['group_id'] for r in labs});gi=np.array([groups.index(r['group_id']) for r in labs]);G=len(groups)
        rng=np.random.default_rng(bootstrap_seed+plan['bootstrap']['dataset_seed_offset'][dataset])
        draw=rng.integers(0,G,size=(B,G));counts=np.stack([np.bincount(x,minlength=G) for x in draw])
        w=np.vstack([np.ones(48),counts[:,gi]])
        bycontext={}
        for context in ['joint','single0','single1','late']:
            bycontext[context]={}
            for name in SCORERS:
                s=[];logits=[];mass=[]
                for sid in ids:
                    if context=='late':
                        a=scoremap.get((sid,'single0',name));b=scoremap.get((sid,'single1',name))
                        z=np.nan if a is None or b is None else (a['logodds']+b['logodds'])/2
                        value=float(np.exp(-np.logaddexp(0,-z))) if np.isfinite(z) else np.nan
                        m=np.nan
                    else:
                        r=scoremap.get((sid,context,name));z=np.nan if r is None else r['logodds']
                        value=np.nan if r is None else r['score'];m=np.nan if r is None else r['vocabulary_mass']
                    s.append(value);logits.append(z);mass.append(m)
                s=np.array(s);logits=np.array(logits);mass=np.array(mass);valid=np.isfinite(s)
                bycontext[context][name]=s
                predicted=(s>=.5).astype(float)
                auc=auroc(w,s,y);acc=ratio(w,(predicted==y).astype(float),valid)
                fsr=ratio(w,predicted,valid&(y==0));rec=ratio(w,predicted,valid&(y==1))
                metric={'dataset':dataset,'context':context,'scorer':name,'planned_n':48,
                    'available_n':int(valid.sum()),'available_success_n':int((valid&(y==1)).sum()),
                    'available_failure_n':int((valid&(y==0)).sum()),'groups':G,'tie_n':int((logits==0).sum()),
                    'mean_score':finite(np.nanmean(s)) if valid.any() else None,
                    'median_candidate_mass':finite(np.nanmedian(mass)) if np.isfinite(mass).any() else None}
                for key,a in [('auroc',auc),('balanced_subset_accuracy_at_half',acc),('diagnostic_fsr_at_half',fsr),('diagnostic_recall_at_half',rec)]:
                    metric.update(summarize(a[0],a[1:],key))
                metrics.append(metric)
                for i,sid in enumerate(ids):flat.append({'dataset':dataset,'sample_id':sid,'group_id':labs[i]['group_id'],
                    'label':int(y[i]),'context':context,'scorer':name,'score':finite(s[i]),'logodds':finite(logits[i]),
                    'candidate_mass':finite(mass[i]),'available':bool(valid[i])})
                if context!='late':
                    nr=[nativemap.get((sid,context)) for sid in ids]
                    nlabels=np.array([np.nan if r is None or r['strict_label'] is None else r['strict_label'] for r in nr])
                    common=valid&np.isfinite(nlabels)
                    agree=(predicted==nlabels).astype(float)
                    rates=ratio(w,agree,common)
                    agreed=agree*common;unknown=(~common).astype(float)
                    low=(w@agreed)/w.sum(axis=1);high=(w@(agreed+unknown))/w.sum(axis=1)
                    ar={'dataset':dataset,'context':context,'scorer':name,'planned_n':48,
                        'joint_available_n':int(common.sum()),'available_success_n':int((common&(y==1)).sum()),
                        'available_failure_n':int((common&(y==0)).sum()),'agreement_count':int(agreed.sum()),
                        'unconditional_lower':float(low[0]),'unconditional_upper':float(high[0])}
                    ar.update(summarize(rates[0],rates[1:],'conditional_agreement'))
                    agreement.append(ar)
            for a in range(len(SCORERS)):
                for b in range(a+1,len(SCORERS)):
                    sa=bycontext[context][SCORERS[a]];sb=bycontext[context][SCORERS[b]]
                    valid=np.isfinite(sa)&np.isfinite(sb)
                    matched=ratio(w,((sa>=.5)==(sb>=.5)).astype(float),valid)
                    aa=auroc(w,np.where(valid,sa,np.nan),y);bb=auroc(w,np.where(valid,sb,np.nan),y)
                    pr={'dataset':dataset,'context':context,'left':SCORERS[a],'right':SCORERS[b],'available_n':int(valid.sum())}
                    pr.update(summarize(matched[0],matched[1:],'decision_agreement'))
                    pr.update(summarize(aa[0]-bb[0],aa[1:]-bb[1:],'auroc_difference'))
                    scorer_pairs.append(pr)
            if context!='late':
                nr=[nativemap.get((sid,context)) for sid in ids]
                nl=np.array([np.nan if r is None or r['strict_label'] is None else r['strict_label'] for r in nr])
                good=np.isfinite(nl);formatrates=ratio(w,good.astype(float),np.ones(48,bool))
                acc=ratio(w,(nl==y).astype(float),good)
                rec={'dataset':dataset,'context':context,'planned_n':48,
                    'generation_success_n':sum(r is not None for r in nr),'strict_valid_n':int(good.sum()),
                    'native_A_n':int((nl==1).sum()),'native_B_n':int((nl==0).sum()),
                    'available_success_n':int((good&(y==1)).sum()),'available_failure_n':int((good&(y==0)).sum()),
                    'cap_n':sum(r is not None and r['stop_reason']=='cap' for r in nr),
                    'secondary_valid_n':sum(r is not None and r['secondary_label'] is not None for r in nr)}
                rec.update(summarize(formatrates[0],formatrates[1:],'strict_format_rate'))
                rec.update(summarize(acc[0],acc[1:],'accuracy_given_strict_format'))
                native.append(rec)
    assert all(sha(p)==h for p,h in pins.items()), 'Input changed during analysis'
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    for name,rs in [('metrics.csv',metrics),('native-format.csv',native),('native-agreement.csv',agreement),('scorer-pairs.csv',scorer_pairs),('per-trial-scores.csv',flat)]:writecsv(out/name,rs)
    result={'status':'PASS','input_pins':pins,'planned_contexts':288,'planned_branches':864,
        'branch_status_counts':dict(Counter(r['status'] for r in raw)),
        'metric_rows':len(metrics),'native_rows':len(native),'agreement_rows':len(agreement),
        'pair_rows':len(scorer_pairs),'per_trial_rows':len(flat),'bootstrap_B':B,
        'all_input_hashes_unchanged':all(sha(p)==h for p,h in pins.items()),
        'interpretation':'Descriptive fixed balanced dev subset; no scorer selected; native agreement is not gold validity; half-score diagnostics are not calibrated deployment points',
        'output_sha256':{p.name:sha(p) for p in out.glob('*.csv')}}
    if not result['all_input_hashes_unchanged']:result['status']='FAIL_INPUT_CHANGED'
    (out/'completion.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert result['status']=='PASS'
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['raw','labels','requests','plan','run-completion','run-identity','protocol','gate','output']:p.add_argument('--'+key,required=True)
    analyze(p.parse_args())
