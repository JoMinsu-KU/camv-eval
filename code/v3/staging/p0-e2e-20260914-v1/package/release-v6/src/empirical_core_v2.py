"""CAMV empirical calibration and evaluation primitives, separate from inference.

Historical inputs are read-only. New outputs are written only by orchestration.
All calibration consumes development cohorts; evaluation labels never select a policy.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict
import csv
import gzip
import itertools
import json
import math
import numpy as np

TARGET = .9
TOL = 1e-12
COSTS = ('calls', 'latency_seconds', 'visual_tokens', 'peak_vram_bytes')
BASES = ('single', 'joint', 'late', 'symmetric', 'reverse')

def sigmoid(x):
    return np.exp(-np.logaddexp(0., -np.asarray(x, dtype=np.float64)))

def clean(value):
    if isinstance(value, np.ndarray): return clean(value.tolist())
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(x) for x in value]
    if isinstance(value, float) and not math.isfinite(value): return None
    return value

@dataclass
class Pool:
    scores: np.ndarray
    available: np.ndarray
    columns: tuple
    logodds: np.ndarray
    costs: dict

    def select(self, columns):
        indices = [self.columns.index(c) for c in columns]
        return Pool(self.scores[:, indices], self.available[:, indices], tuple(columns),
                    self.logodds[:, indices], {k:v[:, indices] for k,v in self.costs.items()})

@dataclass
class Cohort:
    model: str
    dataset: str
    split: str
    seed: int
    samples: tuple
    groups: tuple
    group_index: np.ndarray
    tasks: np.ndarray
    y: np.ndarray
    cameras: tuple
    pairs: tuple
    pools: dict

    def sample_weights(self, multiplicity=None, weighting='sample'):
        w = np.ones(len(self.samples), dtype=np.float64)
        if multiplicity is not None:
            w *= np.asarray(multiplicity, dtype=np.float64)[self.group_index]
        if weighting == 'group':
            w /= np.bincount(self.group_index)[self.group_index]
        elif weighting not in ('sample', 'task_macro'):
            raise ValueError(weighting)
        return w

def threshold(scores, y, weights, available):
    scores = np.asarray(scores, dtype=np.float64)
    shape = scores.shape
    labels = np.broadcast_to(np.asarray(y)[:, None], shape)
    weights = np.broadcast_to(np.asarray(weights)[:, None] / shape[1], shape)
    total = float(weights[labels == 1].sum())
    result = {'threshold': math.nan, 'status': 'NO_DEV_SUCCESSES',
              'positive_weight': total, 'achieved_recall': math.nan}
    if total <= 0: return result
    valid = available & np.isfinite(scores) & (labels == 1) & (weights > 0)
    maximum = float(weights[valid].sum()/total)
    result['maximum_recall'] = maximum
    if not valid.any():
        result['status'] = 'NO_AVAILABLE_DEV_SUCCESSES'
        return result
    if maximum + TOL < TARGET:
        result['status'] = 'TARGET_UNATTAINABLE'
        return result
    s, w = scores[valid], weights[valid]
    order = np.argsort(-s, kind='stable')
    s, w = s[order], w[order]
    ends = np.r_[np.flatnonzero(s[:-1] != s[1:]), len(s)-1]
    recall = np.cumsum(w)[ends] / total
    index = np.flatnonzero(recall + TOL >= TARGET)[0]
    value = float(s[ends[index]])
    result.update(threshold=value, status='OK',
                  achieved_recall=float(weights[valid & (scores >= value)].sum()/total))
    return result

def rates(cohort, predictions, multiplicity=None, weighting='sample'):
    """Per-sample pair decisions are averaged, preserving one total sample weight."""
    accepted = np.asarray(predictions, dtype=np.float64).mean(axis=1)
    weights = cohort.sample_weights(multiplicity, weighting)
    values = []
    for label in (0, 1):
        use = cohort.y == label
        if weighting == 'task_macro':
            task_values = []
            for task in sorted(set(cohort.tasks)):
                select = use & (cohort.tasks == task)
                denom = float(weights[select].sum())
                if denom > 0:
                    task_values.append(float(np.dot(weights[select], accepted[select])/denom))
            values.append(float(np.mean(task_values)) if task_values else math.nan)
        else:
            denom = float(weights[use].sum())
            values.append(float(np.dot(weights[use], accepted[use])/denom) if denom > 0 else math.nan)
    return np.asarray(values)

def fit(dev, multiplicity=None, frozen_pooled=None):
    """Fit all source columns, even if the target has fewer cameras/pairs."""
    weights = dev.sample_weights(multiplicity)
    fitted = {}
    for base in BASES:
        pool = dev.pools[base]
        pooled = threshold(pool.scores, dev.y, weights, pool.available)
        if frozen_pooled is not None and base in frozen_pooled:
            pooled['recomputed_threshold'] = pooled['threshold']
            pooled['threshold'] = float(frozen_pooled[base])
            pooled['source'] = 'historical_frozen_pooled_point'
        columns = {}
        for col in pool.columns:
            p = pool.select([col])
            record = threshold(p.scores, dev.y, weights, p.available)
            metric = rates(dev, p.available & (p.scores >= record['threshold']), multiplicity)
            record.update(false_success_rate=float(metric[0]), success_recall=float(metric[1]))
            columns[col] = record
        fitted[base] = {'pooled': pooled, 'columns': columns}
    return fitted

def choose_camera(fitted, allowed):
    values = fitted['single']['columns']
    eligible = [(values[c]['false_success_rate'], -values[c]['success_recall'], c)
                for c in allowed if c in values and
                all(np.isfinite(values[c][key]) for key in ('threshold','false_success_rate','success_recall'))]
    return min(eligible)[2] if eligible else None

def policies(cohort, fitted):
    """Map source-fitted policies to target slots without consulting target outcomes."""
    out = {}
    for base in ('joint', 'late', 'symmetric'):
        p = cohort.pools[base]
        out[base+'_pooled'] = (p, fitted[base]['pooled']['threshold'], None)
        out[base+'_pair'] = (p, np.array([fitted[base]['columns'][c]['threshold'] for c in p.columns]), None)
    rev = cohort.pools['reverse']
    for source, label in (('joint','forward_threshold'), ('reverse','recalibrated')):
        out['reverse_'+label+'_pooled'] = (rev, fitted[source]['pooled']['threshold'], None)
        out['reverse_'+label+'_pair'] = (rev, np.array([fitted[source]['columns'][c]['threshold'] for c in rev.columns]), None)
    p = cohort.pools['single']
    out['single_pooled_average'] = (p, fitted['single']['pooled']['threshold'], None)
    out['single_calibrated_average'] = (p, np.array([fitted['single']['columns'][c]['threshold'] for c in p.columns]), None)
    for camera in cohort.cameras:
        out['single_calibrated_'+camera] = (p.select([camera]), fitted['single']['columns'][camera]['threshold'], camera)
    best = choose_camera(fitted, cohort.cameras)
    out['best_calibrated'] = (p.select([best or cohort.cameras[0]]),
         fitted['single']['columns'][best]['threshold'] if best else math.nan, best)
    selected = [choose_camera(fitted, pair.split('_')) for pair in cohort.pairs]
    indices = [p.columns.index(c) if c else 0 for c in selected]
    pair_pool = Pool(p.scores[:,indices], p.available[:,indices], cohort.pairs,
                    p.logodds[:,indices], {k:v[:,indices] for k,v in p.costs.items()})
    thresholds = np.array([fitted['single']['columns'][c]['threshold'] if c else math.nan for c in selected])
    out['pair_best_calibrated'] = (pair_pool, thresholds, selected)
    return out

def policy_metrics(cohort, policy, weighting='sample'):
    pool, thresholds, selected = policy
    available = pool.available & np.isfinite(thresholds)
    pred = available & (pool.scores >= thresholds)
    fsr, recall = rates(cohort, pred, weighting=weighting)
    coverage = float(np.mean(available))
    lower = rates(cohort, pred, weighting=weighting)
    upper = rates(cohort, pred | ~available, weighting=weighting)
    out = {'false_success_rate':fsr, 'success_recall':recall,
           'fit_available':bool(np.isfinite(thresholds).all()),
           'weighting':weighting, 'coverage_sample_pair':coverage,
           'fsr_lower':lower[0], 'fsr_upper':upper[0],
           'recall_lower':lower[1], 'recall_upper':upper[1],
           'n_samples':len(cohort.samples), 'n_groups':len(cohort.groups),
           'n_success':int(cohort.y.sum()), 'n_failure':int((1-cohort.y).sum()),
           'n_conditions':len(pool.columns), 'n_unavailable':int((~available).sum()),
           'selected_camera':selected, 'thresholds':thresholds,
           'target_recall_gap':recall-TARGET}
    if weighting == 'sample':
        mean_pred = pred.mean(axis=1)
        tp = float(np.dot(cohort.y, mean_pred)); fp = float(np.dot(1-cohort.y, mean_pred))
        tn = float((1-cohort.y).sum()-fp); positives = float(cohort.y.sum())
        out.update(accuracy=(tp+tn)/len(cohort.y),
                   precision=tp/(tp+fp) if tp+fp else math.nan,
                   f1=2*tp/(tp+fp+positives) if tp+fp+positives else math.nan)
        for label, name in ((0,'false_success_rate'), (1,'success_recall')):
            use = cohort.y == label
            denom = int(available[use].sum())
            out['valid_only_'+name] = float(pred[use].sum()/denom) if denom else math.nan
    for cost in COSTS:
        values = pool.costs[cost]
        finite = np.isfinite(values)
        out['cost_'+cost+'_mean'] = float(values[finite].mean()) if finite.any() else math.nan
        out['cost_'+cost+'_max'] = float(values[finite].max()) if finite.any() else math.nan
        out['cost_'+cost+'_coverage'] = float(finite.mean())
    return out

def prediction_matrix(cohort, fitted, names=None):
    p = policies(cohort,fitted)
    names = list(p) if names is None else names
    accepted = np.empty((len(names),len(cohort.samples)))
    for i,name in enumerate(names):
        pool,t,_ = p[name]
        accepted[i] = ((pool.available & np.isfinite(t)) & (pool.scores>=t)).mean(axis=1)
        if not np.isfinite(t).all(): accepted[i] = np.nan
    return names,accepted

def matrix_rates(cohort, accepted, multiplicities, weighting='sample'):
    """Vectorized evaluation of fixed policies over a batch of group draws."""
    multiplicities = np.atleast_2d(multiplicities)
    weights = multiplicities[:,cohort.group_index].astype(np.float64)
    if weighting=='group': weights /= np.bincount(cohort.group_index)[cohort.group_index]
    output = np.full((len(weights),len(accepted),2),np.nan)
    for label in (0,1):
        if weighting=='task_macro':
            parts = []
            for task in sorted(set(cohort.tasks)):
                select = (cohort.y==label)&(cohort.tasks==task)
                w = weights[:,select]; denominator = w.sum(axis=1)
                with np.errstate(divide='ignore',invalid='ignore'):
                    parts.append((w @ accepted[:,select].T)/denominator[:,None])
            stacked = np.stack(parts)
            valid = np.isfinite(stacked)
            count = valid.sum(axis=0)
            with np.errstate(divide='ignore',invalid='ignore'):
                output[:,:,label] = np.nansum(stacked,axis=0)/count
        else:
            select = cohort.y==label; w=weights[:,select]; denominator=w.sum(axis=1)
            with np.errstate(divide='ignore',invalid='ignore'):
                output[:,:,label] = (w @ accepted[:,select].T)/denominator[:,None]
    return output

def build_cohorts(rows):
    buckets = defaultdict(list)
    for row in rows:
        if row['method_id'] in ('single', 'joint', 'late_meanlogodds'):
            buckets[(row['model_id'],row['dataset'],row['split'],int(row['seed']))].append(row)
    result = {}
    for key, records in sorted(buckets.items()):
        meta = {r['sample_id']:r for r in records}
        samples = tuple(sorted(meta)); sample_index = {s:i for i,s in enumerate(samples)}
        groups = tuple(sorted({r['group_id'] for r in records})); group_index = {g:i for i,g in enumerate(groups)}
        cameras = tuple(sorted({r['cameras'][0] for r in records if r['method_id']=='single'}))
        pairs = tuple('_'.join(p) for p in itertools.combinations(cameras,2))
        pools = {}
        for base in ('single', 'joint', 'reverse'):
            columns = cameras if base=='single' else pairs
            shape = (len(samples),len(columns)); present = np.zeros(shape,bool)
            scores = np.full(shape,np.nan); logodds = np.full(shape,np.nan)
            available = np.zeros(shape,bool); costs = {c:np.full(shape,np.nan) for c in COSTS}
            for r in records:
                if r['method_id'] not in ('single','joint'): continue
                if r['method_id']=='single':
                    if base!='single': continue
                    column = r['cameras'][0]
                else:
                    forward = list(r['cameras']) == sorted(r['cameras'])
                    if base=='single' or forward != (base=='joint'): continue
                    column = '_'.join(sorted(r['cameras']))
                i,j = sample_index[r['sample_id']],columns.index(column)
                if present[i,j]: raise ValueError(('duplicate',key,base,i,j))
                present[i,j] = True
                score = r.get('score'); odds = r.get('logodds')
                scores[i,j] = float(score) if score is not None else np.nan
                logodds[i,j] = float(odds) if odds is not None else np.nan
                available[i,j] = bool(r.get('available',False)) and np.isfinite(scores[i,j])
                for cost in COSTS:
                    value = r.get(cost)
                    costs[cost][i,j] = float(value) if value is not None else np.nan
            if not present.all(): raise ValueError(('routing holes',key,base,int((~present).sum())))
            pools[base] = Pool(scores,available,columns,logodds,costs)
        single = pools['single']; fwd = pools['joint']; rev = pools['reverse']
        left = [cameras.index(p.split('_')[0]) for p in pairs]
        right = [cameras.index(p.split('_')[1]) for p in pairs]
        odds = (single.logodds[:,left]+single.logodds[:,right])/2
        costs = {c:(np.maximum(single.costs[c][:,left],single.costs[c][:,right])
                    if c=='peak_vram_bytes' else single.costs[c][:,left]+single.costs[c][:,right]) for c in COSTS}
        pools['late'] = Pool(sigmoid(odds),single.available[:,left]&single.available[:,right]&np.isfinite(odds),pairs,odds,costs)
        # Historical frozen Late scores must remain byte-value identical. Recomputing
        # an algebraically identical sigmoid can change one ULP at a fixed threshold.
        # New prospective rows contain no derived Late records and use the formula above.
        saved_late = [r for r in records if r['method_id']=='late_meanlogodds']
        if saved_late:
            p = pools['late']; seen = np.zeros(p.scores.shape,bool)
            for r in saved_late:
                i=sample_index[r['sample_id']];j=pairs.index('_'.join(sorted(r['cameras'])))
                if seen[i,j]: raise ValueError(('duplicate historical Late',key,i,j))
                seen[i,j]=True
                value=r.get('score');stored_odds=r.get('logodds')
                if value is not None:
                    if not np.isclose(p.scores[i,j],value,rtol=0,atol=1e-12):
                        raise ValueError(('historical Late derivation disagreement',key,i,j))
                if stored_odds is not None:
                    if not np.isclose(p.logodds[i,j],stored_odds,rtol=0,atol=1e-12):
                        raise ValueError(('historical Late logodds disagreement',key,i,j))
                p.scores[i,j]=float(value) if value is not None else np.nan
                p.logodds[i,j]=float(stored_odds) if stored_odds is not None else np.nan
                p.available[i,j]=bool(r.get('available')) and np.isfinite(p.scores[i,j])
                for cost in COSTS:
                    v=r.get(cost);p.costs[cost][i,j]=float(v) if v is not None else np.nan
            if not seen.all(): raise ValueError(('incomplete stored Late',key))
        odds = (fwd.logodds+rev.logodds)/2
        costs = {c:(np.maximum(fwd.costs[c],rev.costs[c]) if c=='peak_vram_bytes' else fwd.costs[c]+rev.costs[c]) for c in COSTS}
        pools['symmetric'] = Pool(sigmoid(odds),fwd.available&rev.available&np.isfinite(odds),pairs,odds,costs)
        result[key] = Cohort(*key,samples,groups,np.array([group_index[meta[s]['group_id']] for s in samples]),
                            np.array([meta[s]['task_family'] for s in samples]),
                            np.array([meta[s]['label'] for s in samples],dtype=int),cameras,pairs,pools)
    return result

def historical_rows(path, excluded_groups=()):
    excluded = set(excluded_groups)
    with gzip.open(path,'rt',encoding='utf-8',newline='') as stream:
        for cells in csv.DictReader(stream):
            row = {key:json.loads(value) for key,value in cells.items() if value != r'\M'}
            if row['group_id'] in excluded: continue
            assert row['seed']==17 and row['ablation']=='native'
            yield row

def prospective_rows(raw_paths, metadata_path):
    with Path(metadata_path).open(encoding='utf-8-sig') as stream:
        metadata = {r['sample_id']:r for r in map(json.loads,stream)}
    for path in raw_paths:
        with Path(path).open(encoding='utf-8-sig') as stream:
            for row in map(json.loads,stream):
                if row.get('phase') != 'main': continue
                m = metadata[row['sample_id']]
                yield dict(row, dataset=m['dataset'],split=m['split'],group_id=m['group_id'],
                           label=m['label'],task_family=m['task_family'])

def contrast_arrays(method_names, values):
    v = {name:values[...,i,:] for i,name in enumerate(method_names)}
    result = {
        'joint_pooled_minus_late_pooled':v['joint_pooled']-v['late_pooled'],
        'joint_pair_minus_late_pair':v['joint_pair']-v['late_pair'],
        'joint_pair_minus_joint_pooled':v['joint_pair']-v['joint_pooled'],
        'late_pair_minus_late_pooled':v['late_pair']-v['late_pooled'],
        'interaction':(v['joint_pair']-v['late_pair'])-(v['joint_pooled']-v['late_pooled'])}
    for a,b in (('joint_pair','pair_best_calibrated'),('late_pair','pair_best_calibrated'),
                ('joint_pooled','best_calibrated'),('late_pooled','best_calibrated'),
                ('joint_pooled','symmetric_pooled'),('joint_pair','symmetric_pair')):
        result[a+'_minus_'+b] = v[a]-v[b]
    return result

def interval(values, point=None, basic=False):
    values = np.asarray(values,dtype=np.float64)
    valid = np.isfinite(values)
    if valid.sum() < math.ceil(.95*len(values)):
        return np.array([np.nan,np.nan])
    q = np.quantile(values[valid],[.025,.975],method='linear')
    return 2*point-q[::-1] if basic else q

def holm(pvalues):
    keys = list(pvalues)
    order = sorted(range(len(keys)),key=lambda i:pvalues[keys[i]] if np.isfinite(pvalues[keys[i]]) else math.inf)
    output = {}; previous = 0.
    for rank,i in enumerate(order):
        p = pvalues[keys[i]]
        if not np.isfinite(p): output[keys[i]]=math.nan; continue
        previous = max(previous,min(1.,p*(len(keys)-rank)))
        output[keys[i]] = previous
    return output

def decision(fsr_ci, recall_ci, margin=0.):
    if not np.isfinite([*fsr_ci,*recall_ci]).all(): return 'unavailable'
    if fsr_ci[1] < 0 and recall_ci[0] >= -margin: return 'A_advantage'
    if fsr_ci[0] > 0 and recall_ci[1] <= margin: return 'B_advantage'
    if (fsr_ci[1] < 0 and recall_ci[1] < -margin) or (fsr_ci[0] > 0 and recall_ci[0] > margin):
        return 'tradeoff'
    return 'inconclusive'
