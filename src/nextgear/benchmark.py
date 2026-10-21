"""Generate the datasets, train the models and run the benchmark."""

import hashlib
import json
import platform
import time
import tomllib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import torch

from .baselines import Frequency, NGram, StateCounts
from .evaluation import calibration, in_group, in_holdout_group, paired_bootstrap, score, subset, summarize, what_if
from .gru import GRUModel
from .oracle import BayesOracle, predict_parallel
from .report import render
from .simulator import Priors, generate, read_sessions, write_sessions

SPLITS = ("train", "validation", "test", "shifted", "holdout")


def load_config(path: Path) -> dict:
    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


def priors(config: dict, shifted: bool = False) -> Priors:
    values = dict(config.get("priors", {}))
    if shifted:
        values.update(config.get("shift", {}))
    return Priors.from_dict(values)


def _stamp(config: dict) -> str:
    settings = {k: config.get(k) for k in ("data", "seeds", "priors", "shift")}
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:16]


def generate_data(config: dict, data_dir: Path) -> None:
    sizes, seeds = config["data"], config["seeds"]
    if len({seeds[s] for s in SPLITS}) != len(SPLITS):
        raise ValueError("Every split needs its own seed.")
    for name in SPLITS:
        if name == "holdout":
            # The held-out combination is 1 session in 12, so draw a pool and keep only that group.
            # @cpt-begin:cpt-nextgear-algo-evaluation-holdout:p1:inst-sample
            pool = generate(sizes["holdout"] * 30, seeds["holdout"], name, priors(config))
            sessions = [s for s in pool if in_holdout_group(s)][:sizes["holdout"]]
            # @cpt-end:cpt-nextgear-algo-evaluation-holdout:p1:inst-sample
            if len(sessions) < sizes["holdout"]:
                raise ValueError("The holdout pool is too small for the requested number of sessions.")
        else:
            sessions = generate(sizes[name], seeds[name], name, priors(config, shifted=name == "shifted"))
        write_sessions(data_dir / f"{name}.jsonl", sessions)
        print(f"  {name:<10} {len(sessions):>5} sessions")
    (data_dir / "stamp.txt").write_text(_stamp(config), encoding="utf-8")


def load_data(config: dict, data_dir: Path) -> dict[str, list]:
    """Read every split, regenerating the data first if it is missing or from other settings."""
    stamp = data_dir / "stamp.txt"
    if not stamp.exists() or stamp.read_text(encoding="utf-8") != _stamp(config):
        print(f"Generating data in {data_dir}")
        generate_data(config, data_dir)
    data = {name: read_sessions(data_dir / f"{name}.jsonl") for name in SPLITS}
    ids = [s.session_id for sessions in data.values() for s in sessions]
    if len(ids) != len(set(ids)):
        raise ValueError("Session identifiers repeat across splits.")
    return data


def _fit(job: tuple) -> dict:
    name, settings, train, validation, path, threads = job
    torch.set_num_threads(threads)
    start = time.perf_counter()
    model = GRUModel(**settings).fit(train, validation)
    model.save(path)
    return {"model": name, "epochs": len(model.history), "validation_log_loss": min(model.history),
            "seconds": time.perf_counter() - start}


def train_models(config: dict, data: dict, models_dir: Path, threads: int) -> list[dict]:
    """One GRU per seed on the full training data, plus one trained without the holdout group."""
    settings = {k: v for k, v in config["model"].items() if k != "seeds"}
    seeds = config["model"]["seeds"]
    full = [s.events for s in data["train"]], [s.events for s in data["validation"]]
    # @cpt-begin:cpt-nextgear-algo-evaluation-holdout:p1:inst-exclude
    kept = ([s.events for s in data["train"] if not in_holdout_group(s)],
            [s.events for s in data["validation"] if not in_holdout_group(s)])
    # @cpt-end:cpt-nextgear-algo-evaluation-holdout:p1:inst-exclude
    jobs = [(f"gru_seed{seed}", {**settings, "seed": seed}, *full) for seed in seeds]
    jobs.append(("gru_holdout", {**settings, "seed": seeds[0]}, *kept))
    return _run_jobs(jobs, models_dir, threads)


