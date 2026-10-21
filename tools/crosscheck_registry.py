"""Compare Nextgear's dependency check with the real gears-rust registry.

Builds the Rust harness in tools/registry_check (pinned to the same gears-rust commit as
src/nextgear/fabric_gears.py), then asks it about every assembly submitted in a sample of generated
sessions and about random subsets of the sixteen gears. Exits non-zero on any disagreement.

    cargo build --release --manifest-path tools/registry_check/Cargo.toml
    python tools/crosscheck_registry.py
"""

import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nextgear.fabric_gears import DEPS as DECLARED  # noqa: E402
from nextgear.rules import CRATES, missing_dependency, present  # noqa: E402
from nextgear.simulator import Priors, State, apply, generate  # noqa: E402

HARNESS = ROOT / "tools" / "registry_check" / "target" / "release" / "registry-check"


def submitted(sessions) -> list[frozenset[str]]:
    """The assembly at every SUBMIT_ASSEMBLY in the sessions."""
    found = []
    for session in sessions:
        state = State()
        for event in session.events:
            state = apply(state, event)
            if event == "SUBMIT_ASSEMBLY":
                found.append(present(state.path, state.outbound, state.platform))
    return found


def main() -> int:
    rng = random.Random(0)
    gears = sorted(CRATES)
    assemblies = submitted(generate(2000, 99, "crosscheck", Priors()))
    assemblies += [frozenset(g for g in gears if rng.random() < rng.random()) for _ in range(20000)]
    lines = [";".join(f"{CRATES[g]}={','.join(DECLARED.get(CRATES[g], ()))}" for g in sorted(a)) for a in assemblies]
    answers = subprocess.run([str(HARNESS)], input="\n".join(lines) + "\n", capture_output=True, text=True,
                             check=True).stdout.splitlines()
    if len(answers) != len(assemblies):
        raise SystemExit("The harness did not answer every assembly.")
    expected = ["unknown-dependency" if missing_dependency(a) else "ok" for a in assemblies]
    wrong = [(sorted(a), e, r) for a, e, r in zip(assemblies, expected, answers) if e != r]
    simulated = len(assemblies) - 20000
    print(f"{len(assemblies)} assemblies: {len(assemblies) - len(wrong)} agree with the registry, {len(wrong)} disagree.")
    for name, part in (("submitted in simulated sessions", expected[:simulated]), ("random", expected[simulated:])):
        print(f"  {len(part)} {name}, of which {part.count('unknown-dependency')} have a missing dependency")
    for assembly, e, r in wrong[:10]:
        print(f"  {assembly}: Nextgear says {e}, the registry says {r}")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
