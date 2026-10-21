"""Turn report.json into results/REPORT.md and two SVG charts.

The charts are written as plain SVG so that their colours follow the reader's light or dark theme. They use
Computer Modern, like the other figures, embedded as a subset of the copy that ships with matplotlib.
"""

import base64
import io
import logging
import re
from html import escape, unescape
from pathlib import Path

import matplotlib
from fontTools import subset
from fontTools.ttLib import TTFont

FONTS = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
logging.getLogger("fontTools").setLevel(logging.ERROR)  # the bundled fonts carry 1990s timestamps
STYLE = """
svg { font-family: CM, serif; --ink: #1f2328; --muted: #59636e; --grid: #d1d9e0; --ngram: #8c959f;
       --counts: #c4cbd3; --gru: #2a78d6; --seen: #a8c8ef; }
@media (prefers-color-scheme: dark) {
  svg { --ink: #f0f6fc; --muted: #9198a1; --grid: #3d444d; --ngram: #6e7681; --counts: #454c54;
         --gru: #3987e5; --seen: #24466f; }
}
.title { font-size: 17px; font-weight: 700; fill: var(--ink) }
.sub { font-size: 13px; fill: var(--muted) }
.head { font-size: 14px; font-weight: 700; fill: var(--ink) }
.lbl { font-size: 13px; fill: var(--ink) }
.val { font-size: 13px; fill: var(--ink) }
.tick { font-size: 12px; fill: var(--muted) }
.grid { stroke: var(--grid); stroke-width: 1 }
.range { stroke: var(--ink); stroke-width: 1.5 }
"""


def _font_face(name: str, weight: int, text: str) -> str:
    """An @font-face rule embedding only the glyphs that `text` uses."""
    font = TTFont(FONTS / name, recalcTimestamp=False)
    subsetter = subset.Subsetter(subset.Options())
    subsetter.populate(text=text)
    subsetter.subset(font)
    out = io.BytesIO()
    font.save(out)
    data = base64.b64encode(out.getvalue()).decode()
    return f"@font-face {{ font-family: CM; font-weight: {weight}; src: url(data:font/ttf;base64,{data}) }}"


def _svg(width: int, height: int, title: str, body: list[str]) -> str:
    text = "".join(unescape(t) for t in re.findall(r">([^<>]+)</text>", "\n".join(body)))
    fonts = "\n".join(_font_face(name, weight, text) for name, weight in (("cmr10.ttf", 400), ("cmb10.ttf", 700)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {width} {height}" role="img">\n'
            f"<title>{escape(title)}</title>\n<style>{fonts}\n{STYLE}</style>\n" + "\n".join(body)
            + "\n</svg>\n")


def _text(x, y, text, cls, anchor="start") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}">{escape(text)}</text>'


def _bar(x0, y, width, height, colour) -> str:
    """A horizontal bar whose free end is rounded and whose baseline end is square."""
    r = min(4, width / 2, height / 2)
    x1 = x0 + width
    return (f'<path d="M{x0:.1f},{y:.1f} H{x1 - r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} '
            f'V{y + height - r:.1f} Q{x1:.1f},{y + height:.1f} {x1 - r:.1f},{y + height:.1f} H{x0:.1f} Z" '
            f'fill="var(--{colour})"/>')


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


def figure_gap(report: dict, path: Path) -> None:
    """Excess log loss over the oracle reference in four test conditions, one small panel each."""
    best, gru = report["next_event"]["best_ngram"], report["next_event"]["gru"]
    holdout = report["holdout"]["models"]
    rows = [("Best n-gram", "ngram", best, best), ("State counts", "counts", "state_counts", "state_counts"),
            ("GRU", "gru", gru, "gru_holdout")]
    panels = [("Held-out sessions", lambda n, h: report["next_event"]["models"][n]["all"]["excess"]),
              ("Traces new to training", lambda n, h: report["novel"]["models"][n]["excess"]),
              ("Agent behaviour shifted", lambda n, h: report["shift"]["models"][n]["excess"]),
              ("Combination left out", lambda n, h: holdout[h]["all"]["excess"])]
    values = [[get(n, h) for _, _, n, h in rows] for _, get in panels]
    top = max(max(v) for v in values)
    width, left, gap, row, bar_h, y0 = 780, 104, 18, 26, 16, 92
    panel = (width - left - 3 * gap) / 4
    scale = (panel - 44) / top
    body = [_text(0, 20, "Distance from the best possible score (shorter is better)", "title"),
            _text(0, 40, "Excess log loss over the Bayes oracle, in nats per event", "sub")]
    for i, (name, *_rest) in enumerate(rows):
        body.append(_text(left - 10, y0 + i * row + bar_h - 4, name, "lbl", "end"))
    for k, ((title, _), vals) in enumerate(zip(panels, values)):
        x0 = left + k * (panel + gap)
        body.append(_text(x0, y0 - 14, title, "head"))
        body.append(f'<line x1="{x0}" x2="{x0}" y1="{y0 - 4}" y2="{y0 + 3 * row - 6}" class="grid"/>')
        for i, ((_, colour, _, _), v) in enumerate(zip(rows, vals)):
            y = y0 + i * row
            body.append(_bar(x0, y, v * scale, bar_h, colour))
            body.append(_text(x0 + v * scale + 5, y + bar_h - 4, f"{v:.3f}", "val"))
    _write(path, _svg(width, y0 + 3 * row, "Excess log loss over the oracle in four test conditions", body))


