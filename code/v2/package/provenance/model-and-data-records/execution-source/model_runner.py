"""Audited forced-choice scoring. No outcome reader and no scientific retries."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REQUEST_TIMEOUT_S = 180
SYSTEM_PROMPT = "You assess the outcome of a completed robot grasp subtask from camera images. Use only the provided instruction and images."
QUESTION = ("Determine whether the specified grasp subtask succeeded by the AFTER observation. "
            "A means the specified grasp succeeded. B means the specified grasp failed. "
            "Judge the specified target object and grasp outcome, not whether the robot moved. "
            "Return exactly one letter, A or B, without explanation.")
ALLOWED_SAMPLE = {"sample_id", "instruction", "images", "input_hash"}
PROVENANCE_KEYS = ("protocol_id", "protocol_hash", "model_id", "model_version", "seed", "phase",
    "code_sha256", "software_environment_sha256", "environment_distribution_sha256", "data_manifest_sha256",
    "artifact_inventory_sha256", "model_artifacts_sha256", "configuration", "prompt_version")
REQUIRED_ARTIFACTS = {"src/model_runner.py", "src/build_requests.py", "configs/assets-v1.json",
    "configs/conditions-v1.json", "configs/request-templates-v1.jsonl", "configs/pilot-v1.json",
    "configs/reproduction-v1.json", "environment/requirements-lock.txt", "data/prepared-v1/manifest.json",
    "data/prepared-v1/inference/samples.jsonl", "data/prepared-v1/media-manifest.jsonl"}


def now(): return datetime.now(timezone.utc).isoformat()
def canonical(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def read_json(path): return json.loads(path.read_text(encoding="utf-8-sig"))


def read_rows(path):
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip(): yield json.loads(line)


def sha_file(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""): hasher.update(block)
    return hasher.hexdigest()


def safe_path(base, relative):
    path = (base / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(base.resolve()):
        raise ValueError("Manifest path escapes its root")
    return path


class EventJournal:
    """Stable recovery journal plus an optional invocation-specific monitor log."""
    def __init__(self, primary, mirror=None):
        self.primary = primary
        self.paths = [primary]
        if mirror is not None and mirror.resolve() != primary.resolve(): self.paths.append(mirror)


def append(path, item):
    if isinstance(path, EventJournal):
        for destination in path.paths: append(destination, item)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write((canonical(item) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())


class OutputLock:
    """Kernel-owned lock: a dead process releases it, independent of PID reuse."""
    def __init__(self, output):
        self.path = output.with_name(output.name + ".lock")
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.stream.write(b"\0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            self.stream = None
            raise RuntimeError("Another process owns this output") from exc
        return self

    def __exit__(self, *unused):
        if self.stream is not None:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()


def recover_jsonl(path):
    """Repair only a torn final append; preserve original bytes outside raw glob.

    Caller holds the owning run lock. Complete/interior malformed lines block.
    The immutable archive and recovery receipt precede replacing the active
    stream with its complete prefix; scientific records are never edited.
    """
    if isinstance(path, EventJournal): path = path.primary
    if not path.exists(): return []
    original = path.read_bytes()
    lines = original.splitlines(keepends=True)
    records, prefix, torn = [], [], False
    for index, line in enumerate(lines):
        if not line.strip():
            prefix.append(line)
            continue
        try:
            records.append(json.loads(line.decode("utf-8-sig")))
            prefix.append(line)
        except (ValueError, UnicodeError):
            if index != len(lines) - 1 or line.endswith((b"\n", b"\r")):
                raise RuntimeError(f"Corrupt complete/interior ledger: {path}:{index + 1}")
            torn = True
    if torn:
        original_hash = hashlib.sha256(original).hexdigest()
        folder = ROOT / "results/recovery"
        folder.mkdir(parents=True, exist_ok=True)
        archive = folder / (original_hash + ".bin")
        if archive.exists():
            if archive.read_bytes() != original: raise RuntimeError("Recovery archive collision")
        else:
            with archive.open("xb") as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
        complete = b"".join(prefix)
        if complete and not complete.endswith(b"\n"): complete += b"\n"
        replacement = path.with_name(path.name + f".repair-{os.getpid()}-{time.time_ns()}")
        with replacement.open("xb") as stream:
            stream.write(complete)
            stream.flush()
            os.fsync(stream.fileno())
        append(folder / "ledger.jsonl", {"event": "torn_tail_preserved", "timestamp": now(),
            "active_path": str(path), "original_sha256": original_hash, "archive": str(archive),
            "valid_records": len(records), "original_bytes": len(original)})
        os.replace(replacement, path)
    elif original and not original.endswith(b"\n"):
        with path.open("ab") as stream:
            stream.write(b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    return records


def verify_artifacts(protocol):
    hashes = protocol.get("artifact_hashes")
    if not isinstance(hashes, dict) or not REQUIRED_ARTIFACTS <= set(hashes):
        raise RuntimeError("Frozen protocol lacks required artifact hashes")
    for relative, expected in hashes.items():
        path = safe_path(ROOT, relative)
        if not path.is_file() or sha_file(path) != expected:
            raise RuntimeError(f"Frozen artifact hash mismatch: {relative}")
    return digest(hashes)


def verify_environment(lock):
    observed = {}
    for raw in lock.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"): continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", line)
        if match is None: raise RuntimeError(f"Environment lock requires name==version: {line}")
        name, expected = match.groups()
        actual = importlib.metadata.version(name)
        if actual != expected: raise RuntimeError(f"Installed environment drift: {name}")
        observed[re.sub(r"[-_.]+", "-", name).lower()] = actual
    if not observed: raise RuntimeError("Empty environment lock")
    return digest(observed)


def verify_model_assets(model_id, assets):
    entry = assets["models"][model_id]
    directory = ROOT / "models" / model_id
    summary_path = directory / "study-download-receipt.json"
    receipts = {}
    if summary_path.exists():
        summary = read_json(summary_path)
        if summary["revision"] != entry["revision"] or summary["repo"] != entry["repo"]:
            raise RuntimeError("Model receipt revision mismatch")
        receipts = {row["path"]: row for row in summary["files"]}
    required = {"config.json", "tokenizer_config.json", "tokenizer.json", "preprocessor_config.json"}
    index_path = directory / "model.safetensors.index.json"
    if index_path.exists():
        required.add(index_path.name)
        required.update(read_json(index_path)["weight_map"].values())
    else: required.add("model.safetensors")
    required.update(path.name for path in directory.iterdir() if path.is_file()
        and path.name in entry["files"] and path.suffix in {".json", ".jinja", ".txt"})
    observed = {}
    for name in sorted(required):
        info, path = entry["files"].get(name), safe_path(directory, name)
        if info is None or not path.is_file(): raise RuntimeError(f"Missing pinned model file: {name}")
        actual = sha_file(path)
        receipt = receipts.get(name)
        if receipt is None:
            receipt = read_json(path.with_name(path.name + ".receipt.json"))
            expected_url = f"https://huggingface.co/{entry['repo']}/resolve/{entry['revision']}/{name}"
            if receipt.get("url") != expected_url: raise RuntimeError(f"Model receipt revision mismatch: {name}")
        if receipt.get("sha256") != actual or receipt.get("bytes") != path.stat().st_size:
            raise RuntimeError(f"Model file differs from receipt: {name}")
        lfs = info.get("lfs", {})
        lfs_sha = lfs.get("sha256") or lfs.get("oid")
        if lfs_sha and actual != lfs_sha: raise RuntimeError(f"Model LFS hash mismatch: {name}")
        if name.endswith(".safetensors") and not lfs_sha:
            raise RuntimeError(f"Missing authoritative weight SHA256: {name}")
        if not lfs_sha and info.get("blobId"):
            contents = path.read_bytes()
            actual_blob = hashlib.sha1(f"blob {len(contents)}\0".encode() + contents).hexdigest()
            if actual_blob != info["blobId"]: raise RuntimeError(f"Model Git blob mismatch: {name}")
        observed[name] = actual
    return digest({"revision": entry["revision"], "files": observed})


def unique_map(rows, key):
    result = {}
    for row in rows:
        if row[key] in result: raise ValueError(f"Duplicate {key}")
        result[row[key]] = row
    return result


def validate_sample(sample):
    if set(sample) != ALLOWED_SAMPLE or not isinstance(sample["instruction"], str):
        raise ValueError("Inference sample schema permits forbidden fields")
    if digest({"instruction": sample["instruction"], "images": sample["images"]}) != sample["input_hash"]:
        raise ValueError("Inference sample input hash mismatch")
    sources = {}
    for image in sample["images"]:
        if set(image) != {"camera", "endpoint", "image_id"}: raise ValueError("Forbidden nested image fields")
        camera, endpoint = image["camera"], image["endpoint"]
        if not re.fullmatch(r"c[0-3]", camera) or endpoint not in {"before", "after"}:
            raise ValueError("Invalid neutral camera or endpoint")
        if not re.fullmatch(r"im_[0-9a-f]{32}", image["image_id"]): raise ValueError("Nonopaque image ID")
        if (camera, endpoint) in sources: raise ValueError("Duplicate camera/endpoint")
        sources[camera, endpoint] = image["image_id"]
    cameras = {camera for camera, _ in sources}
    if not cameras or any((camera, endpoint) not in sources for camera in cameras for endpoint in ("before", "after")):
        raise ValueError("Missing camera endpoint")
    return sources


def assemble_content(sample, condition, image_loader):
    sources = validate_sample(sample)
    if condition["ablation"] not in {"native", "central75"}: raise ValueError("Unknown preprocessing")
    content = [{"type": "text", "text": "Grasp subtask: " + sample["instruction"]}]
    serial = list(content)
    for position, camera in enumerate(condition["cameras"]):
        for endpoint in ("before", "after"):
            image_id = sources[camera, endpoint]
            description = {"type": "text", "text": f"Observation slot {position + 1}; camera {camera}; {endpoint.upper()}:"}
            content.extend([description, {"type": "image", "image": image_loader(image_id, condition["ablation"])}])
            serial.extend([description, {"type": "image", "image_id": image_id}])
    content.append({"type": "text", "text": QUESTION})
    serial.append({"type": "text", "text": QUESTION})
    return content, serial


def audit_continuations(tokenizer, prompt, prefix_ids, token_ids):
    if len(token_ids) != 2 or token_ids[0] == token_ids[1]: raise ValueError("Candidate tokens must be distinct")
    expanded = tokenizer.decode(prefix_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    for text, prefix in ((prompt, tokenizer.encode(prompt, add_special_tokens=False)), (expanded, prefix_ids)):
        if tokenizer.encode(text, add_special_tokens=False) != prefix: raise ValueError("Expanded prefix does not round-trip")
        for literal, token in zip(("A", "B"), token_ids):
            if tokenizer.decode([token]) != literal: raise ValueError("Literal decoding mismatch")
            if tokenizer.encode(text + literal, add_special_tokens=False) != prefix + [token]:
                raise ValueError("Literal continuation changes assistant-boundary tokenization")


def prepare_inputs(processor, sample, condition, image_loader, media_hashes):
    """CPU-only public preflight helper. Never loads weights or performs scoring."""
    content, serial = assemble_content(sample, condition, image_loader)
    messages = [{"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
                {"role": "user", "content": content}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False, enable_thinking=False)
    images = [entry["image"] for entry in content if entry["type"] == "image"]
    inputs = processor(text=[prompt], images=images, return_tensors="pt")
    prefix_ids = inputs["input_ids"][0].tolist()
    tokenizer = processor.tokenizer
    candidates = [tokenizer.encode(literal, add_special_tokens=False) for literal in ("A", "B")]
    if any(len(candidate) != 1 for candidate in candidates): raise ValueError("A/B must be single tokens")
    token_ids = [candidate[0] for candidate in candidates]
    audit_continuations(tokenizer, prompt, prefix_ids, token_ids)
    audit = {"messages": [{"role": "system", "text": SYSTEM_PROMPT}, {"role": "user", "content": serial}],
             "rendered_prompt": prompt, "token_ids": prefix_ids,
             "processor_tensor_shapes": {key: list(value.shape) for key, value in inputs.items()}}
    used_media = {entry["image_id"]: media_hashes[entry["image_id"]] for entry in serial if entry["type"] == "image"}
    return inputs, {"input": audit, "candidate_token_ids": token_ids,
        "payload_sha256": digest({"input": audit, "media": used_media, "ablation": condition["ablation"]})}


def normalized_score(a, b):
    if not all(math.isfinite(value) for value in (a, b)): raise FloatingPointError("Nonfinite model scores")
    difference = a - b
    return 1.0 / (1.0 + math.exp(-difference)) if difference >= 0 else math.exp(difference) / (1.0 + math.exp(difference))


class Scorer:
    def __init__(self, model_id, seed, prepared_dir=None):
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        import numpy as np
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        self.torch = torch
        self.prepared = Path(prepared_dir) if prepared_dir else ROOT / "data/prepared-v1"
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
        torch.set_num_threads(8)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(True, warn_only=True)
        path = ROOT / "models" / model_id
        self.processor = AutoProcessor.from_pretrained(path, local_files_only=True, trust_remote_code=False)
        self.model = AutoModelForImageTextToText.from_pretrained(path, local_files_only=True, trust_remote_code=False,
            torch_dtype=torch.bfloat16, device_map={"": "cuda:0"}, attn_implementation="sdpa").eval()
        candidates = [self.processor.tokenizer.encode(value, add_special_tokens=False) for value in ("A", "B")]
        if any(len(value) != 1 for value in candidates) or candidates[0] == candidates[1]:
            raise ValueError("PREFLIGHT_CONTRACT_FAILURE: literal A/B tokens are invalid")
        self.media = unique_map(read_rows(self.prepared / "media-manifest.jsonl"), "image_id")
        self.image_cache = {}

    def hardware(self):
        return {"gpu": self.torch.cuda.get_device_name(0), "cuda": self.torch.version.cuda, "torch": self.torch.__version__}

    def cleanup(self): self.torch.cuda.empty_cache()

    def image(self, image_id, ablation):
        from PIL import Image
        key = image_id, ablation
        if key not in self.image_cache:
            entry = self.media[image_id]
            contents = safe_path(self.prepared, entry["local_path"]).read_bytes()
            if hashlib.sha256(contents).hexdigest() != entry["sha256"]:
                raise ValueError("Media bytes differ from frozen manifest")
            with Image.open(io.BytesIO(contents)) as picture: result = picture.convert("RGB")
            if ablation == "central75":
                width, height = result.size
                cw, ch = max(1, math.floor(width * .75)), max(1, math.floor(height * .75))
                left, top = (width - cw) // 2, (height - ch) // 2
                result = result.crop((left, top, left + cw, top + ch)).resize((width, height), Image.Resampling.BICUBIC)
            elif ablation != "native": raise ValueError("Unknown preprocessing")
            if len(self.image_cache) >= 256: self.image_cache.clear()
            self.image_cache[key] = result
        return self.image_cache[key]

    def score(self, sample, condition, progress=lambda **unused: None):
        torch = self.torch
        progress(stage="preprocessing")
        inputs, audit = prepare_inputs(self.processor, sample, condition, self.image,
                                      {key: value["sha256"] for key, value in self.media.items()})
        prefix_ids, token_ids = audit["input"]["token_ids"], audit["candidate_token_ids"]
        image_token_id = getattr(self.model.config, "image_token_id", None)
        image_tokens = sum(token == image_token_id for token in prefix_ids)
        if image_token_id is None or image_tokens <= 0: raise ValueError("Expanded image token IDs are missing")
        progress(stage="host_to_device", input=audit["input"], payload_sha256=audit["payload_sha256"],
                 visual_tokens=image_tokens, total_input_tokens=len(prefix_ids))
        tensors = {key: (value.to("cuda:0", dtype=torch.bfloat16) if torch.is_floating_point(value)
                        else value.to("cuda:0")) for key, value in inputs.items()}
        torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
        progress(stage="model_forward", model_calls=1)
        started = time.perf_counter()
        with torch.inference_mode():
            output = self.model(**tensors, use_cache=False, logits_to_keep=1)
            logits = output.logits[0, -1, :].float()
            logprobs = torch.log_softmax(logits, dim=-1)
            selected, raw_logits = logprobs[token_ids].cpu().tolist(), logits[token_ids].cpu().tolist()
            top = torch.topk(logprobs, 5)
            top_ids, top_lp = top.indices.cpu().tolist(), top.values.cpu().tolist()
        torch.cuda.synchronize()
        progress(stage="score_normalization", gpu_scoring_runtime_s=time.perf_counter() - started,
                 peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated())
        if not all(math.isfinite(value) for value in selected + raw_logits + top_lp):
            progress(nonfinite_output_repr=repr({"selected": selected, "logits": raw_logits, "top": top_lp}))
            raise FloatingPointError("Nonfinite model output")
        a, b = selected
        result = {"logprob_success": a, "logprob_failure": b, "score_success": normalized_score(a, b),
            "raw_output": {"candidate_token_ids": token_ids, "candidate_literals": ["A", "B"],
                "candidate_logits": raw_logits, "candidate_logprobs": selected,
                "full_vocabulary_choice_mass": math.exp(a) + math.exp(b), "top_token_ids": top_ids,
                "top_token_text": [self.processor.tokenizer.decode([token]) for token in top_ids], "top_logprobs": top_lp},
            "parsed_output": {"label_by_candidate_argmax": "A" if a >= b else "B", "success_at_0_5": int(a >= b)},
            "scoring_contract": "two_literal_single_token_conditional_likelihood"}
        del output, logits, logprobs, tensors, inputs
        return result


def empty_measurements():
    return {"model_calls": 0, "visual_tokens": None, "total_input_tokens": None, "runtime_s": None,
        "gpu_scoring_runtime_s": None, "peak_gpu_allocated_bytes": None, "input": None, "payload_sha256": None,
        "raw_output": None, "parsed_output": None, "score_success": None, "logprob_success": None,
        "logprob_failure": None, "stage": "not_started"}


def canonical_costs(record):
    record = dict(record)
    record.update(calls=record.get("model_calls", 0), latency_seconds=record.get("runtime_s"),
                  peak_vram_bytes=record.get("peak_gpu_allocated_bytes"),
                  latency_measurement_status="measured" if record.get("runtime_s") is not None else "unknown_interrupted")
    return record


def failed_record(item, category, error, elapsed=None):
    result = {**empty_measurements(), **item}
    result.update(status=category, error=error, ended_at=now(), runtime_s=elapsed,
                  score_success=None, logprob_success=None, logprob_failure=None)
    return canonical_costs(result)


class AttemptGuard:
    """Serialize success/failure with a watchdog that persists TIMEOUT then exits."""
    def __init__(self, item, output, events, timeout_s=REQUEST_TIMEOUT_S, exit_fn=os._exit):
        self.item = {**empty_measurements(), **item}
        self.output, self.events, self.timeout_s, self.exit_fn = output, events, timeout_s, exit_fn
        self.lock, self.done, self.timer = threading.RLock(), False, None
        self.started = time.perf_counter()

    def start(self):
        append(self.events, {"event": "attempt_start", "timestamp": now(),
            "experiment_id": self.item["experiment_id"], "request_template_id": self.item["request_template_id"], "record": self.item})
        self.timer = threading.Timer(self.timeout_s, self.timeout)
        self.timer.daemon = True
        self.timer.start()

    def update(self, **fields):
        with self.lock:
            if self.done: return
            self.item.update(fields)
            append(self.events, {"event": "attempt_progress", "timestamp": now(),
                                "experiment_id": self.item["experiment_id"], "update": fields})

    def _persist(self, record):
        self.done = True
        append(self.output, record)
        append(self.events, {"event": "attempt_end", "timestamp": now(), "experiment_id": record["experiment_id"],
                            "request_template_id": record["request_template_id"], "status": record["status"]})

    def finish(self, result=None, category=None, error=None):
        with self.lock:
            if self.done: return None
            if self.timer: self.timer.cancel()
            elapsed = time.perf_counter() - self.started
            record = failed_record(self.item, category, error, elapsed) if category else {
                **self.item, **(result or {}), "status": "SUCCESS", "error": None, "ended_at": now(),
                "runtime_s": elapsed, "stage": "complete"}
            record = canonical_costs(record)
            self._persist(record)
            return record

    def timeout(self):
        with self.lock:
            if self.done: return
            record = failed_record(self.item, "TIMEOUT", {"type": "RequestDeadlineExceeded",
                "message": f"Frozen {self.timeout_s}s request deadline"}, time.perf_counter() - self.started)
            record["timeout_s"] = self.timeout_s
            try: self._persist(record)
            finally: self.exit_fn(124)


def validate_record(record, common, request_map):
    for key in PROVENANCE_KEYS:
        if record.get(key) != common[key]: raise RuntimeError(f"Resume provenance mismatch: {key}")
    request = request_map.get(record.get("request_template_id"))
    if request is None or any(record.get(key) != value for key, value in request.items()):
        raise RuntimeError("Resume request/input identity mismatch")
    expected = digest([common["phase"], common["model_id"], common["seed"], request["request_template_id"]])
    if record.get("experiment_id") != expected or record.get("attempt_index") != 0:
        raise RuntimeError("Resume attempt identity mismatch")


def reconcile(output, events, common, request_map):
    terminal = unique_map(recover_jsonl(output), "request_template_id")
    for record in terminal.values():
        validate_record(record, common, request_map)
        if record.get("status") in {None, "STARTED"}: raise RuntimeError("Nonterminal raw result")
    starts = {}
    for event in recover_jsonl(events):
        if event.get("event") == "run_open":
            if any(event.get(key) != common[key] for key in PROVENANCE_KEYS):
                raise RuntimeError("Resume event provenance mismatch")
            if event.get("raw_file") and Path(event["raw_file"]).resolve() != output.resolve():
                raise RuntimeError("Canonical run identity already belongs to a different raw output")
        elif event.get("event") == "attempt_start":
            record = dict(event["record"])
            validate_record(record, common, request_map)
            if event["experiment_id"] in starts: raise RuntimeError("Duplicate attempt START")
            starts[event["experiment_id"]] = record
        elif event.get("event") == "attempt_progress":
            if event["experiment_id"] not in starts: raise RuntimeError("Progress event lacks START")
            starts[event["experiment_id"]].update(event["update"])
    for record in starts.values():
        if record["request_template_id"] in terminal: continue
        recovered = failed_record(record, "INFRA_FAILURE", {"type": "InterruptedFirstAttempt",
            "message": "Prior durable START has no terminal result; not retried"})
        recovered.update(recovered_at=now(), runtime_unavailable_reason="Process interruption; exact end time unknown")
        append(output, recovered)
        append(events, {"event": "attempt_recovered", "timestamp": now(), "experiment_id": record["experiment_id"],
                        "request_template_id": record["request_template_id"], "status": "INFRA_FAILURE"})
        terminal[record["request_template_id"]] = recovered
    return terminal


def run(args):
    output = Path(args.output).resolve() if args.output else ROOT / "results/raw" / args.phase / f"{args.model}-seed{args.seed}.jsonl"
    identity = ROOT / "logs" / f"{args.phase}-{args.model}-seed{args.seed}"
    with OutputLock(ROOT / "results/gpu-execution"), OutputLock(identity), OutputLock(output):
        return run_locked(args, output)


def run_locked(args, output):
    default_protocol = ROOT / "configs/protocol-v1.json"
    protocol_path = Path(args.protocol) if getattr(args, "protocol", None) else default_protocol
    protocol = read_json(protocol_path)
    if protocol.get("frozen") is not True: raise RuntimeError("Protocol must be frozen before real scoring")
    if protocol_path.resolve() != default_protocol.resolve() and sha_file(protocol_path) != sha_file(default_protocol):
        raise RuntimeError("Protocol override differs from frozen protocol")
    timeout = protocol.get("runtime", {}).get("request_timeout_seconds", REQUEST_TIMEOUT_S)
    if timeout != REQUEST_TIMEOUT_S: raise RuntimeError("Request timeout differs from runner contract")
    inventory_hash = verify_artifacts(protocol)
    prepared = Path(args.prepared_dir) if getattr(args, "prepared_dir", None) else ROOT / "data/prepared-v1"
    request_path = Path(args.requests) if getattr(args, "requests", None) else ROOT / "configs/request-templates-v1.jsonl"
    if getattr(args, "prepared_dir", None) or getattr(args, "requests", None):
        if args.phase != "reproduction": raise ValueError("Input-root overrides are reproduction-only")
        for relative in ("manifest.json", "inference/samples.jsonl", "media-manifest.jsonl"):
            if sha_file(prepared / relative) != sha_file(ROOT / "data/prepared-v1" / relative):
                raise RuntimeError("Rebuilt reproduction input differs from frozen input")
        if sha_file(request_path) != sha_file(ROOT / "configs/request-templates-v1.jsonl"):
            raise RuntimeError("Reproduction request registry differs")
    conditions = unique_map(read_json(ROOT / "configs/conditions-v1.json"), "condition_id")
    samples = unique_map(read_rows(prepared / "inference/samples.jsonl"), "sample_id")
    sources = {key: validate_sample(value) for key, value in samples.items()}
    all_requests = list(read_rows(request_path))
    unique_map(all_requests, "request_template_id")
    for request in all_requests:
        if set(request) != {"sample_id", "condition_id", "input_hash", "dataset", "split", "request_template_id"}:
            raise ValueError("Request schema contains forbidden fields")
        sample, condition = samples[request["sample_id"]], conditions[request["condition_id"]]
        if request["input_hash"] != sample["input_hash"]: raise ValueError("Request points to changed input")
        if any((camera, endpoint) not in sources[request["sample_id"]]
               for camera in condition["cameras"] for endpoint in ("before", "after")):
            raise ValueError("Request camera endpoint is unavailable")
    if args.seed not in (17, 29, 43) or args.model not in ("qwen3vl4b", "internvl35_4b"):
        raise ValueError("Model or seed outside frozen study")
    if args.phase in ("pilot", "reproduction"):
        selection = read_json(ROOT / f"configs/{args.phase}-v1.json")
        if args.seed not in selection["seeds"] or args.model not in selection["models"] or args.split:
            raise ValueError("Phase model/seed/split outside frozen selection")
        phase_requests = [row for row in all_requests if row["sample_id"] in selection["sample_ids"]
                          and row["condition_id"] in selection["condition_ids"]]
    elif args.phase == "main": phase_requests = all_requests
    else: raise ValueError("Unknown phase")
    request_map = {row["request_template_id"]: row for row in phase_requests}
    requests = [row for row in phase_requests if not args.split or row["split"] == args.split]
    requests.sort(key=lambda row: digest([args.seed, row["request_template_id"]]))
    selected_ids = {row["request_template_id"] for row in requests}
    assets, env = read_json(ROOT / "configs/assets-v1.json"), ROOT / "environment/requirements-lock.txt"
    common = {"protocol_id": protocol["protocol_id"], "protocol_hash": sha_file(protocol_path),
        "model_id": args.model, "model_version": assets["models"][args.model]["revision"],
        "seed": args.seed, "phase": args.phase, "python": sys.executable, "code_sha256": sha_file(Path(__file__)),
        "software_environment_sha256": sha_file(env), "environment_distribution_sha256": verify_environment(env),
        "data_manifest_sha256": sha_file(ROOT / "data/prepared-v1/manifest.json"),
        "artifact_inventory_sha256": inventory_hash, "model_artifacts_sha256": verify_model_assets(args.model, assets),
        "attempt_index": 0, "configuration": {"temperature": None, "decoding": "conditional_likelihood_no_sampling",
            "dtype": "bfloat16", "attention": "sdpa", "batch_size": 1, "request_timeout_s": REQUEST_TIMEOUT_S},
        "git_commit": protocol.get("git_commit", "UNVERSIONED_HASH_MANIFEST"), "prompt_version": "grasp-label-v1"}
    primary_events = ROOT / "logs" / f"{args.phase}-{args.model}-seed{args.seed}-events.jsonl"
    mirror_events = Path(args.events).resolve() if getattr(args, "events", None) else None
    events = EventJournal(primary_events, mirror_events)
    if any(path.resolve() == output.resolve() for path in events.paths):
        raise ValueError("Event journal cannot share the scientific raw output")
    existing = reconcile(output, events, common, request_map)
    needed = [row for row in requests if row["request_template_id"] not in existing]
    accounted = len(selected_ids & set(existing))
    append(events, {"event": "run_open", "timestamp": now(), "planned": len(requests), "already_accounted": accounted,
        "split": args.split, "pid": os.getpid(), "prepared_dir": str(prepared), "request_path": str(request_path),
        "raw_file": str(output.resolve()), **common})
    scorer = None
    try:
        if needed:
            append(events, {"event": "model_load_start", "timestamp": now(), **common})
            scorer = Scorer(args.model, args.seed, prepared_dir=prepared)
            common["hardware"] = scorer.hardware()
            append(events, {"event": "model_load_complete", "timestamp": now(), "hardware": common["hardware"]})
            append(events, {"event": "MODEL_READY", "timestamp": now(), "pid": os.getpid(),
                            "model_id": args.model, "phase": args.phase, "seed": args.seed})
        for request in needed:
            item = {**common, **request, "experiment_id": digest([args.phase, args.model, args.seed, request["request_template_id"]]),
                    "started_at": now(), "status": "STARTED"}
            guard = AttemptGuard(item, output, events, timeout_s=timeout)
            guard.start()
            try:
                result = scorer.score(samples[request["sample_id"]], conditions[request["condition_id"]], progress=guard.update)
            except Exception as exc:
                oom = getattr(getattr(getattr(scorer, "torch", None), "cuda", None), "OutOfMemoryError", ())
                category = "OOM" if isinstance(exc, oom) else "MODEL_FAILURE" if isinstance(exc, FloatingPointError) else (
                    "INFRA_FAILURE" if isinstance(exc, (FileNotFoundError, OSError)) else "EXECUTION_FAILURE")
                guard.finish(category=category, error={"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
                try: scorer.cleanup()
                except Exception as cleanup_error:
                    append(events, {"event": "cleanup_error", "timestamp": now(), "error": repr(cleanup_error)})
            except BaseException:
                if guard.timer: guard.timer.cancel()
                raise
            else: guard.finish(result=result)
            accounted += 1
            if accounted % 20 == 0:
                print(json.dumps({"phase": args.phase, "model": args.model, "seed": args.seed,
                                  "accounted": accounted, "planned": len(requests)}), flush=True)
    except BaseException as exc:
        append(events, {"event": "run_error", "timestamp": now(), "error": repr(exc)})
        raise
    finally:
        append(events, {"event": "run_close", "timestamp": now(), "raw_file": str(output), "split": args.split})
    append(events, {"event": "run_complete", "timestamp": now(), "accounted": accounted,
                   "planned": len(requests), "new_attempts": len(needed), "split": args.split})
    return {"accounted": accounted, "planned": len(requests), "new_attempts": len(needed)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=["qwen3vl4b", "internvl35_4b"])
    parser.add_argument("--seed", required=True, type=int, choices=[17, 29, 43])
    parser.add_argument("--phase", required=True, choices=["pilot", "main", "reproduction"])
    parser.add_argument("--split", choices=["dev", "confirmation", "external"])
    parser.add_argument("--output")
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--prepared-dir", type=Path)
    parser.add_argument("--requests", type=Path)
    parser.add_argument("--events", type=Path)
    run(parser.parse_args())


if __name__ == "__main__": main()
