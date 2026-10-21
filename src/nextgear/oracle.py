"""The Bayes-optimal oracle: the best any predictor can do from the events alone.

It knows the simulator's rules and priors but not the session's hidden parameters. It keeps
a posterior over all 384 hidden parameter sets and updates it with Bayes' rule after each
event, so no events-only predictor can have lower expected log loss on this data.
"""

from concurrent.futures import ProcessPoolExecutor

import numpy as np

from .events import INDEX, VOCAB
from .simulator import Priors, State, apply, depends_on_hidden, hypotheses, next_distribution


FACTS = {
    "needs the Chat Engine": lambda h: h.spec.execution == "CHAT_ENGINE",
    "needs the Billing Ledger": lambda h: h.spec.execution == "BILLING_LEDGER",
    "needs the Serverless Runtime": lambda h: h.spec.execution == "SERVERLESS_RUNTIME",
    "needs the Policy Manager": lambda h: h.spec.policy,
    "needs the License Resolver": lambda h: h.spec.license,
    "needs the Tenant Resolver": lambda h: h.spec.tenant,
    "needs the Usage Collector": lambda h: h.spec.usage,
    "has a tight latency budget": lambda h: h.spec.budget == "tight",
    "agent is careful": lambda h: h.careful,
}


# @cpt-dod:cpt-nextgear-dod-predictors-contract:p1
# @cpt-algo:cpt-nextgear-algo-predictors-oracle:p1
class BayesOracle:
    def __init__(self, priors: Priors):
        self.priors = priors
        pairs = hypotheses(priors)
        self.hidden = [h for h, _ in pairs]
        # @cpt-begin:cpt-nextgear-algo-predictors-oracle:p1:inst-prior
        self.prior = np.array([p for _, p in pairs])
        self.prior /= self.prior.sum()
        # @cpt-end:cpt-nextgear-algo-predictors-oracle:p1:inst-prior
        self._beliefs: dict[tuple[str, ...], tuple[State, np.ndarray]] = {}
        self._vectors: dict[tuple, np.ndarray] = {}

    def _vector(self, distribution: dict[str, float]) -> np.ndarray:
        key = tuple(distribution.items())
        if key not in self._vectors:
            vector = np.zeros(len(VOCAB))
            for event, p in distribution.items():
                vector[INDEX[event]] = p
            self._vectors[key] = vector
        return self._vectors[key]

    def _table(self, state: State, alive: np.ndarray) -> np.ndarray:
        """One next-event row per hypothesis still possible. System checks read only the
        specification, so hypotheses sharing a specification share a row."""
        rows, by_spec = [], {}
        for i in alive:
            key = self.hidden[i].spec if state.pending == "system" else i
            if key not in by_spec:
                by_spec[key] = self._vector(next_distribution(self.hidden[i], state, self.priors))
            rows.append(by_spec[key])
        return np.array(rows)

    def _mixture(self, state: State, weights: np.ndarray):
        """Posterior-weighted next-event distribution, plus the table needed for the update."""
        if not depends_on_hidden(state):
            return self._vector(next_distribution(self.hidden[0], state, self.priors)).copy(), None, None
        # @cpt-begin:cpt-nextgear-algo-predictors-oracle:p1:inst-mix
        alive = np.flatnonzero(weights)
        table = self._table(state, alive)
        return weights[alive] @ table, alive, table
        # @cpt-end:cpt-nextgear-algo-predictors-oracle:p1:inst-mix

    @staticmethod
    def _update(weights: np.ndarray, alive, table, event: str) -> np.ndarray:
        if alive is None:
            return weights
        # @cpt-begin:cpt-nextgear-algo-predictors-oracle:p1:inst-update
        weights = weights.copy()
        weights[alive] *= table[:, INDEX[event]]
        if weights.sum() <= 0:
            raise ValueError(f"{event} is impossible under every hidden hypothesis.")
        return weights / weights.sum()
        # @cpt-end:cpt-nextgear-algo-predictors-oracle:p1:inst-update

    def predict_session(self, events) -> np.ndarray:
        """Row t is the distribution of event t + 1 given events 0..t."""
        rows, weights, state = [], self.prior, apply(State(), events[0])
        for event in events[1:]:
            row, alive, table = self._mixture(state, weights)
            rows.append(row)
            weights, state = self._update(weights, alive, table, event), apply(state, event)
        return np.array(rows)

    def predict_many(self, sequences) -> list[np.ndarray]:
        return [self.predict_session(s) for s in sequences]

    def belief(self, events) -> tuple[State, np.ndarray]:
        """Observable state and posterior after `events`, reusing the longest cached prefix."""
        key = tuple(events)
        if not key:
            raise ValueError("A prefix must start with SESSION_STARTED.")
        k = len(key)
        while k > 1 and key[:k] not in self._beliefs:
            k -= 1
        if key[:k] in self._beliefs:
            state, weights = self._beliefs[key[:k]]
        else:
            state, weights = apply(State(), key[0]), self.prior
            self._beliefs[key[:1]] = (state, weights)
        for j in range(k, len(key)):
            _, alive, table = self._mixture(state, weights)
            weights, state = self._update(weights, alive, table, key[j]), apply(state, key[j])
            self._beliefs[key[:j + 1]] = (state, weights)
        return self._beliefs[key]

    def predict_next(self, prefixes, intervene: bool = False) -> np.ndarray:
        """Next-event distribution after each prefix.

        With `intervene=True` the last event is treated as forced, Pearl's do(): it moves
        the state but is not evidence about the hidden parameters. This is the right
        answer to "what if the agent did X here?" when the agent would not have chosen X.
        """
        rows, tables = [], {}  # what-if queries share a base prefix; build its table once
        for prefix in prefixes:
            prefix = tuple(prefix)
            if len(prefix) == 1:
                state, weights = self.belief(prefix)
            else:
                base = prefix[:-1]
                state, weights = self.belief(base)
                # @cpt-begin:cpt-nextgear-algo-predictors-oracle:p1:inst-intervene
                if not intervene:
                    if base not in tables:
                        tables[base] = self._mixture(state, weights)[1:]
                    weights = self._update(weights, *tables[base], prefix[-1])
                state = apply(state, prefix[-1])
                # @cpt-end:cpt-nextgear-algo-predictors-oracle:p1:inst-intervene
            rows.append(self._mixture(state, weights)[0])
        return np.array(rows)

    def marginals(self, events) -> dict[str, float]:
        """Posterior probability of each hidden fact in FACTS after `events`."""
        _, weights = self.belief(events)
        return {name: float(sum(w for w, h in zip(weights, self.hidden) if test(h))) for name, test in FACTS.items()}


def _predict_chunk(args) -> list[np.ndarray]:
    priors, sequences = args
    return BayesOracle(priors).predict_many(sequences)


def predict_parallel(priors: Priors, sequences, workers: int) -> list[np.ndarray]:
    """`BayesOracle(priors).predict_many(sequences)`, split across processes."""
    sequences = list(sequences)
    if workers <= 1 or len(sequences) < 100:
        return _predict_chunk((priors, sequences))
    size = -(-len(sequences) // workers)
    chunks = [(priors, sequences[i:i + size]) for i in range(0, len(sequences), size)]
    with ProcessPoolExecutor(len(chunks)) as pool:
        return [row for part in pool.map(_predict_chunk, chunks) for row in part]
