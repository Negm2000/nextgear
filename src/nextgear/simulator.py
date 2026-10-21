"""The session generator.

`next_distribution` gives the probability of every next event from a session's hidden
parameters and its observable state. The generator samples from it and the oracle averages
it over every possible hidden parameter set, so the two can never disagree.
"""

import itertools
import json
import random
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .events import ADD_EVENTS, LOCAL_VERDICTS, SYSTEM_VERDICTS, VOCAB
from .rules import EXECUTION_GEARS, ORDER, OUTBOUND, Spec, local_verdict, system_verdict

EXECUTIONS: tuple[str, ...] = ("CHAT_ENGINE", "BILLING_LEDGER", "SERVERLESS_RUNTIME")
CHOICES: tuple[str, ...] = (*ADD_EVENTS, "SUBMIT_ASSEMBLY")


@dataclass(frozen=True)
class Priors:
    """How hidden parameters are drawn and how the agent behaves."""

    execution_weights: tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3)
    p_policy: float = 0.5
    p_license: float = 0.5
    p_tenant: float = 0.5
    p_usage: float = 0.5
    p_tight_budget: float = 0.35
    p_careful: float = 0.5
    mistake_careful: float = 0.05
    mistake_sloppy: float = 0.25
    knows_outbound_careful: float = 0.9
    knows_outbound_sloppy: float = 0.3
    max_proposals: int = 40
    max_submissions: int = 4

    def __post_init__(self):
        probabilities = [self.p_policy, self.p_license, self.p_tenant, self.p_usage, self.p_tight_budget,
                         self.p_careful, self.knows_outbound_careful, self.knows_outbound_sloppy, *self.execution_weights]
        if any(not 0 <= p <= 1 for p in probabilities) or abs(sum(self.execution_weights) - 1) > 1e-9:
            raise ValueError("Priors must be probabilities and execution weights must sum to 1.")
        if not 0 < self.mistake_careful < 1 or not 0 < self.mistake_sloppy < 1:
            raise ValueError("Mistake rates must be strictly between 0 and 1.")
        if self.max_proposals < 1 or self.max_submissions < 1:
            raise ValueError("Budgets must be positive.")

    @classmethod
    def from_dict(cls, data: dict) -> "Priors":
        data = dict(data)
        if "execution_weights" in data:
            data["execution_weights"] = tuple(data["execution_weights"])
        return cls(**data)


@dataclass(frozen=True)
class Hidden:
    """Per-session parameters that only the oracle and the checks may read."""

    spec: Spec
    careful: bool
    knows_outbound: bool


@dataclass(frozen=True)
class State:
    """Everything an observer can reconstruct from the events so far."""

    path: tuple[str, ...] = ()
    outbound: bool = False
    cache: bool = False
    learned_outbound: bool = False
    proposals: int = 0
    submissions: int = 0
    pending: str = "start"  # start | decide | local | revert | system | rollback | latency | done
    gear: str | None = None


ALLOWED: dict[str, frozenset[str]] = {
    "start": frozenset({"SESSION_STARTED"}),
    "decide": frozenset(CHOICES) | {"SESSION_ABANDONED"},
    "local": frozenset(LOCAL_VERDICTS),
    "revert": frozenset({"STEP_REVERTED"}),
    "system": frozenset(SYSTEM_VERDICTS),
    "rollback": frozenset({"ROLLBACK_ASSEMBLY"}),
    "latency": frozenset({"ENABLE_RESOLVER_CACHE", "SESSION_ABANDONED"}),
    "done": frozenset(),
}
AFTER_SYSTEM_CHECK: dict[str, str] = {
    "ASSEMBLY_ADMISSIBLE": "done", "MISSING_CAPABILITY": "rollback", "COST_VIOLATION": "rollback",
    "EXTERNAL_CALL_VIOLATION": "decide", "LATENCY_VIOLATION": "latency",
}


