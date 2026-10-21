"""Predictors, the oracle, the information boundary and the statistics."""

import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest import mock

import numpy as np

from nextgear.baselines import Frequency, NGram, StateCounts
from nextgear.evaluation import (calibration, in_group, in_holdout_group, paired_bootstrap, score, step_types, subset, summarize,
                                 what_if)
from nextgear.events import INDEX, VOCAB
from nextgear.gru import GRUModel
from nextgear.oracle import BayesOracle, predict_parallel
from nextgear.rules import Spec
from nextgear.simulator import Priors, generate


class Shared:
    priors = Priors()
    train = generate(300, 11, "train", priors)
    validation = generate(60, 12, "validation", priors)
    test = generate(60, 13, "test", priors)
    events = [s.events for s in train]


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.oracle = BayesOracle(Shared.priors)

    def test_rows_are_distributions_that_never_rule_out_what_happened(self):
        for session in Shared.test[:20]:
            rows = self.oracle.predict_session(session.events)
            self.assertTrue(np.allclose(rows.sum(axis=1), 1))
            actual = [INDEX[e] for e in session.events[1:]]
            self.assertTrue((rows[np.arange(len(actual)), actual] > 0).all())

    def test_oracle_beats_the_count_baselines(self):
        events = [s.events for s in Shared.test]
        reference = score(Shared.test, self.oracle.predict_many(events))
        for model in (NGram(6).fit(Shared.events), StateCounts().fit(Shared.events)):
            self.assertLess(reference["loss"].mean(), score(Shared.test, model.predict_many(events))["loss"].mean())

    def test_prefix_queries_match_a_full_pass_including_the_first_event(self):
        session = Shared.test[0]
        full = self.oracle.predict_session(session.events)
        for t in range(len(session.events) - 1):
            np.testing.assert_allclose(self.oracle.predict_next([session.events[:t + 1]])[0], full[t])
        with self.assertRaises(ValueError):
            self.oracle.predict_next([()])

    def test_parallel_prediction_matches_serial(self):
        # Below 100 sequences predict_parallel falls back to serial, so use enough to reach the process pool.
        events = [s.events for s in generate(120, 14, "parallel", Shared.priors)]
        serial = self.oracle.predict_many(events)
        with mock.patch("nextgear.oracle.ProcessPoolExecutor", wraps=ProcessPoolExecutor) as pool:
            parallel = predict_parallel(Shared.priors, events, workers=2)
        pool.assert_called_once()
        self.assertEqual(len(serial), len(parallel))
        for a, b in zip(serial, parallel):
            np.testing.assert_allclose(a, b)

    def test_forcing_an_action_changes_beliefs_only_where_hidden_values_matter(self):
        session = Shared.test[0]
        prefix = session.events[:1] + ("ADD_API_GATEWAY",)
        np.testing.assert_allclose(self.oracle.predict_next([prefix])[0],
                                   self.oracle.predict_next([prefix], intervene=True)[0])
        beliefs = self.oracle.marginals(session.events[:5])
        self.assertAlmostEqual(sum(v for k, v in beliefs.items() if k.split()[-2:] in
                                   (["Chat", "Engine"], ["Billing", "Ledger"], ["Serverless", "Runtime"])), 1.0)


class LearnedAndBaselineTests(unittest.TestCase):
    def test_gru_rows_are_distributions_and_checkpoints_round_trip(self):
        model = GRUModel(hidden=16, embedding=8, max_epochs=2, seed=0).fit(Shared.events,
                                                                          [s.events for s in Shared.validation])
        events = Shared.test[0].events
        rows = model.predict_session(events)
        self.assertEqual(rows.shape, (len(events) - 1, len(VOCAB)))
        self.assertTrue(np.allclose(rows.sum(axis=1), 1, atol=1e-5))
        with tempfile.TemporaryDirectory() as directory:
            model.save(Path(directory) / "m.pt")
            np.testing.assert_allclose(GRUModel.load(Path(directory) / "m.pt").predict_session(events), rows)
        np.testing.assert_allclose(model.predict_next([events[:4]])[0], rows[3], atol=1e-6)

    def test_baselines_are_strictly_positive_distributions(self):
        for model in (Frequency().fit(Shared.events), NGram(1).fit(Shared.events), NGram(6).fit(Shared.events),
                      StateCounts().fit(Shared.events)):
            rows = model.predict_session(Shared.test[0].events)
            self.assertTrue(np.allclose(rows.sum(axis=1), 1))
            self.assertTrue((rows > 0).all())

    def test_state_counts_read_only_the_prefix(self):
        model = StateCounts().fit(Shared.events)
        events = Shared.test[1].events
        rows = model.predict_session(events)
        for t in range(1, len(events)):
            np.testing.assert_allclose(model.predict_next([events[:t]])[0], rows[t - 1])

    def test_predictors_never_see_hidden_values(self):
        session = Shared.test[0]
        other = replace(session, hidden=replace(session.hidden, careful=not session.hidden.careful,
                                                knows_deps=not session.hidden.knows_deps,
                                                spec=Spec("BILLING_LEDGER", False, False, False, "loose")))
        for model in (NGram(3).fit(Shared.events), StateCounts().fit(Shared.events)):
            np.testing.assert_array_equal(model.predict_session(session.events), model.predict_session(other.events))


