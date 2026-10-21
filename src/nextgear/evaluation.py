"""Metrics: proper scores by step type, a paired session bootstrap, and what-if queries."""

import numpy as np

from .events import ADD_EVENTS, INDEX, LOCAL_VERDICTS, SYSTEM_VERDICTS, VOCAB
from .rules import local_verdict, system_verdict
from .simulator import Priors, State, apply

STEP_TYPES = {"decide": "decision", "local": "local check", "system": "system check",
              "revert": "bookkeeping", "rollback": "bookkeeping", "latency": "bookkeeping"}
SLICES = ("all", "decision", "local check", "system check", "bookkeeping")


def step_types(events) -> list[str]:
    """What kind of step produced each event after the first."""
    state, types = apply(State(), events[0]), []
    for event in events[1:]:
        types.append(STEP_TYPES[state.pending])
        state = apply(state, event)
    return types


# @cpt-algo:cpt-nextgear-algo-evaluation-score:p1
def score(sessions, matrices) -> dict[str, np.ndarray]:
    """Per-event scores for one predictor, for every event after SESSION_STARTED."""
    if not sessions or len(sessions) != len(matrices):
        raise ValueError("Need exactly one prediction matrix per session.")
    parts = {k: [] for k in ("loss", "top1", "brier", "confidence", "session", "type", "target", "key")}
    for i, (session, p) in enumerate(zip(sessions, matrices)):
        y = np.array([INDEX[e] for e in session.events[1:]])
        if p.shape != (len(y), len(VOCAB)) or not np.isfinite(p).all() or (p < 0).any() \
                or not np.allclose(p.sum(axis=1), 1.0, atol=1e-6):
            raise ValueError(f"Invalid prediction matrix for {session.session_id}.")
        # @cpt-begin:cpt-nextgear-algo-evaluation-score:p1:inst-label
        parts["type"].append(np.array(step_types(session.events)))
        parts["session"].append(np.full(len(y), i))
        parts["key"].append(np.array([f"{session.session_id}:{t}" for t in range(1, len(y) + 1)]))
        parts["target"].append(y)
        # @cpt-end:cpt-nextgear-algo-evaluation-score:p1:inst-label
        # @cpt-begin:cpt-nextgear-algo-evaluation-score:p1:inst-score
        rows = np.arange(len(y))
        onehot = np.zeros_like(p)
        onehot[rows, y] = 1.0
        parts["loss"].append(-np.log(np.maximum(p[rows, y], 1e-12)))
        parts["top1"].append(p.argmax(axis=1) == y)
        parts["brier"].append(((p - onehot) ** 2).sum(axis=1))
        parts["confidence"].append(p.max(axis=1))
        # @cpt-end:cpt-nextgear-algo-evaluation-score:p1:inst-score
    return {k: np.concatenate(v) for k, v in parts.items()}


def subset(scored: dict, sessions: np.ndarray) -> dict:
    """Scores restricted to the given session indices, renumbered from zero."""
    keep = np.isin(scored["session"], sessions)
    result = {k: v[keep] for k, v in scored.items()}
    result["session"] = np.searchsorted(np.sort(sessions), result["session"])
    return result


def summarize(scored: dict, reference: dict | None = None) -> dict:
    """Mean metrics overall and per step type; with a reference, the excess log loss over it."""
    summary = {}
    for name in SLICES:
        mask = np.ones(len(scored["loss"]), bool) if name == "all" else scored["type"] == name
        if not mask.any():
            continue
        summary[name] = {"events": int(mask.sum()), "log_loss": float(scored["loss"][mask].mean()),
                         "accuracy": float(scored["top1"][mask].mean()), "brier": float(scored["brier"][mask].mean())}
        if reference is not None:
            summary[name]["excess"] = summary[name]["log_loss"] - float(reference["loss"][mask].mean())
    return summary


def calibration(scored: dict, bins: int = 15, types=("decision", "system check")) -> dict:
    """Expected calibration error of the top prediction on the steps that are uncertain."""
    mask = np.isin(scored["type"], types)
    confidence, correct = scored["confidence"][mask], scored["top1"][mask].astype(float)
    which = np.clip(np.digitize(confidence, np.linspace(0, 1, bins + 1)[1:-1]), 0, bins - 1)
    curve, ece = [], 0.0
    for b in range(bins):
        in_bin = which == b
        if in_bin.any():
            ece += in_bin.mean() * abs(correct[in_bin].mean() - confidence[in_bin].mean())
            curve.append({"confidence": float(confidence[in_bin].mean()), "accuracy": float(correct[in_bin].mean()),
                          "count": int(in_bin.sum())})
    return {"ece": float(ece), "events": int(mask.sum()), "curve": curve}


