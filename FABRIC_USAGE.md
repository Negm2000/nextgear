# How Constructor Fabric was used

The assignment asks for a next-event predictor built using Constructor Fabric. I used [Constructor Studio](https://github.com/constructorfabric/studio) from the Fabric organization to structure and validate the software: requirements, architecture decisions, design, feature specifications and code traceability. The predictor itself runs in Python/PyTorch; Studio is the development workflow, not a model-training library.

## Artifacts

The chain is **PRD → ADR → DESIGN → DECOMPOSITION → FEATURE → CODE**:

- [PRD](architecture/PRD.md): event vocabulary, simulator, prediction contract and evaluation requirements.
- [Four decisions](architecture/ADR/): domain, exact oracle, GRU and session-level bootstrap.
- [Design](architecture/DESIGN.md) and [decomposition](architecture/DECOMPOSITION.md): information boundaries and module ownership.
- [Four features](architecture/features/): simulator, predictors, evaluation and pipeline, with algorithm steps mapped to `@cpt-` markers in source.

The exercise used Studio's SDLC kit to keep those artifacts consistent while the implementation was simplified. Several specifications were revised after code review; their presence does not prove a requirements-first chronology. The most useful pressure from the workflow was making the information boundary and evaluation contract explicit, then finding stale references when modules changed.

## Reproduce validation

From the repository root, in the Python environment used for Nextgear:

```sh
python -m pip install "constructor-studio @ git+https://github.com/constructorfabric/studio.git@3e73a118af4108fa45b306e02f20c9692d1bc1d6"
cfs validate
```

The Studio reference resolves to v1.8.0. SDLC kit v1.2.1 is vendored under `.cf-studio/config/kits/sdlc/` with its Apache license and notice. The five-line root `AGENTS.md` registers the `.cf-studio` directory for discovery on a clean checkout. Larger generated IDE integrations and runtime caches are ignored. The CLI downloads its pinned skill engine on first use; no full `cfs init` is needed. CI runs validation as well as tests and a small end-to-end experiment.

The final local check validates 11 artifacts and scans 9 marked source files: 21/21 traced identifiers, zero errors and zero warnings. The behavioral suite contains 33 passing tests. This records local evidence; hosted CI is shown separately on GitHub.

Validation checks artifact structure, identifier links and specification-to-code markers. Tests separately check the simulator, probabilities, causal prefix contract, paired scoring and pipeline. Neither check establishes that the authored simulator describes real Fabric systems.

## Public sources and authored assumptions

[Gear documentation at a fixed revision](https://github.com/constructorfabric/gears-rust/blob/60db50e2482d9eae1a78da6a4f6372579eb9d8e3/docs/GEARS.md) supplies the domain vocabulary and motivates request-path ordering, authentication and outbound adapters. The [internship description](https://job-boards.eu.greenhouse.io/constructorknowledgelabs/jobs/4979107101) motivates synthetic architecture data, baseline experiments and reproducible evaluation.

The simulator's stochastic policy, requirement frequencies, verdict precedence, latency values, budget distribution and cache effects are this project's assumptions. No Rust checker, GearSpec/AppGraph implementation or private company system is reproduced. The Bayes oracle shares transition code with the generator, so it is an internal mathematical reference rather than independent external validation.
