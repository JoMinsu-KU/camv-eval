"""Frozen-contract native SmolVLM scoring. Requires a root-issued GPU gate.

No label file is imported/read. Gate validation precedes all CUDA/model access.
Prompt/input audit logic has declared lineage from grasp-study/src/model_runner.py.
"""
from __future__ import annotations
import argparse,hashlib,importlib.metadata,io,json,math,os,platform,re,sys,threading,time,traceback
from collections import OrderedDict
from pathlib import Path
from common import *
from runtime import FileFirewall,RequestGuard,RunLock,process_identity,reconcile

ROOT=Path(__file__).resolve().parent
EXPECTED_REQUEST_FIELDS={'sample_id','input_hash','model_id','model_revision','seed','phase','method_id','cameras','ablation','prompt_sha256','protocol_id','attempt','condition_id','request_id'}

def validate_sample(sample):
    if set(sample)!={'sample_id','instruction','images','input_hash'}:raise ContractError('Forbidden inference sample field')
    if not re.fullmatch(r's_[0-9a-f]{32}',sample['sample_id']):raise ContractError('Sample ID is not opaque')
    if not isinstance(sample['instruction'],str) or not sample['instruction']:raise ContractError('Missing subtask instruction')
    if digest({'instruction':sample['instruction'],'images':sample['images']})!=sample['input_hash']:raise ContractError('Input hash mismatch')
    sources={}
    for image in sample['images']:
        if set(image)!={'camera','endpoint','image_id'}:raise ContractError('Forbidden nested image field')
        if not re.fullmatch(r'c[0-3]',image['camera']) or image['endpoint'] not in {'before','after'}:raise ContractError('Invalid camera or endpoint')
        if not re.fullmatch(r'im_[0-9a-f]{32}',image['image_id']):raise ContractError('Nonopaque image ID')
        key=(image['camera'],image['endpoint'])
        if key in sources:raise ContractError('Duplicated camera endpoint')
        sources[key]=image['image_id']
    cameras={key[0] for key in sources}
    if len(cameras) not in (3,4) or set(sources)!={(c,e) for c in cameras for e in ['before','after']}:raise ContractError('Missing camera endpoint')
    return sources

def validate_request(request,sample,prompt_sha):
    if set(request)!=EXPECTED_REQUEST_FIELDS:raise ContractError('Unexpected request fields')
    candidate=dict(request);rid=candidate.pop('request_id')
    if rid!='r_'+digest(candidate)[:40]:raise ContractError('Request ID mismatch')
    fixed={'model_id':MODEL_ID,'model_revision':MODEL_REVISION,'protocol_id':PROTOCOL_ID,'ablation':'native','attempt':0,'prompt_sha256':prompt_sha,'input_hash':sample['input_hash']}
    for key,value in fixed.items():
        if request[key]!=value:raise ContractError(f'Request contract mismatch: {key}')
    if request['seed'] not in (17,29,43):raise ContractError('Undeclared seed')
    cameras=request['cameras']
    if len(cameras) not in (1,2) or len(set(cameras))!=len(cameras):raise ContractError('Invalid camera condition')
    if request['method_id']!=('single' if len(cameras)==1 else 'joint'):raise ContractError('Method/camera mismatch')
    if request['condition_id']!=request['method_id']+'_'+'_'.join(cameras):raise ContractError('Condition ID mismatch')
    sources=validate_sample(sample)
    if any((c,e) not in sources for c in cameras for e in ['before','after']):raise ContractError('Condition uses absent camera')

def assemble(sample,request,prompt):
    sources=validate_sample(sample)
    content=[{'type':'text','text':prompt['instruction_prefix']+sample['instruction']}];serial=list(content);ordered=[]
    for position,camera in enumerate(request['cameras'],1):
        for endpoint in ['before','after']:
            image_id=sources[(camera,endpoint)]
            label={'type':'text','text':prompt['image_prefix'].format(position=position,camera=camera,endpoint=endpoint.upper())}
            content.extend([label,{'type':'image'}]);serial.extend([label,{'type':'image','image_id':image_id}]);ordered.append(image_id)
    content.append({'type':'text','text':prompt['QUESTION']});serial.append({'type':'text','text':prompt['QUESTION']})
    messages=[{'role':'system','content':[{'type':'text','text':prompt['SYSTEM_PROMPT']}]},{'role':'user','content':content}]
    return messages,serial,ordered