def _run_jobs(jobs: list[tuple], models_dir: Path, threads: int) -> list[dict]:
    workers = max(1, min(len(jobs), threads // 4))
    models_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(*job, models_dir / f"{job[0]}.pt", max(1, threads // workers)) for job in jobs]
    if workers == 1:
        records = [_fit(job) for job in jobs]
    else:
        with ProcessPoolExecutor(workers) as pool:
            records = list(pool.map(_fit, jobs))
    for r in records:
        print(f"  {r['model']:<34} {r['epochs']:>2} epochs, validation log loss {r['validation_log_loss']:.4f}, "
              f"{r['seconds']:.0f}s")
    return records


# @cpt-dod:cpt-nextgear-dod-evaluation-report:p1
# @cpt-algo:cpt-nextgear-algo-evaluation-novel:p1
# @cpt-algo:cpt-nextgear-algo-evaluation-shift:p1
# @cpt-algo:cpt-nextgear-algo-evaluation-holdout:p1
def evaluate(config: dict, data: dict, models_dir: Path, threads: int) -> dict:
    ev, seeds = config["evaluation"], config["model"]["seeds"]
    boot = {"resamples": ev["bootstrap_resamples"], "seed": config["seeds"]["bootstrap"]}
    base, shifted = priors(config), priors(config, shifted=True)
    train, validation, test = data["train"], data["validation"], data["test"]
    train_events = [s.events for s in train]
    timings, start = {}, time.perf_counter()

    def lap(name):
        nonlocal start
        timings[name], start = time.perf_counter() - start, time.perf_counter()

    def score_all(models, sessions, oracle_priors=None):
        events = [s.events for s in sessions]
        scored = {name: score(sessions, model.predict_many(events)) for name, model in models.items()}
        if oracle_priors is not None:
            scored["oracle"] = score(sessions, predict_parallel(oracle_priors, events, threads))
        return scored

    def compare(scored, a, b, steps="all"):
        return {"a": a, "b": b, **paired_bootstrap(scored[a], scored[b], step_type=steps, **boot)}

    ngrams = {f"ngram_{k}": NGram(k).fit(train_events) for k in config["baselines"]["contexts"]}
    best = min(ngrams, key=lambda n: score(validation, ngrams[n].predict_many([s.events for s in validation]))["loss"].mean())
    grus = {f"gru_seed{s}": GRUModel.load(models_dir / f"gru_seed{s}.pt") for s in seeds}
    gru = f"gru_seed{seeds[0]}"
    predictors = {"frequency": Frequency().fit(train_events), **ngrams,
                  "state_counts": StateCounts(base.max_proposals, base.max_submissions).fit(train_events), **grus}

    scored = score_all(predictors, test, base)
    models = {name: summarize(s, scored["oracle"]) for name, s in scored.items()}
    o, b, g = (models[n]["all"]["log_loss"] for n in ("oracle", best, gru))
    report = {"next_event": {
        "sessions": len(test), "events": len(scored["oracle"]["loss"]), "best_ngram": best, "gru": gru,
        "models": models, "gap_closed": (b - g) / (b - o),
        "seeds": [models[n]["all"]["log_loss"] for n in grus],
        "paired": [*(compare(scored, n, best) for n in grus), compare(scored, gru, "state_counts"),
                   compare(scored, gru, "oracle"),
                   *(compare(scored, gru, best, steps) for steps in ("decision", "local check", "system check"))]}}
    report["calibration"] = {n: calibration(scored[n], ev["calibration_bins"])
                             for n in ("frequency", best, "state_counts", gru, "oracle")}
    lap("test")

    # @cpt-begin:cpt-nextgear-algo-evaluation-novel:p1:inst-split
    seen = {s.events for s in train}
    novel = np.array([i for i, s in enumerate(test) if s.events not in seen])
    novel_scored = {name: subset(s, novel) for name, s in scored.items()}
    # @cpt-end:cpt-nextgear-algo-evaluation-novel:p1:inst-split
    # @cpt-begin:cpt-nextgear-algo-evaluation-novel:p1:inst-compare
    report["novel"] = {
        "sessions": len(novel), "repeated": len(test) - len(novel),
        "models": {n: summarize(novel_scored[n], novel_scored["oracle"])["all"]
                   for n in (best, "state_counts", gru, "oracle")},
        "paired": [compare(novel_scored, gru, best), compare(novel_scored, gru, "state_counts")]}
    # @cpt-end:cpt-nextgear-algo-evaluation-novel:p1:inst-compare

    oracle = BayesOracle(base)
    report["what_if"] = what_if({best: predictors[best], "state_counts": predictors["state_counts"],
                                 gru: grus[gru], "oracle": oracle},
                                test[:ev["what_if_sessions"]], base, interventional=oracle)
    lap("what_if")

    # @cpt-begin:cpt-nextgear-algo-evaluation-shift:p1:inst-score
    chosen = {best: predictors[best], "state_counts": predictors["state_counts"], gru: grus[gru]}
    shift_scored = score_all(chosen, data["shifted"], shifted)
    shift_scored["oracle_stale"] = score(data["shifted"], predict_parallel(base, [s.events for s in data["shifted"]], threads))
    report["shift"] = {"sessions": len(data["shifted"]), "changes": config["shift"],
                       "models": {n: summarize(s, shift_scored["oracle"])["all"] for n, s in shift_scored.items()},
                       "paired": [compare(shift_scored, gru, best), compare(shift_scored, gru, "state_counts")]}
    # @cpt-end:cpt-nextgear-algo-evaluation-shift:p1:inst-score
    lap("shift")

    # @cpt-begin:cpt-nextgear-algo-evaluation-holdout:p1:inst-score
    kept = [s.events for s in train if not in_holdout_group(s)]
    held = {best: NGram(ngrams[best].context).fit(kept),
            "state_counts": StateCounts(base.max_proposals, base.max_submissions).fit(kept),
            "gru_holdout": GRUModel.load(models_dir / "gru_holdout.pt"), gru: grus[gru]}
    hold_scored = score_all(held, data["holdout"], base)
    report["holdout"] = {"sessions": len(data["holdout"]), "excluded_train": len(train) - len(kept),
                         "models": {n: summarize(s, hold_scored["oracle"]) for n, s in hold_scored.items()},
                         "paired": [compare(hold_scored, "gru_holdout", best),
                                    compare(hold_scored, "gru_holdout", "state_counts"),
                                    compare(hold_scored, "gru_holdout", gru)]}
    # @cpt-end:cpt-nextgear-algo-evaluation-holdout:p1:inst-score
    lap("holdout")
    report["training"] = [{"model": n, "epochs": len(m.history), "validation_log_loss": min(m.history)}
                          for n, m in {**grus, "gru_holdout": held["gru_holdout"]}.items()]
    report["timings"] = timings
    return report


def _meta(config: dict, threads: int, seconds: dict) -> dict:
    return {"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__,
            "platform": f"{platform.system()} {platform.release()} {platform.machine()}", "threads": threads,
            "seconds": seconds, "config": config}


def run_training(config: dict, data: dict, models_dir: Path, threads: int) -> None:
    print("Training")
    train_models(config, data, models_dir, threads)
    (models_dir / "stamp.txt").write_text(_stamp(config) + json.dumps(config["model"], sort_keys=True), encoding="utf-8")


def check_models(config: dict, models_dir: Path) -> None:
    stamp = models_dir / "stamp.txt"
    if not stamp.exists() or stamp.read_text(encoding="utf-8") != _stamp(config) + json.dumps(config["model"], sort_keys=True):
        raise ValueError(f"The models in {models_dir} were trained on other data or settings; "
                         "run `python -m nextgear train` first.")


# @cpt-flow:cpt-nextgear-flow-pipeline-reproduce:p1
def run(config: dict, data_dir: Path, models_dir: Path, results_dir: Path, threads: int, train: bool) -> dict:
    """Data, then (optionally) training, then the evaluation and the report."""
    start = time.perf_counter()
    # @cpt-begin:cpt-nextgear-flow-pipeline-reproduce:p1:inst-generate
    data = load_data(config, data_dir)
    # @cpt-end:cpt-nextgear-flow-pipeline-reproduce:p1:inst-generate
    seconds = {"data": time.perf_counter() - start}
    # @cpt-begin:cpt-nextgear-flow-pipeline-reproduce:p1:inst-train
    if train:
        run_training(config, data, models_dir, threads)
        seconds["train"] = time.perf_counter() - start - seconds["data"]
    check_models(config, models_dir)
    # @cpt-end:cpt-nextgear-flow-pipeline-reproduce:p1:inst-train
    # @cpt-begin:cpt-nextgear-flow-pipeline-reproduce:p1:inst-evaluate
    print("Evaluating")
    report = evaluate(config, data, models_dir, threads)
    seconds["evaluate"] = sum(report.pop("timings").values())
    seconds["total"] = time.perf_counter() - start
    report["meta"] = _meta(config, threads, seconds)
    # @cpt-end:cpt-nextgear-flow-pipeline-reproduce:p1:inst-evaluate
    # @cpt-begin:cpt-nextgear-flow-pipeline-reproduce:p1:inst-publish
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "report.json").write_text(json.dumps(report, indent=1, allow_nan=False), encoding="utf-8")
    render(report, results_dir)
    if "holdout" in config:
        report = run_sweep(config, data_dir, models_dir, results_dir, threads, train, report)
    print(f"Done in {time.perf_counter() - start:.0f}s. Report: {results_dir / 'REPORT.md'}")
    return report
    # @cpt-end:cpt-nextgear-flow-pipeline-reproduce:p1:inst-publish


# The repeated exclusion test: several requirement groups, each removed from training in turn, with
# several training seeds. It has its own data files, checkpoints and stamp, so it can be rerun with
# `python -m nextgear sweep` without touching the main experiment.

def _groups(config: dict) -> list[tuple[str, ...]]:
    return [tuple(g) for g in config["holdout"]["groups"]]


def group_key(group) -> str:
    return "-".join(part.lower() for part in group)


def _sweep_stamp(config: dict) -> str:
    return _stamp(config) + json.dumps({"model": config["model"], "holdout": config["holdout"]}, sort_keys=True)


def load_sweep_data(config: dict, data_dir: Path) -> dict[str, list]:
    """New sessions for every group, drawn from the same pool as the holdout split."""
    files = {group_key(g): data_dir / f"holdout-{group_key(g)}.jsonl" for g in _groups(config)}
    stamp = data_dir / "sweep_stamp.txt"
    if (not stamp.exists() or stamp.read_text(encoding="utf-8") != _sweep_stamp(config)
            or not all(f.exists() for f in files.values())):
        size = config["data"]["holdout"]
        pool = generate(size * 30, config["seeds"]["holdout"], "holdout", priors(config))
        for group in _groups(config):
            sessions = [s for s in pool if in_group(s, group)][:size]
            if len(sessions) < size:
                raise ValueError(f"The holdout pool is too small for group {group}.")
            write_sessions(files[group_key(group)], sessions)
        stamp.write_text(_sweep_stamp(config), encoding="utf-8")
    return {key: read_sessions(path) for key, path in files.items()}


# @cpt-begin:cpt-nextgear-algo-evaluation-holdout:p1:inst-sweep
def train_sweep(config: dict, data: dict, models_dir: Path, threads: int) -> list[dict]:
    """One GRU per group and seed, each trained without its group."""
    settings = {k: v for k, v in config["model"].items() if k != "seeds"}
    jobs = []
    for group in _groups(config):
        kept = ([s.events for s in data["train"] if not in_group(s, group)],
                [s.events for s in data["validation"] if not in_group(s, group)])
        jobs += [(f"{group_key(group)}_seed{seed}", {**settings, "seed": seed}, *kept)
                 for seed in config["holdout"]["seeds"]]
    sweep_dir = models_dir / "sweep"
    records = _run_jobs(jobs, sweep_dir, threads)
    (sweep_dir / "stamp.txt").write_text(_sweep_stamp(config), encoding="utf-8")
    return records


def evaluate_sweep(config: dict, data: dict, groups: dict[str, list], models_dir: Path, threads: int,
                   context: int) -> dict:
    """Score every group's GRUs, the n-gram refit without the group, and the normal GRUs, on new
    sessions from the group, against the base-prior oracle as a common reference."""
    stamp = models_dir / "sweep" / "stamp.txt"
    if not stamp.exists() or stamp.read_text(encoding="utf-8") != _sweep_stamp(config):
        raise ValueError(f"The sweep models in {models_dir / 'sweep'} were trained on other data or settings; "
                         "run `python -m nextgear sweep` first.")
    ev = config["evaluation"]
    boot = {"resamples": ev["bootstrap_resamples"], "seed": config["seeds"]["bootstrap"]}
    seen = {f"gru_seed{s}": GRUModel.load(models_dir / f"gru_seed{s}.pt") for s in config["model"]["seeds"]}
    results = []
    for group in _groups(config):
        key, sessions = group_key(group), groups[group_key(group)]
        events = [s.events for s in sessions]
        kept = [s.events for s in data["train"] if not in_group(s, group)]
        models = {"ngram": NGram(context).fit(kept), **seen}
        models |= {f"unseen_seed{s}": GRUModel.load(models_dir / "sweep" / f"{key}_seed{s}.pt")
                   for s in config["holdout"]["seeds"]}
        scored = {name: score(sessions, model.predict_many(events)) for name, model in models.items()}
        scored["oracle"] = score(sessions, predict_parallel(priors(config), events, threads))
        summary = {name: summarize(s, scored["oracle"]) for name, s in scored.items()}
        for seed in config["holdout"]["seeds"]:
            unseen, normal = f"unseen_seed{seed}", summary.get(f"gru_seed{seed}")
            results.append({
                "group": list(group), "seed": seed, "sessions": len(sessions),
                "excluded_train": len(data["train"]) - len(kept),
                "log_loss": summary[unseen]["all"]["log_loss"], "excess": summary[unseen]["all"]["excess"],
                "system_accuracy": summary[unseen]["system check"]["accuracy"],
                "ngram_system_accuracy": summary["ngram"]["system check"]["accuracy"],
                "seen_system_accuracy": normal["system check"]["accuracy"] if normal else None,
                "vs_ngram": paired_bootstrap(scored[unseen], scored["ngram"], **boot),
            })
    return {"groups": [list(g) for g in _groups(config)], "seeds": config["holdout"]["seeds"], "runs": results}
# @cpt-end:cpt-nextgear-algo-evaluation-holdout:p1:inst-sweep


def run_sweep(config: dict, data_dir: Path, models_dir: Path, results_dir: Path, threads: int, train: bool,
              report: dict | None = None) -> dict:
    """Train (optionally) and evaluate the repeated exclusion test, add it to the report and re-render."""
    start = time.perf_counter()
    data = load_data(config, data_dir)
    groups = load_sweep_data(config, data_dir)
    if train:
        print("Training the repeated exclusion test")
        train_sweep(config, data, models_dir, threads)
    trained = time.perf_counter()
    if report is None:
        report = json.loads((results_dir / "report.json").read_text(encoding="utf-8"))
    context = int(report["next_event"]["best_ngram"].split("_")[1])
    print("Evaluating the repeated exclusion test")
    report["holdout_sweep"] = evaluate_sweep(config, data, groups, models_dir, threads, context)
    report["holdout_sweep"]["seconds"] = {"train": trained - start, "evaluate": time.perf_counter() - trained}
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "report.json").write_text(json.dumps(report, indent=1, allow_nan=False), encoding="utf-8")
    render(report, results_dir)
    return report