# @cpt-state:cpt-nextgear-state-simulator-session:p1
def apply(state: State, event: str) -> State:
    """Advance the observable state by one event; reject events that cannot happen here."""
    if event not in ALLOWED[state.pending]:
        raise ValueError(f"{event} cannot follow pending step '{state.pending}'.")
    pending = state.pending
    # @cpt-begin:cpt-nextgear-state-simulator-session:p1:inst-start
    if pending == "start":
        return replace(state, pending="decide")
    # @cpt-end:cpt-nextgear-state-simulator-session:p1:inst-start
    # @cpt-begin:cpt-nextgear-state-simulator-session:p1:inst-decide
    if pending == "decide":
        if event == "SESSION_ABANDONED":
            return replace(state, pending="done")
        if event == "SUBMIT_ASSEMBLY":
            return replace(state, proposals=state.proposals + 1, submissions=state.submissions + 1, pending="system")
        return replace(state, proposals=state.proposals + 1, pending="local", gear=ADD_EVENTS[event])
    # @cpt-end:cpt-nextgear-state-simulator-session:p1:inst-decide
    # @cpt-begin:cpt-nextgear-state-simulator-session:p1:inst-local
    if pending == "local":
        if event != "STEP_ACCEPTED":
            return replace(state, pending="revert")
        if state.gear == OUTBOUND:
            return replace(state, outbound=True, pending="decide", gear=None)
        return replace(state, path=state.path + (state.gear,), pending="decide", gear=None)
    # @cpt-end:cpt-nextgear-state-simulator-session:p1:inst-local
    # @cpt-begin:cpt-nextgear-state-simulator-session:p1:inst-revert
    if pending == "revert":
        return replace(state, pending="decide", gear=None)
    # @cpt-end:cpt-nextgear-state-simulator-session:p1:inst-revert
    # @cpt-begin:cpt-nextgear-state-simulator-session:p1:inst-system
    if pending == "system":
        learned = state.learned_outbound or event == "EXTERNAL_CALL_VIOLATION"
        return replace(state, pending=AFTER_SYSTEM_CHECK[event], learned_outbound=learned)
    # @cpt-end:cpt-nextgear-state-simulator-session:p1:inst-system
    # @cpt-begin:cpt-nextgear-state-simulator-session:p1:inst-rollback
    if pending == "rollback":
        return replace(state, path=(), outbound=False, pending="decide")
    # @cpt-end:cpt-nextgear-state-simulator-session:p1:inst-rollback
    # @cpt-begin:cpt-nextgear-state-simulator-session:p1:inst-latency
    if event == "ENABLE_RESOLVER_CACHE":
        return replace(state, cache=True, pending="decide")
    return replace(state, pending="done")
    # @cpt-end:cpt-nextgear-state-simulator-session:p1:inst-latency


def replay(events) -> State:
    state = State()
    for event in events:
        state = apply(state, event)
    return state


def intended_step(hidden: Hidden, state: State) -> str:
    """What the agent means to do: add the next required gear it can append, add the
    outbound gateway if it knows it is needed, otherwise submit."""
    last = ORDER[state.path[-1]] if state.path else -1
    for gear in hidden.spec.required_path():
        bypass = gear in EXECUTION_GEARS and "AUTH_RESOLVER" not in state.path
        if gear not in state.path and ORDER[gear] > last and not bypass:
            return f"ADD_{gear}"
    knows_outbound = hidden.knows_outbound or state.learned_outbound
    if hidden.spec.needs_outbound() and knows_outbound and not state.outbound:
        return f"ADD_{OUTBOUND}"
    return "SUBMIT_ASSEMBLY"


# @cpt-algo:cpt-nextgear-algo-simulator-next-event:p1
def next_distribution(hidden: Hidden, state: State, priors: Priors) -> dict[str, float]:
    """Probability of each possible next event. Only the agent's decisions are random."""
    pending = state.pending
    if pending == "decide":
        # @cpt-begin:cpt-nextgear-algo-simulator-next-event:p1:inst-budget
        if state.proposals >= priors.max_proposals or state.submissions >= priors.max_submissions:
            return {"SESSION_ABANDONED": 1.0}
        # @cpt-end:cpt-nextgear-algo-simulator-next-event:p1:inst-budget
        # @cpt-begin:cpt-nextgear-algo-simulator-next-event:p1:inst-agent
        mistake = priors.mistake_careful if hidden.careful else priors.mistake_sloppy
        distribution = dict.fromkeys(CHOICES, mistake / (len(CHOICES) - 1))
        distribution[intended_step(hidden, state)] = 1.0 - mistake
        return distribution
        # @cpt-end:cpt-nextgear-algo-simulator-next-event:p1:inst-agent
    # @cpt-begin:cpt-nextgear-algo-simulator-next-event:p1:inst-checks
    if pending == "local":
        return {local_verdict(state.path, state.outbound, state.gear): 1.0}
    if pending == "system":
        return {system_verdict(hidden.spec, state.path, state.outbound, state.cache): 1.0}
    if pending == "revert":
        return {"STEP_REVERTED": 1.0}
    if pending == "rollback":
        return {"ROLLBACK_ASSEMBLY": 1.0}
    if pending == "latency":
        return {"SESSION_ABANDONED" if state.cache else "ENABLE_RESOLVER_CACHE": 1.0}
    # @cpt-end:cpt-nextgear-algo-simulator-next-event:p1:inst-checks
    raise ValueError(f"No event can follow pending step '{pending}'.")


