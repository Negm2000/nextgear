"""The whole pipeline on a toy configuration, then the demo and the animation."""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from nextgear import benchmark
from nextgear.baselines import Frequency, NGram
from nextgear.cli import hero_svg, main
from nextgear.demo import run_demo
from nextgear.gru import GRUModel
from nextgear.oracle import BayesOracle
from nextgear.simulator import Priors

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_all_then_demo_and_animation(self):
        config = benchmark.load_config(ROOT / "configs" / "quick.toml")
        config["data"].update(train=120, validation=40, test=40, shifted=20, holdout=15)
        config["model"].update(max_epochs=1, hidden=16, embedding=8)
        config["evaluation"].update(bootstrap_resamples=200, what_if_sessions=5)
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            dirs = root / "data", root / "models", root / "results"
            benchmark.run(config, *dirs, threads=2, train=True)
            report = json.loads((root / "results" / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["next_event"]["sessions"], 40)
            self.assertEqual(report["holdout"]["sessions"], 15)
            runs = report["holdout_sweep"]["runs"]
            self.assertEqual(len(runs), len(config["holdout"]["groups"]) * len(config["holdout"]["seeds"]))
            self.assertTrue(all(run["sessions"] == 15 and run["excluded_train"] > 0 for run in runs))
            for name in ("REPORT.md", "figures/gap.svg", "figures/unseen.svg"):
                self.assertTrue((root / "results" / name).exists(), name)

            data = benchmark.load_data(config, root / "data")
            gru = GRUModel.load(root / "models" / "gru_seed0.pt")
            oracle, ngram = BayesOracle(benchmark.priors(config)), NGram(6).fit([s.events for s in data["train"]])
            run_demo(data["test"], gru, ngram, oracle, None, None)
            with self.assertRaises(ValueError):
                run_demo(data["test"], gru, ngram, oracle, 999, None)
            session = data["test"][0]
            svg = hero_svg(session, gru, oracle)
            self.assertTrue(svg.startswith("<svg") and svg.count('class="frame') == len(session.events) - 1)

            changed = copy.deepcopy(config)
            changed["model"]["hidden"] = 32
            with self.assertRaises(ValueError):
                benchmark.check_models(changed, root / "models")

            reordered = copy.deepcopy(config)
            reordered["model"] = dict(reversed(list(config["model"].items())))
            benchmark.check_models(reordered, root / "models")

    def test_demo_refuses_a_what_if_after_the_submission_budget_is_spent(self):
        events = ("SESSION_STARTED", "SUBMIT_ASSEMBLY", "MISSING_CAPABILITY",
                  "ROLLBACK_ASSEMBLY", "SESSION_ABANDONED")
        session = SimpleNamespace(events=events, session_id="budget-exhausted")
        frequency, ngram = Frequency().fit([events]), NGram(1).fit([events])
        oracle = BayesOracle(Priors(max_submissions=1))
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "decision positions"):
            run_demo([session], frequency, ngram, oracle, 0, 4)

    def test_cli_rejects_bad_arguments(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--threads", "0", "demo"])


if __name__ == "__main__":
    unittest.main()