class MediaLoader:
    def __init__(self,manifest,media_root,max_cache=64):
        self.media={row['image_id']:row for row in manifest};self.root=Path(media_root);self.cache=OrderedDict();self.max_cache=max_cache
        if len(self.media)!=len(manifest):raise ContractError('Duplicate media IDs')
        for row in manifest:
            if set(row)!={'image_id','local_path','sha256','bytes','width','height','format'}:raise ContractError('Unexpected media schema')
            safe_child(self.root,row['local_path'])
    def image(self,image_id):
        from PIL import Image
        if image_id in self.cache:
            self.cache.move_to_end(image_id);return self.cache[image_id]
        row=self.media[image_id];path=safe_child(self.root,row['local_path']);raw=path.read_bytes()
        if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ContractError('Source media byte hash mismatch')
        with Image.open(io.BytesIO(raw)) as original:
            if list(original.size)!=[row['width'],row['height']] or original.format!=row['format']:raise ContractError('Media dimensions/format mismatch')
            image=original.convert('RGB');image.load()
        self.cache[image_id]=image
        while len(self.cache)>self.max_cache:self.cache.popitem(last=False)
        return image

def tensor_sha(tensor):return hashlib.sha256(tensor.contiguous().numpy().tobytes()).hexdigest()
def prepare_inputs(processor,sample,request,prompt,loader,verify_processor_extensions=False):
    messages,serial,ordered=assemble(sample,request,prompt)
    rendered=processor.apply_chat_template(messages,add_generation_prompt=True,tokenize=False)
    images=[loader.image(image_id) for image_id in ordered]
    inputs=processor(text=[rendered],images=[images],return_tensors='pt')
    ids=inputs['input_ids'][0].tolist();tok=processor.tokenizer
    candidates=[tok.encode(letter,add_special_tokens=False) for letter in ['A','B']]
    if candidates!=[[49],[50]]:raise ContractError('Unexpected literal A/B token IDs')
    expanded=tok.decode(ids,skip_special_tokens=False,clean_up_tokenization_spaces=False,spaces_between_special_tokens=False)
    if tok.encode(expanded,add_special_tokens=False)!=ids:raise ContractError('Expanded prefix roundtrip failed')
    for literal,candidate in zip(['A','B'],[49,50]):
        if tok.decode([candidate],clean_up_tokenization_spaces=False)!=literal:raise ContractError('Literal decoding mismatch')
        if tok.encode(expanded+literal,add_special_tokens=False)!=ids+[candidate]:raise ContractError('Candidate changes full expanded prefix')
        if verify_processor_extensions:
            extension=processor(text=[rendered+literal],images=[images],return_tensors='pt')['input_ids'][0].tolist()
            if extension!=ids+[candidate]:raise ContractError('Actual processor candidate extension failed')
    pixels=inputs['pixel_values'];mask=inputs['pixel_attention_mask']
    import torch
    if pixels.ndim!=5 or pixels.shape[0]!=1 or pixels.shape[2]!=3 or not torch.isfinite(pixels).all().item():raise ContractError('Invalid processed pixels')
    patches=int(mask.flatten(start_dim=2).any(dim=2).sum().item())
    visual=sum(token==49153 for token in ids)
    if patches<=0 or visual!=patches*81:raise ContractError('Visual tokens/patch support mismatch')
    audit={'messages':[{'role':'system','text':prompt['SYSTEM_PROMPT']},{'role':'user','content':serial}],'rendered_prompt':rendered,'token_ids':ids,'candidate_token_ids':[49,50],'tensor_shapes':{key:list(value.shape) for key,value in inputs.items()},'tensor_sha256':{key:tensor_sha(value) for key,value in inputs.items()},'source_media':[{'image_id':image_id,'sha256':loader.media[image_id]['sha256'],'bytes':loader.media[image_id]['bytes']} for image_id in ordered],'valid_image_patches':patches,'visual_tokens':visual,'total_input_tokens':len(ids),'decode_audit_spaces_between_special_tokens':False}
    audit['payload_sha256']=digest(audit)
    return inputs,audit