def depends_on_hidden(state: State) -> bool:
    """Only agent decisions and system checks depend on what the observer cannot see."""
    return state.pending in ("decide", "system")


def sample_hidden(priors: Priors, rng: random.Random) -> Hidden:
    spec = Spec(
        execution=rng.choices(EXECUTIONS, weights=priors.execution_weights)[0],
        policy=rng.random() < priors.p_policy,
        license=rng.random() < priors.p_license,
        tenant=rng.random() < priors.p_tenant,
        usage=rng.random() < priors.p_usage,
        budget="tight" if rng.random() < priors.p_tight_budget else "loose",
    )
    careful = rng.random() < priors.p_careful
    knows = rng.random() < (priors.knows_outbound_careful if careful else priors.knows_outbound_sloppy)
    return Hidden(spec, careful, knows)


def hypotheses(priors: Priors) -> list[tuple[Hidden, float]]:
    """Every possible hidden parameter set (3 x 2^7 = 384) with its prior probability."""
    def bern(p: float, value: bool) -> float:
        return p if value else 1 - p

    result = []
    for execution, weight in zip(EXECUTIONS, priors.execution_weights):
        for policy, license_, tenant, usage, careful, knows, tight in itertools.product((False, True), repeat=7):
            knows_p = priors.knows_outbound_careful if careful else priors.knows_outbound_sloppy
            p = (weight * bern(priors.p_policy, policy) * bern(priors.p_license, license_)
                 * bern(priors.p_tenant, tenant) * bern(priors.p_usage, usage) * bern(priors.p_tight_budget, tight)
                 * bern(priors.p_careful, careful) * bern(knows_p, knows))
            if p > 0:
                spec = Spec(execution, policy, license_, tenant, usage, "tight" if tight else "loose")
                result.append((Hidden(spec, careful, knows), p))
    return result


def simulate(hidden: Hidden, priors: Priors, rng: random.Random) -> list[str]:
    events, state = ["SESSION_STARTED"], apply(State(), "SESSION_STARTED")
    while state.pending != "done":
        distribution = next_distribution(hidden, state, priors)
        event = rng.choices(list(distribution), weights=list(distribution.values()))[0]
        events.append(event)
        state = apply(state, event)
    return events


@dataclass(frozen=True)
class Session:
    session_id: str
    events: tuple[str, ...]
    hidden: Hidden


# @cpt-dod:cpt-nextgear-dod-simulator-sessions:p1
# @cpt-algo:cpt-nextgear-algo-simulator-generate:p1
def generate(count: int, seed: int, split: str, priors: Priors) -> list[Session]:
    """`count` independent sessions; the first k sessions do not depend on `count`."""
    if count < 1:
        raise ValueError("Session count must be positive.")
    # @cpt-begin:cpt-nextgear-algo-simulator-generate:p1:inst-seed
    split_rng = random.Random(seed)
    rngs = [random.Random(split_rng.getrandbits(64)) for _ in range(count)]
    # @cpt-end:cpt-nextgear-algo-simulator-generate:p1:inst-seed
    sessions = []
    for i, rng in enumerate(rngs):
        # @cpt-begin:cpt-nextgear-algo-simulator-generate:p1:inst-simulate
        hidden = sample_hidden(priors, rng)
        sessions.append(Session(f"{split}-{i:05d}", tuple(simulate(hidden, priors, rng)), hidden))
        # @cpt-end:cpt-nextgear-algo-simulator-generate:p1:inst-simulate
    return sessions


def write_sessions(path: Path, sessions: list[Session]) -> None:
    # @cpt-begin:cpt-nextgear-algo-simulator-generate:p1:inst-write
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for s in sessions:
            stream.write(json.dumps({"session_id": s.session_id, "events": list(s.events),
                                     "hidden": asdict(s.hidden)}) + "\n")
    # @cpt-end:cpt-nextgear-algo-simulator-generate:p1:inst-write


def read_sessions(path: Path) -> list[Session]:
    sessions = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            data = json.loads(line)
            hidden = data["hidden"]
            session = Session(data["session_id"], tuple(data["events"]),
                              Hidden(Spec(**hidden["spec"]), hidden["careful"], hidden["knows_outbound"]))
            if any(e not in VOCAB for e in session.events) or replay(session.events).pending != "done":
                raise ValueError(f"Session {session.session_id} in {path} is not a complete, valid trace.")
            sessions.append(session)
    if not sessions:
        raise ValueError(f"{path} contains no sessions.")
    return sessions
