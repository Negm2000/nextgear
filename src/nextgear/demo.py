"""Replay a held-out session in the terminal: forecasts first, then what actually happened."""

import numpy as np

from .baselines import NGram
from .evaluation import step_types
from .events import ADD_EVENTS, EVENTS, INDEX, LOCAL_VERDICTS, VOCAB
from .gru import GRUModel
from .oracle import BayesOracle
from .rules import local_verdict, system_verdict
from .simulator import State, apply


def pick_session(sessions) -> int:
    """The first test session with a rejected gear, a failed system check and a happy ending."""
    for i, s in enumerate(sessions):
        events = set(s.events)
        if ({"ORDER_VIOLATION", "BYPASS_VIOLATION"} & events and "ASSEMBLY_ADMISSIBLE" in events
                and {"MISSING_CAPABILITY", "EXTERNAL_CALL_VIOLATION", "COST_VIOLATION", "LATENCY_VIOLATION"} & events
                and len(s.events) <= 24):
            return i
    return 0


SYSTEM_FAILURES = {"MISSING_CAPABILITY", "EXTERNAL_CALL_VIOLATION", "COST_VIOLATION", "LATENCY_VIOLATION"}


def pick_hero_session(sessions, gru: GRUModel) -> int:
    """A short session with a rejected gear and a failed system check that ends admissible,
    choosing the one where the GRU saw the failure coming most clearly."""
    best, best_p = 0, -1.0
    for i, s in enumerate(sessions):
        events = s.events
        failures = [t for t, e in enumerate(events) if e in SYSTEM_FAILURES]
        if not (12 <= len(events) <= 21 and events[-1] == "ASSEMBLY_ADMISSIBLE" and failures
                and {"ORDER_VIOLATION", "BYPASS_VIOLATION"} & set(events)):
            continue
        rows = gru.predict_session(events)
        p = min(rows[t - 1][INDEX[events[t]]] for t in failures)
        if p > best_p:
            best, best_p = i, p
    return best


def _mark(row: np.ndarray, event: str) -> str:
    return "✓" if int(np.argmax(row)) == INDEX[event] else "✗"


# @cpt-flow:cpt-nextgear-flow-pipeline-demo:p1
def run_demo(test, gru: GRUModel, ngram: NGram, oracle: BayesOracle, index: int | None,
             what_if_at: int | None) -> None:
    if index is None:
        index = pick_session(test)
    if not 0 <= index < len(test):
        raise ValueError(f"--session must be between 0 and {len(test) - 1}.")
    session = test[index]
    events = session.events
    learned, counted, best = gru.predict_session(events), ngram.predict_session(events), oracle.predict_session(events)
    types = step_types(events)
    print(f"Test session {index} ({session.session_id}). The models see only the events; the agent's "
          "specification is hidden from them.\n")
    print(f"{'':>4}{'what happened':<27}{'GRU top guess, before it happened':<36}"
          f"{'P(what happened):':<18}")
    print(f"{'':>67}{'GRU':>6}{'n-gram':>8}{'oracle':>8}")
    # @cpt-begin:cpt-nextgear-flow-pipeline-demo:p1:inst-replay
    for t, event in enumerate(events[1:]):
        if types[t] == "bookkeeping":
            print(f"{t + 1:>3} {event:<27}(routine step)")
            continue
        guess = int(np.argmax(learned[t]))
        print(f"{t + 1:>3} {event:<27}{_mark(learned[t], event)} {VOCAB[guess]:<26}{learned[t][guess]:>5.2f}   "
              f"{learned[t][INDEX[event]]:>6.2f}{counted[t][INDEX[event]]:>8.2f}{best[t][INDEX[event]]:>8.2f}")
    # @cpt-end:cpt-nextgear-flow-pipeline-demo:p1:inst-replay
    print(f"\nThe session ends with {events[-1]}: {EVENTS[events[-1]]}")

    # @cpt-begin:cpt-nextgear-flow-pipeline-demo:p1:inst-what-if
    decisions, state = {}, apply(State(), events[0])
    for t, event in enumerate(events[1:], start=1):
        if (state.pending == "decide" and state.proposals < oracle.priors.max_proposals
                and state.submissions < oracle.priors.max_submissions):
            decisions[t] = state
        state = apply(state, event)
    if what_if_at is None:
        what_if_at = sorted(decisions)[len(decisions) // 2]
    if what_if_at not in decisions:
        raise ValueError(f"--what-if must be one of the decision positions {sorted(decisions)}.")
    state, prefix = decisions[what_if_at], events[:what_if_at]
    print(f"\nWhat if, at step {what_if_at}, the agent had not done {events[what_if_at]}?")
    print("The oracle's belief about the hidden specification at that point:")
    for fact, p in oracle.marginals(prefix).items():
        print(f"  {p:4.0%}  {fact}")
    print(f"\n  {'if the agent proposed':<28}{'GRU predicts':<28}checks say")
    rows = gru.predict_next([prefix + (add,) for add in ADD_EVENTS])
    for (add, gear), row in zip(ADD_EVENTS.items(), rows):
        verdicts = {v: row[INDEX[v]] for v in LOCAL_VERDICTS}
        guess = max(verdicts, key=verdicts.get)
        truth = local_verdict(state.path, state.outbound, gear)
        print(f"  {add:<28}{guess:<18}{verdicts[guess]:.2f}{'':<6}{truth} {'✓' if guess == truth else '✗'}")
    submit = prefix + ("SUBMIT_ASSEMBLY",)
    admissible = INDEX["ASSEMBLY_ADMISSIBLE"]
    print(f"  {'SUBMIT_ASSEMBLY':<28}P(pass): GRU {gru.predict_next([submit])[0][admissible]:.2f}, oracle with do() "
          f"{oracle.predict_next([submit], intervene=True)[0][admissible]:.2f}; checks say "
          f"{system_verdict(session.hidden.spec, state.path, state.outbound, state.cache)}")
    # @cpt-end:cpt-nextgear-flow-pipeline-demo:p1:inst-what-if