class NativeScorer:
    def __init__(self,model_dir,prompt,media,media_root,seed):
        import random,numpy as np,torch
        from transformers import AutoProcessor,Idefics3ForConditionalGeneration
        self.torch=torch;self.seed=seed;self.prompt=prompt;self.loader=MediaLoader(media,media_root)
        random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
        torch.set_num_threads(8);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.use_deterministic_algorithms(True,warn_only=True)
        self.processor=AutoProcessor.from_pretrained(model_dir,trust_remote_code=False,local_files_only=True,use_fast=False)
        self.model=Idefics3ForConditionalGeneration.from_pretrained(model_dir,trust_remote_code=False,local_files_only=True,torch_dtype=torch.bfloat16,device_map={'':'cuda:0'},attn_implementation='sdpa',low_cpu_mem_usage=True).eval()
        if type(self.processor).__name__!='Idefics3Processor' or type(self.processor.tokenizer).__name__!='GPT2Tokenizer':raise ContractError('Processor implementation mismatch')
        ip=self.processor.image_processor
        if ip.size!={'longest_edge':1536} or ip.max_image_size!={'longest_edge':384} or not ip.do_image_splitting or self.processor.image_seq_len!=81:raise ContractError('Native processor geometry changed')
        if self.model.config.image_token_id!=49153:raise ContractError('Image token ID changed')
    def hardware(self):
        properties=self.torch.cuda.get_device_properties(0)
        return {'gpu':properties.name,'gpu_total_bytes':properties.total_memory,'cuda':self.torch.version.cuda,'torch':self.torch.__version__,'storage':'E: SATA HDD','platform':platform.platform(),'cpu':platform.processor()}
    def score(self,sample,request,progress):
        torch=self.torch;start=time.perf_counter()
        inputs,audit=prepare_inputs(self.processor,sample,request,self.prompt,self.loader)
        preprocessing=time.perf_counter()-start
        progress(input=audit,preprocessing_seconds=preprocessing,visual_tokens=audit['visual_tokens'])
        torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();transfer_start=time.perf_counter()
        gpu={key:value.to(device='cuda:0',dtype=torch.bfloat16) if value.is_floating_point() else value.to('cuda:0') for key,value in inputs.items()}
        torch.cuda.synchronize();transfer=time.perf_counter()-transfer_start
        progress(calls=1,transfer_seconds=transfer)
        forward_start=time.perf_counter()
        with torch.inference_mode():
            result=self.model(**gpu,use_cache=False,logits_to_keep=1,return_dict=True)
        torch.cuda.synchronize();forward=time.perf_counter()-forward_start
        peak=int(torch.cuda.max_memory_allocated());progress(forward_seconds=forward,peak_vram_bytes=peak)
        post_start=time.perf_counter()
        logits=result.logits[0,-1].float();logprobs=torch.log_softmax(logits,dim=-1)
        chosen_lp=logprobs[[49,50]].cpu().tolist();chosen_logits=logits[[49,50]].cpu().tolist()
        top_lp,top_ids=torch.topk(logprobs,5);top_lp=top_lp.cpu().tolist();top_ids=top_ids.cpu().tolist()
        if not all(math.isfinite(value) for value in chosen_lp+chosen_logits+top_lp):raise ContractError('Nonfinite model logits/logprobs')
        logodds=float(chosen_lp[0])-float(chosen_lp[1]);score=stable_sigmoid(logodds)
        raw={'candidate_literals':['A','B'],'candidate_token_ids':[49,50],'candidate_logits':chosen_logits,'candidate_logprobs':chosen_lp,'full_vocabulary_choice_mass':math.exp(chosen_lp[0])+math.exp(chosen_lp[1]),'top_token_ids':top_ids,'top_token_text':[self.processor.tokenizer.decode([token],clean_up_tokenization_spaces=False) for token in top_ids],'top_logprobs':top_lp,'vocabulary_size':int(logits.numel())}
        post=time.perf_counter()-post_start
        return {'score':score,'logodds':logodds,'raw_output':raw,'input':audit,'calls':1,'visual_tokens':audit['visual_tokens'],'peak_vram_bytes':peak,'preprocessing_seconds':preprocessing,'transfer_seconds':transfer,'forward_seconds':forward,'postprocessing_seconds':post,'scoring_contract':'single_token_A_success_B_failure_conditional_likelihood','score_dtype':'Python_binary64_stable_sigmoid_from_saved_float32_logprobs'}

def environment_snapshot():
    packages={item.metadata['Name'].lower():item.version for item in importlib.metadata.distributions() if item.metadata.get('Name')}
    return {'python':sys.version,'executable':sys.executable,'packages':dict(sorted(packages.items())),'storage':'E: SATA HDD','environment':'Existing grasp-vlm or separately existing grasp-vlm-repro; no runner dependency installation'}

