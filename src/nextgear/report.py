"""Turn report.json into results/REPORT.md and two figures in the style of a paper."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Computer Modern ships with matplotlib, so the figures look like LaTeX without a TeX install.
PAPER = {
    "font.family": "serif", "font.serif": ["cmr10"], "mathtext.fontset": "cm", "axes.unicode_minus": False,
    "axes.formatter.use_mathtext": True, "font.size": 9, "axes.titlesize": 9, "axes.linewidth": 0.6,
    "axes.edgecolor": "black", "xtick.direction": "in", "ytick.direction": "in", "xtick.major.width": 0.6,
    "xtick.major.size": 3, "ytick.major.size": 0, "xtick.labelsize": 8, "ytick.labelsize": 9,
    "svg.fonttype": "path", "svg.hashsalt": "nextgear", "figure.facecolor": "white", "savefig.facecolor": "white",
}
INK, GRU, GREY, LIGHT = "#000000", "#2b5797", "#8c8c8c", "#c8c8c8"


def label(name: str) -> str:
    if name.startswith("ngram_"):
        return f"n-gram ({name.split('_')[1]})"
    if name.startswith("gru_seed"):
        return "GRU" if name.endswith("0") else f"GRU (seed {name[-1]})"
    return {"frequency": "Frequency", "state_counts": "State counts", "oracle": "Oracle",
            "oracle_do": "Oracle with do()", "oracle_stale": "Oracle, old priors",
            "gru_holdout": "GRU, combination unseen"}.get(name, name)


def _ci(c: dict) -> str:
    return f"{c['difference']:+.4f} [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]"


def _paired_rows(comparisons) -> list[str]:
    return [f"| {label(c['a'])} vs {label(c['b'])} | {c['steps']} | {_ci(c)} |" for c in comparisons]


def _bars(ax, names, values, colors, fmt, labels=None):
    y = list(range(len(names)))[::-1]
    ax.barh(y, values, height=0.62, color=colors, edgecolor=INK, linewidth=0.5)
    for yi, v in zip(y, values):
        ax.text(v, yi, f"  {fmt(v)}", va="center", fontsize=8)
    ax.set_yticks(y, [(labels or {}).get(n, label(n)) for n in names])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)


def figure_gap(report: dict, path: Path) -> None:
    """Excess log loss over the oracle reference in four test conditions."""
    best, gru = report["next_event"]["best_ngram"], report["next_event"]["gru"]
    names = [best, "state_counts", gru]
    holdout = report["holdout"]["models"]
    panels = [("(a) held-out sessions", {n: report["next_event"]["models"][n]["all"]["excess"] for n in names}),
              ("(b) traces never seen in training", {n: report["novel"]["models"][n]["excess"] for n in names}),
              ("(c) agent behaviour shifted", {n: report["shift"]["models"][n]["excess"] for n in names}),
              ("(d) requirement combination unseen", {best: holdout[best]["all"]["excess"],
                                                      "state_counts": holdout["state_counts"]["all"]["excess"],
                                                      gru: holdout["gru_holdout"]["all"]["excess"]})]
    top = max(v for _, values in panels for v in values.values())
    with plt.rc_context(PAPER):
        fig, axes = plt.subplots(1, 4, figsize=(9.6, 1.9), sharey=True)
        for ax, (title, values) in zip(axes, panels):
            _bars(ax, names, [values[n] for n in names], [LIGHT, GREY, GRU], lambda v: f"{v:.3f}")
            ax.set_title(title, loc="left")
            ax.set_xlim(0, top * 1.4)
        fig.subplots_adjust(left=0.085, right=0.99, top=0.84, bottom=0.3, wspace=0.13)
        fig.text(0.54, 0.1, r"excess log loss over the Bayes reference $p^\ast$ (nats per event)",
                 ha="center")
        fig.savefig(path, bbox_inches="tight", pad_inches=0.06)
        plt.close(fig)


def figure_what_if(report: dict, path: Path) -> None:
    """Predicted chance that a forced submission passes, against the observed rate."""
    w = report["what_if"]
    names = [report["next_event"]["best_ngram"], "state_counts", report["next_event"]["gru"], "oracle", "oracle_do"]
    values = [w["models"][n]["submit_p_admissible"] for n in names]
    with plt.rc_context(PAPER):
        fig, ax = plt.subplots(figsize=(5.6, 1.9))
        _bars(ax, names, values, [LIGHT, GREY, GRU, "white", INK], lambda v: f"{v:.1%}",
              labels={"oracle": r"Oracle, $a$ observed", "oracle_do": r"Oracle, $\mathrm{do}(a)$"})
        ax.axvline(w["true_admissible_rate"], color=INK, linewidth=0.8, linestyle=(0, (4, 2)))
        ax.text(w["true_admissible_rate"], len(names) - 0.4, f" observed: {w['true_admissible_rate']:.1%}",
                fontsize=8, va="bottom")
        ax.set_xlim(0, max(values) * 1.3)
        ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.05))
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0%}"))
        ax.set_xlabel(r"predicted $P(\mathrm{pass} \mid e_{1:t},\ a = \mathrm{submit})$ at every decision point")
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight", pad_inches=0.06)
        plt.close(fig)


def render(report: dict, results_dir: Path) -> None:
    figures = results_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    figure_gap(report, figures / "gap.svg")
    figure_what_if(report, figures / "what-if.svg")
    (results_dir / "REPORT.md").write_text(markdown(report), encoding="utf-8", newline="\n")


def markdown(r: dict) -> str:
    ne, meta = r["next_event"], r["meta"]
    best = ne["best_ngram"]
    seconds = meta["seconds"]
    lines = [
        "# Benchmark results", "",
        f"Generated by `python -m nextgear all` in {seconds['total'] / 60:.1f} minutes on {meta['platform']} "
        f"with {meta['threads']} threads (Python {meta['python']}, PyTorch {meta['torch']}). "
        "Every number below comes from [report.json](report.json).", "",
        "## 1. Next-event prediction", "",
        f"{ne['sessions']} held-out sessions, {ne['events']} predicted events. Log loss is the average of "
        "−log P(the event that happened); lower is better. Here the oracle's priors match the data, so its value "
        "is the lowest that any predictor seeing only the events can expect. Accuracy scores the top prediction "
        "as right or wrong.", "",
        "| Model | Log loss | Gap to oracle | Accuracy | Decisions | Local checks | System checks | Brier | ECE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, m in ne["models"].items():
        ece = r["calibration"].get(name, {}).get("ece")
        lines.append(f"| {label(name)} | {m['all']['log_loss']:.4f} | {m['all']['excess']:.4f} | "
                     f"{m['all']['accuracy']:.1%} | {m['decision']['accuracy']:.1%} | {m['local check']['accuracy']:.1%} | "
                     f"{m['system check']['accuracy']:.1%} | {m['all']['brier']:.4f} | "
                     + (f"{ece:.3f} |" if ece is not None else "– |"))
    lines += [
        "", f"The GRU closes **{ne['gap_closed']:.0%}** of the gap between the best n-gram and the oracle. "
        f"Across {len(ne['seeds'])} training seeds its log loss ranges from {min(ne['seeds']):.4f} to {max(ne['seeds']):.4f}. "
        f"The n-gram context ({best.split('_')[1]} events) was chosen on validation data. ECE is the expected "
        "calibration error of the top prediction, measured on decisions and system checks: the only steps whose "
        "outcome depends on hidden values.", "",
        "## 2. Are the differences real?", "",
        "Differences in log loss per event, with 95% intervals from resampling whole sessions "
        f"({meta['config']['evaluation']['bootstrap_resamples']} resamples), so events from the same session stay together. "
        "Negative means the first model is better.", "",
        "| Comparison | Steps | Difference [95% interval] |", "|---|---|---:|", *_paired_rows(ne["paired"]),
    ]
    nv = r["novel"]
    lines += [
        "", "## 3. Traces never seen in training", "",
        f"The simulator is small enough to repeat itself: {nv['repeated']} of {ne['sessions']} test sessions match a "
        f"training session event for event. The tables below score the other {nv['sessions']}. Their prefixes and "
        "subsequences can still be familiar from training, so this rules out recall of whole traces, not "
        "memorisation in general. Selecting sessions by novelty also changes their distribution, and the oracle "
        "is not told about the selection: it still gives probability to endings that would recreate a training "
        "trace. Here it is a common reference, not the best achievable score for this subset.", "",
        "| Model | Log loss | Gap to oracle | Accuracy |", "|---|---:|---:|---:|",
        *(f"| {label(n)} | {m['log_loss']:.4f} | {m['excess']:.4f} | {m['accuracy']:.1%} |" for n, m in nv["models"].items()),
        "", "| Comparison | Steps | Difference [95% interval] |", "|---|---|---:|", *_paired_rows(nv["paired"]),
    ]
    w = r["what_if"]
    lines += [
        "", "## 4. What if the agent had done something else?", "",
        f"At every decision point of the first {meta['config']['evaluation']['what_if_sessions']} test sessions "
        f"({w['decision_points']} points), each model predicts the check's verdict for all sixteen gears and for a "
        f"submission. The checks give the true answer. {w['unchosen_local_queries']} gear queries are actions the "
        f"agent did not take; {w['unchosen_rejected_share']:.0%} of those would have been rejected.", "",
        "| Model | Right verdict, untaken gears | Gear verdict log loss | P(pass) if forced to submit | Submit log loss |",
        "|---|---:|---:|---:|---:|",
        *(f"| {label(n)} | {m['unchosen_local_accuracy']:.2%} | {m['local_log_loss']:.4f} | {m['submit_p_admissible']:.1%} | "
          f"{m['submit_log_loss']:.4f} |" for n, m in w["models"].items()),
        "", f"Forced submissions pass {w['true_admissible_rate']:.1%} of the time. In the logs, an agent submits when "
        "it believes the assembly is ready, so a model trained on them reads a submission as evidence of "
        "readiness and over-predicts a pass. The oracle without do() does the same, because it treats the "
        "submission as an observation. The oracle queried with do() treats the submission as forced and does "
        "not learn from it. These what-if figures are descriptive; no intervals are reported for them.",
    ]
    s = r["shift"]
    lines += [
        "", "## 5. The agent changes", "",
        f"{s['sessions']} sessions from changed settings, with no retraining: "
        + ", ".join(f"`{k} = {v}`" for k, v in s["changes"].items()) + ". The oracle knows the new settings; "
        "\"Oracle, old priors\" is the same exact model with the original settings.", "",
        "| Model | Log loss | Gap to oracle | Accuracy |", "|---|---:|---:|---:|",
        *(f"| {label(n)} | {m['log_loss']:.4f} | {m['excess']:.4f} | {m['accuracy']:.1%} |" for n, m in s["models"].items()),
        "", "| Comparison | Steps | Difference [95% interval] |", "|---|---|---:|", *_paired_rows(s["paired"]),
    ]
    h = r["holdout"]
    lines += [
        "", "## 6. A requirement combination never seen in training", "",
        f"Sessions whose specification needs the Chat Engine with both the Policy Manager and the License Resolver "
        f"were removed from training and validation ({h['excluded_train']} training sessions). The count models and a "
        f"GRU were refit without them, then scored on {h['sessions']} new sessions of exactly that kind. "
        "\"GRU\" is the normal model, which did see such sessions. The oracle keeps the base prior and is not "
        "told that the evaluation sessions come from this group. It is a common reference, not the best score "
        "available to a predictor that knew the group. Model settings and the n-gram context are reused from "
        "the main experiment, where they were chosen on validation data that included this group, so this is "
        "an exploratory exclusion test rather than an untouched holdout.", "",
        "| Model | Log loss | Gap to oracle | System checks log loss | System checks accuracy |", "|---|---:|---:|---:|---:|",
        *(f"| {label(n)} | {m['all']['log_loss']:.4f} | {m['all']['excess']:.4f} | {m['system check']['log_loss']:.4f} | "
          f"{m['system check']['accuracy']:.1%} |" for n, m in h["models"].items()),
        "", "| Comparison | Steps | Difference [95% interval] |", "|---|---|---:|", *_paired_rows(h["paired"]),
    ]
    lines += ["", "## 7. Training", "", "| Model | Epochs | Best validation log loss |", "|---|---:|---:|",
              *(f"| {label(t['model'])} | {t['epochs']} | {t['validation_log_loss']:.4f} |" for t in r["training"]),
              "", "Stage times (seconds): " + ", ".join(f"{k} {v:.0f}" for k, v in seconds.items()) + ".", "",
              "The intervals are conditional on the fitted models and the authored generator. They do not cover "
              "simulator misspecification or all training randomness; the three full-data training seeds show some "
              "of the latter, and the holdout GRU has a single seed. The analyses are exploratory, without "
              "preregistration or correction for multiple comparisons. The oracle shares transition code with the "
              "generator, so it is a reference inside the simulator, not independent validation of the domain "
              "assumptions.", ""]
    return "\n".join(lines)
