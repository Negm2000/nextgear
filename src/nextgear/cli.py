"""nextgear command line: all | train | evaluate | demo | hero."""

import argparse
import os
import sys
from pathlib import Path

import torch

from . import benchmark
from .baselines import NGram
from .gru import GRUModel
from .hero import render_hero
from .oracle import FACTS, BayesOracle


# @cpt-dod:cpt-nextgear-dod-pipeline-commands:p1
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nextgear", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/default.toml"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--threads", type=int, default=min(16, os.cpu_count() or 1))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("all", help="generate data, train every model, evaluate, write the report")
    commands.add_parser("train", help="generate data if needed and train the GRUs")
    commands.add_parser("evaluate", help="evaluate the trained models and write the report")
    demo = commands.add_parser("demo", help="replay a held-out session in the terminal")
    demo.add_argument("--session", type=int, help="index into the test split")
    demo.add_argument("--what-if", type=int, help="event position of the decision to question")
    hero = commands.add_parser("hero", help="draw the README animation")
    hero.add_argument("--session", type=int, help="index into the test split")
    hero.add_argument("--out", type=Path, default=Path("assets/session.svg"))
    args = parser.parse_args(argv)
    if args.threads < 1:
        parser.error("--threads must be positive.")
    torch.set_num_threads(args.threads)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # print ✓ and ✗ on any console
            stream.reconfigure(encoding="utf-8", errors="replace")

    config = benchmark.load_config(args.config)
    if args.command in ("all", "evaluate"):
        benchmark.run(config, args.data_dir, args.models_dir, args.results_dir, args.threads,
                      train=args.command == "all")
        return 0
    data = benchmark.load_data(config, args.data_dir)
    if args.command == "train":
        benchmark.run_training(config, data, args.models_dir, args.threads)
        return 0
    benchmark.check_models(config, args.models_dir)
    gru = GRUModel.load(args.models_dir / f"gru_seed{config['model']['seeds'][0]}.pt")
    oracle = BayesOracle(benchmark.priors(config))
    test = data["test"]
    if args.command == "demo":
        from .demo import run_demo
        run_demo(test, gru, NGram(6).fit([s.events for s in data["train"]]), oracle, args.session, args.what_if)
    else:
        from .demo import pick_hero_session
        session = test[pick_hero_session(test, gru) if args.session is None else args.session]
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(hero_svg(session, gru, oracle), encoding="utf-8")
        print(f"Wrote {args.out} ({session.session_id})")
    return 0


def hero_svg(session, gru: GRUModel, oracle: BayesOracle) -> str:
    events = session.events
    beliefs = [oracle.marginals(events[:t + 1]) for t in range(1, len(events))]
    truth = {fact: bool(test(session.hidden)) for fact, test in FACTS.items()}
    return render_hero(events, gru.predict_session(events), oracle.predict_session(events), beliefs, truth)