def validate_gate(gate_path,request_path,output,phase,seed):
    gate_path=Path(gate_path).resolve();request_path=Path(request_path).resolve();output=Path(output).resolve()
    gate=read_json(gate_path)
    if gate.get('status')!='APPROVED_FOR_GPU_EXECUTION' or gate.get('cuda_inference_authorized') is not True:raise ContractError('Root GPU execution gate is not granted')
    if phase not in gate['allowed_phases'] or seed not in gate['allowed_seeds']:raise ContractError('Phase/seed outside root execution gate')
    if not within(output,gate['output_root']) or not within(output,STUDY):raise ContractError('Output path outside authorized new study root')
    registry_hashes={str(Path(path).resolve()):value for path,value in gate['request_registries'].items()}
    if str(request_path) not in registry_hashes or sha_file(request_path)!=registry_hashes[str(request_path)]:raise ContractError('Request registry not frozen in gate')
    code_hashes={str(Path(path).resolve()):value for path,value in gate['code_hashes'].items()}
    required_code=[Path(__file__).resolve(),(ROOT/'common.py').resolve(),(ROOT/'runtime.py').resolve()]
    if any(str(path) not in code_hashes for path in required_code):raise ContractError('Gate omits executed source hashes')
    for path,expected in {**code_hashes,**gate['input_hashes']}.items():
        if sha_file(path)!=expected:raise ContractError(f'Frozen file hash mismatch: {path}')
    required_inputs=['science_freeze_path','protocol_path','prompt_path','samples_path','media_manifest_path','assets_manifest_path']
    normalized_inputs={str(Path(path).resolve()) for path in gate['input_hashes']}
    if any(str(Path(gate[key]).resolve()) not in normalized_inputs for key in required_inputs):raise ContractError('Gate omits required input hash')
    freeze=read_json(gate['science_freeze_path'])
    prompt_path=Path(gate['prompt_path']).resolve()
    if prompt_path!=(STUDY/freeze['active_prompt']).resolve() or sha_file(prompt_path)!=freeze['hashes'][freeze['active_prompt']]:raise ContractError('Gate prompt disagrees with active science freeze')
    if sha_file(gate['protocol_path'])!=freeze['hashes']['configs/protocol-v1.json']:raise ContractError('Scientific machine protocol hash mismatch')
    protocol=read_json(gate['protocol_path'])
    if protocol['model_id']!=MODEL_ID or protocol['revision']!=MODEL_REVISION or protocol['request_timeout_seconds']!=180 or protocol['startup_timeout_seconds']!=600:raise ContractError('Unsupported scientific contract')
    assets=read_json(gate['assets_manifest_path'])
    if assets['repo']!='HuggingFaceTB/SmolVLM-Instruct' or assets['revision']!=MODEL_REVISION:raise ContractError('Unexpected model assets')
    model_files=[]
    for record in assets['files']:
        path=safe_child(gate['model_dir'],record['path'])
        if path.stat().st_size!=record['bytes'] or sha_file(path)!=record['sha256']:raise ContractError(f'Model asset checksum mismatch: {record["path"]}')
        model_files.append(path)
    weights=[record for record in assets['files'] if record['path']=='model.safetensors']
    if len(weights)!=1 or weights[0]['sha256']!='8a4f76cb64f6f2e4e74716d8fc1cfc6a70bbb3eeea69d424c3ec9902655065eb':raise ContractError('Published weight checksum missing')
    return gate,protocol,model_files

