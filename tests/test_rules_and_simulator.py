"""The event vocabulary, the checks and the generator."""

import ast
import random
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nextgear.events import EVENTS, LOCAL_VERDICTS, PROPOSALS, SYSTEM_VERDICTS, TERMINALS, VOCAB
from nextgear.rules import ORDER, Spec, latency_ms, local_verdict, system_verdict
from nextgear.simulator import (CHOICES, Priors, State, apply, generate, hypotheses, next_distribution, read_sessions,
                                replay, sample_hidden, write_sessions)

SRC = Path(__file__).resolve().parents[1] / "src" / "nextgear"


class VocabularyTests(unittest.TestCase):
    def test_every_event_has_a_short_description(self):
        self.assertEqual(len(VOCAB), 24)
        for name, text in EVENTS.items():
            self.assertTrue(text.endswith("."), name)
            self.assertLess(len(text), 90, name)
        for group in (PROPOSALS, LOCAL_VERDICTS, SYSTEM_VERDICTS, TERMINALS):
            self.assertTrue(set(group) <= set(VOCAB))


class LocalCheckTests(unittest.TestCase):
    def test_request_path_follows_the_published_gears_order(self):
        # gears-rust docs/GEARS.md line 63
        chain = ["API_GATEWAY", "AUTH_RESOLVER", "POLICY_MANAGER", "LICENSE_RESOLVER", "CHAT_ENGINE",
                 "TENANT_RESOLVER", "USAGE_COLLECTOR"]
        self.assertEqual(sorted(chain, key=ORDER.get), chain)
        path = ()
        for gear in chain:
            self.assertEqual(local_verdict(path, False, gear), "STEP_ACCEPTED")
            path += (gear,)

    def test_bypass_takes_precedence_and_order_is_enforced(self):
        self.assertEqual(local_verdict(("API_GATEWAY",), False, "BILLING_LEDGER"), "BYPASS_VIOLATION")
        self.assertEqual(local_verdict((), False, "CHAT_ENGINE"), "BYPASS_VIOLATION")
        self.assertEqual(local_verdict((), False, "AUTH_RESOLVER"), "ORDER_VIOLATION")
        path = ("API_GATEWAY", "AUTH_RESOLVER", "LICENSE_RESOLVER")
        self.assertEqual(local_verdict(path, False, "POLICY_MANAGER"), "ORDER_VIOLATION")
        self.assertEqual(local_verdict(path, False, "LICENSE_RESOLVER"), "ORDER_VIOLATION")
        path += ("CHAT_ENGINE",)
        self.assertEqual(local_verdict(path, False, "BILLING_LEDGER"), "ORDER_VIOLATION")
        self.assertEqual(local_verdict(path, False, "OUTBOUND_API_GATEWAY"), "STEP_ACCEPTED")
        self.assertEqual(local_verdict(path, True, "OUTBOUND_API_GATEWAY"), "ORDER_VIOLATION")


class SystemCheckTests(unittest.TestCase):
    def setUp(self):
        self.spec = Spec("CHAT_ENGINE", policy=True, license=False, tenant=False, usage=True, budget="tight")
        self.full = ("API_GATEWAY", "AUTH_RESOLVER", "POLICY_MANAGER", "CHAT_ENGINE", "USAGE_COLLECTOR")

    def test_checks_apply_in_order_first_failure_wins(self):
        self.assertEqual(system_verdict(self.spec, self.full[:-1], False, False), "MISSING_CAPABILITY")
        self.assertEqual(system_verdict(self.spec, self.full, False, False), "EXTERNAL_CALL_VIOLATION")
        extra = self.full[:3] + ("LICENSE_RESOLVER",) + self.full[3:]
        self.assertEqual(system_verdict(self.spec, extra, True, False), "COST_VIOLATION")
        self.assertEqual(system_verdict(self.spec, self.full, True, False), "LATENCY_VIOLATION")
        self.assertEqual(system_verdict(self.spec, self.full, True, True), "LATENCY_VIOLATION")  # 63 ms > 60 ms
        self.assertEqual(system_verdict(replace(self.spec, budget="loose"), self.full, True, False),
                         "ASSEMBLY_ADMISSIBLE")
        lean = Spec("CHAT_ENGINE", policy=False, license=False, tenant=False, usage=False, budget="tight")
        path = ("API_GATEWAY", "AUTH_RESOLVER", "CHAT_ENGINE")
        self.assertEqual(system_verdict(lean, path, True, False), "LATENCY_VIOLATION")  # 61 ms
        self.assertEqual(system_verdict(lean, path, True, True), "ASSEMBLY_ADMISSIBLE")  # 57 ms

    def test_cache_halves_resolver_latency_only(self):
        self.assertEqual(latency_ms(self.full, True, False), 3 + 8 + 6 + 40 + 3 + 10)
        self.assertEqual(latency_ms(self.full, True, True), 3 + 4 + 3 + 40 + 3 + 10)


