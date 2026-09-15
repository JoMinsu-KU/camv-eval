"""Three shared-camera pairs; frozen-policy interaction and bootstrap primitives.

No experiment is dispatched by import. All stochastic operations require an
explicit SeedSequence namespace. The null is a vector-law exchangeability null.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from scipy.special import ndtr
from scipy.stats import t as student_t
from frozen_primitives_v1 import threshold, interval, centered_p, holm

PAIRS = ((0, 1), (0, 2), (1, 2))
POLICIES = ('joint_pooled', 'joint_pair', 'late_pooled', 'late_pair')
METRICS = ('false_success_rate', 'success_recall')
CONTRASTS = ('joint_pooled_minus_late_pooled', 'joint_pair_minus_late_pair',
             'joint_pair_minus_joint_pooled', 'late_pair_minus_late_pooled', 'interaction')
ALGORITHMS = ('conditional_percentile', 'refit_percentile', 'refit_basic', 'cluster_sandwich_t')
A = np.array([[.5, .5, 0], [.5, 0, .5], [0, .5, .5]], dtype=np.float64)
SIGMA = .5 * np.eye(3) + .5 * np.ones((3, 3))
CHOLESKY = np.linalg.cholesky(SIGMA)
PAIR_COV = A @ SIGMA @ A.T
PAIR_SD = np.sqrt(np.diag(PAIR_COV))
RNG_ROOT = 20260914

@dataclass
class Data:
    y: np.ndarray
    cameras: np.ndarray
    joint: np.ndarray

    @property
    def late(self): return self.cameras @ A.T
    @property
    def groups(self): return self.y.shape[0]
    @property
    def valid_calibration(self):
        return bool(np.any(self.y == 0) and np.any(self.y == 1)
                    and np.isfinite(self.cameras).all() and np.isfinite(self.joint).all())

def generator(scenario, groups, namespace, target=False):
    rng = np.random.default_rng(np.random.SeedSequence(namespace))
    m = 3
    prevalence = rng.beta(2., 3., size=groups)
    y = (rng.random((groups, m)) < prevalence[:, None]).astype(np.int8)
    rho = float(scenario['rho'])
    # Conditional on the shared labels the two full camera arrays are iid.
    replicas = []
    for _ in range(2):
        h = rng.standard_normal((groups, 3)) @ CHOLESKY.T
        e = rng.standard_normal((groups, m, 3)) @ CHOLESKY.T
        replicas.append(1.5 * y[..., None] + math.sqrt(rho) * h[:, None, :]
                        + math.sqrt(1. - rho) * e)
    if target:
        shift = np.asarray(scenario['common_target_shift'])[y] * PAIR_SD[0]
        # Apply the common shift before pair averaging in BOTH replicas, so
        # the null uses the same floating-point transformation as well as the
        # same mathematical vector law (including shifted condition N04).
        replicas = [camera + shift[..., None] for camera in replicas]
    cameras = replicas[0]
    joint = replicas[1] @ A.T + np.asarray(scenario['joint_pair_offsets'])
    if target:
        joint = joint + y[..., None] * float(scenario['joint_success_target_shift']) * PAIR_SD
    return Data(y, cameras, joint)

def contrasts(v):
    jp, jr, lp, lr = (v[..., i, :] for i in range(4))
    return np.stack((jp-lp, jr-lr, jr-jp, lr-lp, (jr-lr)-(jp-lp)), axis=-2)

class CalibrationPlan:
    """Pre-sort each native threshold pool once; weighted knots match threshold()."""
    def __init__(self, dev):
        self.groups = dev.groups
        self.positive = dev.y.sum(axis=1, dtype=np.int64)
        self.negative = (1-dev.y).sum(axis=1, dtype=np.int64)
        labels = dev.y.reshape(-1)
        gids = np.repeat(np.arange(dev.groups), dev.y.shape[1])
        self.entries = []
        for scores in (dev.joint.reshape(-1, 3), dev.late.reshape(-1, 3)):
            for chosen in (scores, scores[:, [0]], scores[:, [1]], scores[:, [2]]):
                p = chosen.shape[1]
                values = chosen[labels == 1].reshape(-1)
                g = np.repeat(gids[labels == 1], p)
                order = np.argsort(-values, kind='stable')
                v, g = values[order], g[order]
                ends = np.r_[np.flatnonzero(v[:-1] != v[1:]), len(v)-1] if len(v) else np.array([], int)
                self.entries.append((v, g, ends, p))

    def fit(self, multiplicity):
        w = np.atleast_2d(np.asarray(multiplicity, dtype=np.int64))
        if w.shape[1] != self.groups or np.any(w < 0): raise ValueError('Invalid dev multiplicity')
        pos, neg = w @ self.positive, w @ self.negative
        valid = (pos > 0) & (neg > 0)
        out = np.full((len(w), 8), np.nan)
        for k, (values, groups, ends, p) in enumerate(self.entries):
            if not len(values): continue
            # Zero-weight rows cannot create a knot: select the first weighted
            # cumulative crossing, which is always an included positive score.
            cumulative = np.cumsum(w[:, groups] / p, axis=1)[:, ends]
            with np.errstate(divide='ignore', invalid='ignore'):
                attained = cumulative / pos[:, None] + 1e-12 >= .9
            ok = valid & attained.any(axis=1)
            index = np.argmax(attained, axis=1)
            out[ok, k] = values[ends[index[ok]]]
        return out

def policy_thresholds(fits):
    fits = np.atleast_2d(fits)
    return np.stack((np.repeat(fits[:, [0]], 3, axis=1), fits[:, 1:4],
                     np.repeat(fits[:, [4]], 3, axis=1), fits[:, 5:8]), axis=1)

def predictions(data, fits):
    score = np.stack((data.joint, data.joint, data.late, data.late), axis=-2).reshape(-1, 4, 3)
    ts = policy_thresholds(fits)
    return score[None, ...] >= ts[:, None, :, :]

def weighted_rates(data, fits, multiplicity):
    fits = np.atleast_2d(fits)
    w = np.atleast_2d(np.asarray(multiplicity, dtype=np.int64))
    if w.shape[1] != data.groups or np.any(w < 0): raise ValueError('Invalid eval multiplicity')
    if len(fits) not in (1, len(w)): raise ValueError('Fit/draw axis mismatch')
    accepted = predictions(data, fits).mean(axis=-1)
    y = data.y.reshape(-1)
    samplew = np.repeat(w, data.y.shape[1], axis=1)
    out = np.full((len(w), 4, 2), np.nan)
    for label in (0, 1):
        maskw = samplew * (y == label)[None, :]
        denom = maskw.sum(axis=1)
        num = np.sum(accepted * maskw[..., None], axis=1)
        with np.errstate(divide='ignore', invalid='ignore'):
            out[:, :, label] = num / denom[:, None]
    out[~np.broadcast_to(np.isfinite(fits).all(axis=1), (len(w),)), :, :] = np.nan
    return out

def oracle(scenario, fits):
    """Exact marginal Normal mixture per fitted policy (equal pair weights)."""
    ts = policy_thresholds(fits)
    result = np.full((len(ts), 4, 2), np.nan)
    offset = np.asarray(scenario['joint_pair_offsets'])
    common = np.asarray(scenario['common_target_shift'])
    for label in (0, 1):
        late_mu = 1.5 * label + common[label] * PAIR_SD
        joint_mu = late_mu + offset + label * scenario['joint_success_target_shift'] * PAIR_SD
        means = np.stack((joint_mu, joint_mu, late_mu, late_mu))
        result[:, :, label] = ndtr((means[None, ...] - ts) / PAIR_SD).mean(axis=-1)
    return result

def sandwich(data, fits, point_contrasts):
    pred = predictions(data, fits)[0].mean(axis=-1).reshape(data.groups, 3, 4)
    # Apply the same parentheses to each sample's four decisions.
    samplec = contrasts(pred[..., None])[..., 0]
    bounds = np.full((5, 2, 2), np.nan)
    se = np.full((5, 2), np.nan)
    if data.groups < 2 or not np.isfinite(fits).all(): return bounds, se
    critical = student_t.ppf(.975, data.groups-1)
    for label in (0, 1):
        mask = data.y == label
        n = mask.sum(axis=1).astype(float)
        if n.sum() == 0: continue
        x = (samplec * mask[..., None]).sum(axis=1)
        psi = (x - n[:, None] * point_contrasts[:, label]) / n.mean()
        se[:, label] = np.sqrt((psi * psi).sum(axis=0) / (data.groups * (data.groups-1)))
        bounds[:, label, 0] = point_contrasts[:, label] - critical * se[:, label]
        bounds[:, label, 1] = point_contrasts[:, label] + critical * se[:, label]
    return bounds, se

def analyze_data(scenario, dev, evaluation, md, me, batch=64):
    """Pure computation over explicitly supplied data and fixed group draws."""
    B = len(md)
    if len(me) != B or B < 2: raise ValueError('Bootstrap census mismatch')
    plan = CalibrationPlan(dev)
    fits = plan.fit(np.ones(dev.groups, dtype=np.int64))[0]
    point = weighted_rates(evaluation, fits, np.ones(evaluation.groups, dtype=np.int64))[0]
    conditional = weighted_rates(evaluation, fits, me)
    refit = np.full_like(conditional, np.nan)
    refit_fits = np.full((B, 8), np.nan)
    for start in range(0, B, batch):
        stop = min(start+batch, B)
        ff = plan.fit(md[start:stop]); refit_fits[start:stop] = ff
        refit[start:stop] = weighted_rates(evaluation, ff, me[start:stop])
    cp, cc, cr = contrasts(point), contrasts(conditional), contrasts(refit)
    bounds = np.full((4, 5, 2, 2), np.nan)
    pvalues = np.full((2, 5, 2), np.nan)
    valid_counts = np.zeros((2, 5, 2), dtype=np.int32)
    for c in range(5):
        for m in range(2):
            bounds[0, c, m] = interval(cc[:, c, m])
            bounds[1, c, m] = interval(cr[:, c, m])
            bounds[2, c, m] = interval(cr[:, c, m], cp[c, m], True)
            for u, draws in enumerate((cc[:, c, m], cr[:, c, m])):
                pvalues[u, c, m] = centered_p(cp[c, m], draws, B)
                valid_counts[u, c, m] = np.isfinite(draws).sum()
    bounds[3], se = sandwich(evaluation, fits, cp)
    return {'point_policy': point, 'point_contrasts': cp,
            'conditional_policy_draws': conditional, 'refit_policy_draws': refit,
            'point_thresholds': fits, 'refit_thresholds': refit_fits,
            'conditional_truth_policy': oracle(scenario, fits)[0],
            'conditional_truth_contrasts': contrasts(oracle(scenario, fits)[0]),
            'intervals': bounds, 'centered_p': pvalues, 'valid_counts': valid_counts,
            'sandwich_se': se, 'dev_multiplicity': md, 'eval_multiplicity': me,
            'dev_labels': dev.y, 'dev_cameras': dev.cameras, 'dev_joint': dev.joint,
            'eval_labels': evaluation.y, 'eval_cameras': evaluation.cameras, 'eval_joint': evaluation.joint}

def outer_record(scenario, scenario_index, outer_index, B):
    gd, ge = scenario['G_dev'], scenario['G_eval']
    dev = generator(scenario, gd, [RNG_ROOT, 10, scenario_index, outer_index])
    target = generator(scenario, ge, [RNG_ROOT, 20, scenario_index, outer_index], True)
    md = np.random.default_rng(np.random.SeedSequence([RNG_ROOT, 30, scenario_index, outer_index])).multinomial(gd, np.ones(gd)/gd, size=B)
    me = np.random.default_rng(np.random.SeedSequence([RNG_ROOT, 40, scenario_index, outer_index])).multinomial(ge, np.ones(ge)/ge, size=B)
    return analyze_data(scenario, dev, target, md, me)

def reference_record(scenario, scenario_index, reference_index):
    dev = generator(scenario, scenario['G_dev'], [RNG_ROOT, 100, scenario_index, reference_index])
    fits = CalibrationPlan(dev).fit(np.ones(dev.groups, dtype=np.int64))[0]
    pp = oracle(scenario, fits)[0]
    return {'reference_policy': pp, 'reference_contrasts': contrasts(pp),
            'reference_thresholds': fits, 'reference_class_counts': np.array([(dev.y==0).sum(), (dev.y==1).sum()]),
            'reference_valid': np.array(dev.valid_calibration, dtype=np.bool_)}