class StatisticsTests(unittest.TestCase):
    def setUp(self):
        events = [s.events for s in Shared.test]
        self.ngram = score(Shared.test, NGram(3).fit(Shared.events).predict_many(events))
        self.frequency = score(Shared.test, Frequency().fit(Shared.events).predict_many(events))

    def test_step_types_label_every_prediction(self):
        types = step_types(Shared.test[0].events)
        self.assertEqual(len(types), len(Shared.test[0].events) - 1)
        self.assertEqual(types[0], "decision")

    def test_paired_bootstrap_identity_and_sign(self):
        same = paired_bootstrap(self.ngram, self.ngram, resamples=200, seed=0)
        self.assertEqual(same["difference"], 0.0)
        self.assertEqual(same["ci95"], [0.0, 0.0])
        better = paired_bootstrap(self.ngram, self.frequency, resamples=200, seed=0)
        self.assertLess(better["ci95"][1], 0)
        self.assertAlmostEqual(better["difference"], self.ngram["loss"].mean() - self.frequency["loss"].mean())
        self.assertIn("excess", summarize(self.frequency, self.ngram)["all"])

    def test_bootstrap_refuses_scores_for_different_events(self):
        other = {k: v.copy() for k, v in self.ngram.items()}
        other["key"][0] = "another-session:1"
        with self.assertRaises(ValueError):
            paired_bootstrap(self.ngram, other, resamples=200, seed=0)

    def test_score_refuses_missing_or_invalid_predictions(self):
        rows = Frequency().fit(Shared.events).predict_many([s.events for s in Shared.test])
        with self.assertRaises(ValueError):
            score(Shared.test, rows[:-1])
        for value in (float("nan"), -0.1, 2.0):
            broken = [r.copy() for r in rows]
            broken[0][0, 0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                score(Shared.test, broken)

    def test_subset_keeps_only_the_chosen_sessions(self):
        part = subset(self.ngram, np.array([3, 7]))
        self.assertEqual(set(part["session"]), {0, 1})
        self.assertEqual(len(part["loss"]), len(Shared.test[3].events) + len(Shared.test[7].events) - 2)

    def test_calibration_is_zero_for_a_calibrated_input(self):
        scored = {"confidence": np.array([0.9] * 10 + [0.6] * 10), "top1": np.array([1] * 9 + [0] + [1] * 6 + [0] * 4),
                  "type": np.array(["decision"] * 20)}
        self.assertAlmostEqual(calibration(scored, bins=10)["ece"], 0.0)

    def test_oracle_with_do_knows_every_local_verdict(self):
        oracle = BayesOracle(Shared.priors)
        result = what_if({"oracle": oracle}, Shared.test[:5], Shared.priors, interventional=oracle)
        self.assertEqual(result["models"]["oracle"]["unchosen_local_accuracy"], 1.0)
        self.assertEqual(result["models"]["oracle_do"]["unchosen_local_accuracy"], 1.0)
        self.assertGreater(result["unchosen_local_queries"], 0)

    def test_groups_select_the_execution_gear_and_both_flags(self):
        sessions = generate(500, 94, "source", Priors())
        group = ("BILLING_LEDGER", "policy", "usage")
        held = [s for s in sessions if in_group(s, group)]
        self.assertTrue(0 < len(held) < len(sessions))
        for s in sessions:
            spec = s.hidden.spec
            self.assertEqual(in_group(s, group), spec.execution == "BILLING_LEDGER" and spec.policy and spec.usage)

    def test_holdout_group_is_a_strict_partition(self):
        sessions = generate(500, 93, "source", Priors())
        held = [s for s in sessions if in_holdout_group(s)]
        self.assertTrue(0 < len(held) < len(sessions))
        for s in held:
            self.assertEqual((s.hidden.spec.execution, s.hidden.spec.policy, s.hidden.spec.license),
                             ("CHAT_ENGINE", True, True))


if __name__ == "__main__":
    unittest.main()