def run(args):
    # All validation below uses only allowed configuration/opaque input metadata.
    gate,protocol,model_files=validate_gate(args.gate,args.requests,args.output,args.phase,args.seed)
    prompt=read_json(gate['prompt_path']);samples=read_rows(gate['samples_path']);media=read_rows(gate['media_manifest_path'])
    samplemap={row['sample_id']:row for row in samples}
    if len(samplemap)!=len(samples):raise ContractError('Duplicate sample IDs')
    for sample in samples:validate_sample(sample)
    prompt_sha=sha_file(gate['prompt_path'])
    allrequests=read_rows(args.requests)
    if len({row['request_id'] for row in allrequests})!=len(allrequests):raise ContractError('Duplicate request IDs')
    for request in allrequests:validate_request(request,samplemap[request['sample_id']],prompt_sha)
    requests=[row for row in allrequests if row['seed']==args.seed and row['phase']==args.phase]
    if not requests:raise ContractError('No selected requests in registered plan')
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    files=[args.gate,args.requests,*gate['code_hashes'],*gate['input_hashes'],*model_files]
    files += [safe_child(gate['media_root'],row['local_path']) for row in media]
    firewall=FileFirewall(files,output);firewall.install()
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    snapshot=environment_snapshot()
    for name,version in gate.get('expected_packages',{}).items():
        if snapshot['packages'].get(name.lower())!=version:raise ContractError(f'Environment package mismatch: {name}')
    snapshot_hash=digest(snapshot);immutable_json(output/f'environment-{snapshot_hash}.json',snapshot)
    common={'experiment_id':gate['experiment_id'],'protocol_id':PROTOCOL_ID,'protocol_sha256':sha_file(gate['protocol_path']),'prompt_sha256':prompt_sha,'prompt_version':prompt['version'],'execution_manifest_sha256':sha_file(args.gate),'code_manifest_sha256':digest(gate['code_hashes']),'assets_manifest_sha256':sha_file(gate['assets_manifest_path']),'samples_sha256':sha_file(gate['samples_path']),'media_manifest_sha256':sha_file(gate['media_manifest_path']),'environment_snapshot_sha256':snapshot_hash,'environment_snapshot_file':str(output/f'environment-{snapshot_hash}.json'),'model_revision':MODEL_REVISION,'configuration':{'dtype':'bfloat16','quantization':None,'attention':'sdpa','batch_size':1,'use_fast':False,'processor_geometry':'checkpoint_native_defaults','temperature':'NOT_APPLICABLE_NO_SAMPLING','torch_threads':8,'tf32':False,'deterministic_algorithms':'warn_only','use_cache':False,'logits_to_keep':1,'storage':'E: SATA HDD'},'metrics_reference':'Offline label-joining empirical analysis; inference cannot read outcome metadata','git_status':'UNVERSIONED_HASH_MANIFEST'}
    raw_path=output/'raw.jsonl';event_path=output/'events.jsonl'
    with RunLock(output/'run.lock'):
        completed=reconcile(raw_path,event_path,requests,common)
        needed=[row for row in requests if row['request_id'] not in completed]
        append(event_path,{'event':'RUN_OPEN','timestamp_utc':now(),'process':process_identity(),'planned':len(requests),'previous_completed':len(completed),'gate_sha256':common['execution_manifest_sha256']})
        if not needed:
            append(event_path,{'event':'RUN_COMPLETE','timestamp_utc':now(),'planned':len(requests),'new_attempts':0})
            print(canonical({'status':'ALREADY_ACCOUNTED','requests':len(requests)}));return
        def startup_timeout():
            append(event_path,{'event':'STARTUP_TIMEOUT','timestamp_utc':now(),'timeout_seconds':600,'process':process_identity()});os._exit(125)
        timer=threading.Timer(600,startup_timeout);timer.daemon=True;timer.start();loading=time.perf_counter()
        try:scorer=NativeScorer(gate['model_dir'],prompt,media,gate['media_root'],args.seed)
        except BaseException as exc:
            append(event_path,{'event':'STARTUP_FAILURE','timestamp_utc':now(),'error':repr(exc),'traceback':traceback.format_exc()});raise
        finally:timer.cancel()
        common['hardware']=scorer.hardware()
        append(event_path,{'event':'MODEL_READY','timestamp_utc':now(),'load_seconds':time.perf_counter()-loading,'hardware':common['hardware']})
        for index,request in enumerate(needed,1):
            guard=RequestGuard(request,common,raw_path,event_path,180);guard.start()
            try:
                result=scorer.score(samplemap[request['sample_id']],request,guard.update)
                guard.finish(result=result)
            except BaseException as exc:
                oom=isinstance(exc,scorer.torch.cuda.OutOfMemoryError)
                category='OOM' if oom else 'FORMAT_ERROR' if isinstance(exc,ContractError) else 'EXECUTION_FAILURE' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'MODEL_FAILURE'
                guard.finish(status=category,error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
                # Pause technical invalidity; original first attempt remains immutable.
                append(event_path,{'event':'TECHNICAL_PAUSE','timestamp_utc':now(),'request_id':request['request_id'],'category':category,'no_retry':True});raise
            if index==1 or index%16==0 or index==len(needed):print(canonical({'event':'progress','phase':args.phase,'seed':args.seed,'new_completed':index,'new_planned':len(needed),'request_id':request['request_id']}),flush=True)
        append(event_path,{'event':'RUN_COMPLETE','timestamp_utc':now(),'planned':len(requests),'new_attempts':len(needed),'firewall_denials':firewall.denials})
        print(canonical({'status':'COMPLETE_ACCOUNTING','phase':args.phase,'seed':args.seed,'planned':len(requests),'new_attempts':len(needed)}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--gate',type=Path,required=True);parser.add_argument('--requests',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--phase',required=True);parser.add_argument('--seed',type=int,choices=[17,29,43],required=True)
    run(parser.parse_args())