def figure_unseen(report: dict, path: Path) -> None:
    """System-check accuracy on each excluded combination: the n-gram, and GRUs that did and did not see it."""
    runs = report["holdout_sweep"]["runs"]
    groups = [tuple(g) for g in report["holdout_sweep"]["groups"]]
    width, left, right, bar_h, row, head, y = 780, 150, 724, 16, 24, 26, 90
    span = right - left
    body = [_text(0, 20, "System checks on a combination the GRU never trained on", "title"),
            _text(0, 40, "Share of pass/fail verdicts predicted correctly on new sessions of each combination left out "
                         "of training.", "sub"),
            _text(0, 56, "Bars: average of three training seeds. Lines: lowest to highest seed.", "sub")]
    ticks = (0, 0.25, 0.5, 0.75, 1.0)
    for group in groups:
        mine = [r for r in runs if tuple(r["group"]) == group]
        seen = [r["seen_system_accuracy"] for r in mine if r["seen_system_accuracy"] is not None]
        bars = [("n-gram", "ngram", [mine[0]["ngram_system_accuracy"]]),
                ("GRU, never saw it", "gru", [r["system_accuracy"] for r in mine]),
                ("GRU, trained on it", "seen", seen)]
        body.append(_text(0, y + 13, _group(group), "head"))
        y += head
        body += [f'<line x1="{left + t * span:.1f}" x2="{left + t * span:.1f}" y1="{y - 4}" '
                 f'y2="{y + len(bars) * row - 4}" class="grid"/>' for t in ticks]
        for name, colour, vals in bars:
            if not vals:
                continue
            mean, lo, hi = sum(vals) / len(vals), min(vals), max(vals)
            body.append(_text(left - 10, y + bar_h - 4, name, "lbl", "end"))
            body.append(_bar(left, y, mean * span, bar_h, colour))
            end = mean
            if len(vals) > 1:
                mid, a, b = y + bar_h / 2, left + lo * span, left + hi * span
                body.append(f'<path d="M{a:.1f},{mid - 4:.1f} V{mid + 4:.1f} M{a:.1f},{mid:.1f} H{b:.1f} '
                            f'M{b:.1f},{mid - 4:.1f} V{mid + 4:.1f}" class="range" fill="none"/>')
                end = max(mean, hi)
            body.append(_text(left + end * span + 6, y + bar_h - 4, f"{mean:.0%}", "val"))
            y += row
        y += 10
    body += [_text(left + t * span, y + 6, f"{t:.0%}", "tick", "middle") for t in ticks]
    _write(path, _svg(width, y + 12, "System-check accuracy on combinations left out of training", body))


def _write(path: Path, svg: str) -> None:
    path.write_text(svg, encoding="utf-8", newline="\n")

def render(report: dict, results_dir: Path) -> None:
    figures = results_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    figure_gap(report, figures / "gap.svg")
    if "holdout_sweep" in report:
        figure_unseen(report, figures / "unseen.svg")
    (results_dir / "REPORT.md").write_text(markdown(report), encoding="utf-8", newline="\n")


GROUP_NAMES = {"CHAT_ENGINE": "Chat Engine", "BILLING_LEDGER": "Billing Ledger", "SERVERLESS_RUNTIME": "Serverless Runtime",
               "policy": "Policy Manager", "license": "License Resolver", "usage": "Usage Collector"}


def _group(group) -> str:
    return " + ".join(GROUP_NAMES[g] for g in group)


def _sweep_lines(sw: dict) -> list[str]:
    runs = sw["runs"]
    below = sum(run["vs_ngram"]["ci95"][1] < 0 for run in runs)
    above = sum(run["vs_ngram"]["ci95"][0] > 0 for run in runs)
    beats_ngram = sum(run["system_accuracy"] > run["ngram_system_accuracy"] for run in runs)
    paired = [run for run in runs if run["seen_system_accuracy"] is not None]
    behind_seen = sum(run["system_accuracy"] < run["seen_system_accuracy"] for run in paired)
    def pct(v):
        return f"{v:.1%}" if v is not None else "–"

    return [
        "", "### Repeated over groups and seeds", "",
        f"The same test for {len(sw['groups'])} groups and {len(sw['seeds'])} training "
        f"seed{'s' if len(sw['seeds']) != 1 else ''} each. Each group is one "
        "execution gear with two optional requirements; it is removed from training and validation, the n-gram "
        "is refit without it, and a GRU is retrained for each seed and scored on new sessions of that group. "
        "\"Seen\" is the normal GRU with the same seed. The oracle is the same common reference as above.", "",
        "| Excluded group | Seed | Log loss | Gap to oracle | Difference from n-gram [95% interval] | "
        "System checks: unseen GRU | n-gram | seen GRU |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        *(f"| {_group(run['group'])} | {run['seed']} | {run['log_loss']:.4f} | {run['excess']:.4f} | "
          f"{_ci(run['vs_ngram'])} | {run['system_accuracy']:.1%} | {run['ngram_system_accuracy']:.1%} | "
          f"{pct(run['seen_system_accuracy'])} |" for run in runs),
        "", f"In {below} of {len(runs)} runs the retrained GRU's interval against the n-gram lies entirely below "
        f"zero, and in {above} entirely above it. On system checks the retrained GRU is more accurate than the "
        f"n-gram in {beats_ngram} of {len(runs)} runs and less accurate than the GRU that saw the group in "
        f"{behind_seen} of {len(paired)}.",
    ]


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
        "it believes the assembly is ready, so a model trained on them learns what follows a submission that is "
        "evidence of readiness. A forced submission carries no such evidence. The oracle without do() still "
        "treats it as an observation; the oracle queried with do() does not, and the difference between their "
        "submit log losses measures what that evidence is worth here. These what-if figures are descriptive; no "
        "intervals are reported for them.",
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
    if "holdout_sweep" in r:
        lines += _sweep_lines(r["holdout_sweep"])
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