# @cpt-algo:cpt-nextgear-algo-evaluation-bootstrap:p1
def paired_bootstrap(a: dict, b: dict, resamples: int, seed: int, step_type: str = "all") -> dict:
    """Mean log loss of a minus b per event, with a 95% interval from resampling whole sessions."""
    if resamples < 100:
        raise ValueError("Use at least 100 bootstrap resamples.")
    if any(not np.array_equal(a[k], b[k]) for k in ("key", "target")):
        raise ValueError("A paired comparison needs scores for the same events.")
    # @cpt-begin:cpt-nextgear-algo-evaluation-bootstrap:p1:inst-collect
    mask = np.ones(len(a["loss"]), bool) if step_type == "all" else a["type"] == step_type
    n = int(a["session"].max()) + 1
    diff = np.bincount(a["session"][mask], weights=a["loss"][mask] - b["loss"][mask], minlength=n)
    count = np.bincount(a["session"][mask], minlength=n).astype(float)
    # @cpt-end:cpt-nextgear-algo-evaluation-bootstrap:p1:inst-collect
    # @cpt-begin:cpt-nextgear-algo-evaluation-bootstrap:p1:inst-resample
    rng = np.random.default_rng(seed)
    draws = [rng.integers(0, n, size=(min(1000, resamples - start), n)) for start in range(0, resamples, 1000)]
    samples = np.concatenate([diff[d].sum(axis=1) / count[d].sum(axis=1) for d in draws])
    # @cpt-end:cpt-nextgear-algo-evaluation-bootstrap:p1:inst-resample
    # @cpt-begin:cpt-nextgear-algo-evaluation-bootstrap:p1:inst-interval
    low, high = np.quantile(samples, [0.025, 0.975])
    return {"difference": float(diff.sum() / count.sum()), "ci95": [float(low), float(high)],
            "sessions": n, "steps": step_type}
    # @cpt-end:cpt-nextgear-algo-evaluation-bootstrap:p1:inst-interval


# @cpt-algo:cpt-nextgear-algo-evaluation-what-if:p1
def what_if(predictors: dict, sessions, priors: Priors, interventional=None) -> dict:
    """At every decision point, ask each predictor what the checks would say to each of the
    sixteen gears and to a submission, including every action the agent did not take.

    `interventional` is a BayesOracle queried with do(), the correct reference for forced actions.
    """
    # @cpt-begin:cpt-nextgear-algo-evaluation-what-if:p1:inst-queries
    local_q, local_y, chosen, submit_q, submit_y = [], [], [], [], []
    for session in sessions:
        state = apply(State(), session.events[0])
        for t, event in enumerate(session.events[1:], start=1):
            if (state.pending == "decide" and state.proposals < priors.max_proposals
                    and state.submissions < priors.max_submissions):
                prefix = session.events[:t]
                for add, gear in ADD_EVENTS.items():
                    local_q.append(prefix + (add,))
                    local_y.append(LOCAL_VERDICTS.index(local_verdict(state.path, state.outbound, state.platform, gear)))
                    chosen.append(add == event)
                submit_q.append(prefix + ("SUBMIT_ASSEMBLY",))
                submit_y.append(SYSTEM_VERDICTS.index(
                    system_verdict(session.hidden.spec, state.path, state.outbound, state.platform, state.cache)))
            state = apply(state, event)
    # @cpt-end:cpt-nextgear-algo-evaluation-what-if:p1:inst-queries
    local_y, submit_y, unchosen = np.array(local_y), np.array(submit_y), ~np.array(chosen)
    local_cols, submit_cols = [INDEX[v] for v in LOCAL_VERDICTS], [INDEX[v] for v in SYSTEM_VERDICTS]
    admissible = SYSTEM_VERDICTS.index("ASSEMBLY_ADMISSIBLE")
    queried = {name: (model, False) for name, model in predictors.items()}
    if interventional is not None:
        queried["oracle_do"] = (interventional, True)
    results = {"decision_points": len(submit_y), "local_queries": len(local_y),
               "unchosen_local_queries": int(unchosen.sum()),
               "unchosen_rejected_share": float((local_y[unchosen] != 0).mean()),
               "true_admissible_rate": float((submit_y == admissible).mean()), "models": {}}
    # @cpt-begin:cpt-nextgear-algo-evaluation-what-if:p1:inst-score
    for name, (model, do) in queried.items():
        local_p = (model.predict_next(local_q, intervene=True) if do else model.predict_next(local_q))[:, local_cols]
        submit_p = (model.predict_next(submit_q, intervene=True) if do else model.predict_next(submit_q))[:, submit_cols]
        rows_l, rows_s = np.arange(len(local_y)), np.arange(len(submit_y))
        loss = lambda p, rows, y: max(0.0, float(-np.log(np.maximum(p[rows, y], 1e-12)).mean()))  # noqa: E731
        results["models"][name] = {
            "unchosen_local_accuracy": float((local_p.argmax(axis=1) == local_y)[unchosen].mean()),
            "local_log_loss": loss(local_p, rows_l, local_y),
            "submit_p_admissible": float(submit_p[:, admissible].mean()),
            "submit_log_loss": loss(submit_p, rows_s, submit_y),
        }
    # @cpt-end:cpt-nextgear-algo-evaluation-what-if:p1:inst-score
    return results


HOLDOUT_GROUP: tuple[str, ...] = ("CHAT_ENGINE", "policy", "license")


def in_group(session, group) -> bool:
    """True when the session's specification needs the group's execution gear and both optional gears.
    A group is written as (execution gear, flag, flag) with flags from policy, license and usage."""
    spec = session.hidden.spec
    return spec.execution == group[0] and all(getattr(spec, flag) for flag in group[1:])


def in_holdout_group(session) -> bool:
    """The specification combination removed from training for the generalization test."""
    return in_group(session, HOLDOUT_GROUP)
