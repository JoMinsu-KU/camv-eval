"""Unchanged function-source copies with recorded lineage. No module import side effects."""
import math
import numpy as np
TARGET=.9
TOL=1e-12

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

def require(ok, message):
    if not ok: raise ValueError(message)

def centered_p(point, draws, B=2000):
    draws = np.asarray(draws, dtype=np.float64)
    require(draws.shape == (B,), 'Exact frozen bootstrap census required')
    finite = draws[np.isfinite(draws)]
    if len(finite) < math.ceil(.95 * B) or not np.isfinite(point): return math.nan
    return (1 + int(np.sum(np.abs(finite - point) >= abs(point)))) / (len(finite) + 1)
