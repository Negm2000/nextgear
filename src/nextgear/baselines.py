"""Count-based baselines.

`NGram` sees the last few events. `StateCounts` is given domain knowledge: it rebuilds the
visible assembly with the simulator's state machine and counts what happens next in each
state. Neither sees the hidden specification or any verdict before it happens.
"""

from collections import Counter, defaultdict

import numpy as np

from .events import INDEX, VOCAB
from .simulator import State, apply, replay


def interpolate(tables) -> np.ndarray:
    """Witten-Bell interpolation, from the coarsest context to the most specific."""
    p = np.full(len(VOCAB), 1.0 / len(VOCAB))
    for counts in tables:
        if counts:
            observed = np.zeros(len(VOCAB))
            for event, c in counts.items():
                observed[INDEX[event]] = c
            p = (observed + len(counts) * p) / (sum(counts.values()) + len(counts))
    return p


class Frequency:
    """How often each event occurs overall, ignoring history."""

    name = "frequency"

    def fit(self, sequences) -> "Frequency":
        counts = Counter(e for seq in sequences for e in seq[1:])
        self.p = np.array([counts[e] + 1.0 for e in VOCAB])
        self.p /= self.p.sum()
        return self

    def predict_session(self, events) -> np.ndarray:
        return np.tile(self.p, (len(events) - 1, 1))

    def predict_many(self, sequences) -> list[np.ndarray]:
        return [self.predict_session(s) for s in sequences]

    def predict_next(self, prefixes) -> np.ndarray:
        return np.tile(self.p, (len(prefixes), 1))


class NGram:
    """Conditions on the last `context` events."""

    def __init__(self, context: int):
        if context < 1:
            raise ValueError("Context length must be at least 1.")
        self.context = context
        self.name = f"ngram_{context}"

    # @cpt-algo:cpt-nextgear-algo-predictors-ngram:p1
    def fit(self, sequences) -> "NGram":
        # @cpt-begin:cpt-nextgear-algo-predictors-ngram:p1:inst-count
        self.counts: dict[tuple[str, ...], Counter] = defaultdict(Counter)
        for seq in sequences:
            for t in range(1, len(seq)):
                for k in range(min(self.context, t) + 1):
                    self.counts[tuple(seq[t - k:t])][seq[t]] += 1
        # @cpt-end:cpt-nextgear-algo-predictors-ngram:p1:inst-count
        self._cache: dict[tuple[str, ...], np.ndarray] = {}
        return self

    def _probability(self, history) -> np.ndarray:
        history = tuple(history[-self.context:])
        if history not in self._cache:
            # @cpt-begin:cpt-nextgear-algo-predictors-ngram:p1:inst-interpolate
            self._cache[history] = interpolate(self.counts.get(history[len(history) - k:])
                                               for k in range(len(history) + 1))
            # @cpt-end:cpt-nextgear-algo-predictors-ngram:p1:inst-interpolate
        return self._cache[history]

    def predict_session(self, events) -> np.ndarray:
        return np.array([self._probability(events[:t]) for t in range(1, len(events))])

    def predict_many(self, sequences) -> list[np.ndarray]:
        return [self.predict_session(s) for s in sequences]

    def predict_next(self, prefixes) -> np.ndarray:
        return np.array([self._probability(p) for p in prefixes])


class StateCounts:
    """Counts the next event per visible assembly state, backing off to coarser states."""

    name = "state_counts"

    @staticmethod
    def _contexts(state: State) -> tuple:
        core = (state.pending, state.gear, state.path, state.outbound, state.platform, state.cache,
                state.learned_outbound, state.learned_deps)
        return ((), (state.pending, state.gear), core,
                (*core, min(state.submissions, 4), min(state.proposals // 10, 4)))

    # @cpt-algo:cpt-nextgear-algo-predictors-state-counts:p1
    def fit(self, sequences) -> "StateCounts":
        # @cpt-begin:cpt-nextgear-algo-predictors-state-counts:p1:inst-count
        self.counts: dict[tuple, Counter] = defaultdict(Counter)
        for events in sequences:
            state = apply(State(), events[0])
            for event in events[1:]:
                for level, context in enumerate(self._contexts(state)):
                    self.counts[level, context][event] += 1
                state = apply(state, event)
        # @cpt-end:cpt-nextgear-algo-predictors-state-counts:p1:inst-count
        self._cache: dict[tuple, np.ndarray] = {}
        return self

    def _probability(self, state: State) -> np.ndarray:
        contexts = self._contexts(state)
        if contexts not in self._cache:
            # @cpt-begin:cpt-nextgear-algo-predictors-state-counts:p1:inst-interpolate
            self._cache[contexts] = interpolate(self.counts.get((level, c)) for level, c in enumerate(contexts))
            # @cpt-end:cpt-nextgear-algo-predictors-state-counts:p1:inst-interpolate
        return self._cache[contexts]

    def predict_session(self, events) -> np.ndarray:
        rows, state = [], apply(State(), events[0])
        for event in events[1:]:
            rows.append(self._probability(state))
            state = apply(state, event)
        return np.array(rows)

    def predict_many(self, sequences) -> list[np.ndarray]:
        return [self.predict_session(s) for s in sequences]

    def predict_next(self, prefixes) -> np.ndarray:
        return np.array([self._probability(replay(p)) for p in prefixes])