class GeneratorTests(unittest.TestCase):
    def test_generation_is_reproducible_and_complete(self):
        first, second = generate(80, 5, "train", Priors()), generate(80, 5, "train", Priors())
        self.assertEqual(first, second)
        self.assertNotEqual(first, generate(80, 6, "train", Priors()))
        for session in first:
            self.assertEqual(session.events[0], "SESSION_STARTED")
            self.assertIn(session.events[-1], TERMINALS)
            self.assertEqual(replay(session.events).pending, "done")

    def test_a_smaller_split_is_a_prefix_of_a_larger_one(self):
        self.assertEqual(generate(30, 9, "train", Priors()), generate(60, 9, "train", Priors())[:30])

    def test_transition_probabilities_are_distributions(self):
        rng, priors = random.Random(1), Priors()
        for _ in range(200):
            hidden = sample_hidden(priors, rng)
            state = apply(State(), "SESSION_STARTED")
            while state.pending != "done":
                distribution = next_distribution(hidden, state, priors)
                self.assertAlmostEqual(sum(distribution.values()), 1.0)
                state = apply(state, rng.choices(list(distribution), weights=list(distribution.values()))[0])

    def test_agent_never_intends_a_known_bypass(self):
        priors = Priors()
        hidden = sample_hidden(priors, random.Random(3))
        state = replace(apply(State(), "SESSION_STARTED"), path=("API_GATEWAY", "POLICY_MANAGER"))
        distribution = next_distribution(replace(hidden, careful=True), state, priors)
        self.assertNotEqual(max(distribution, key=distribution.get), f"ADD_{hidden.spec.execution}")
        self.assertEqual(set(distribution), set(CHOICES))

    def test_impossible_traces_are_rejected(self):
        with self.assertRaises(ValueError):
            replay(["SESSION_STARTED", "STEP_ACCEPTED"])
        with self.assertRaises(ValueError):
            replay(["SESSION_STARTED", "ADD_API_GATEWAY", "ASSEMBLY_ADMISSIBLE"])

    def test_hypothesis_priors_sum_to_one(self):
        pairs = hypotheses(Priors())
        self.assertEqual(len(pairs), 384)
        self.assertAlmostEqual(sum(p for _, p in pairs), 1.0)

    def test_round_trip_and_truncated_file(self):
        sessions = generate(10, 3, "rt", Priors())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "s.jsonl"
            write_sessions(path, sessions)
            self.assertEqual(read_sessions(path), sessions)
            lines = path.read_text(encoding="utf-8").splitlines()
            lines[0] = lines[0].replace('"ASSEMBLY_ADMISSIBLE"]', "]").replace('"SESSION_ABANDONED"]', "]")
            path.write_text("\n".join(lines).replace(", ]", "]") + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_sessions(path)

    def test_generator_does_not_import_predictors_or_evaluation(self):
        for module in ("events.py", "rules.py", "simulator.py"):
            tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
            imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
            self.assertFalse(imported & {"gru", "baselines", "oracle", "evaluation", "benchmark"}, module)


if __name__ == "__main__":
    unittest.main()
