# How Constructor Fabric was used

The assignment asks for a next-event predictor built using Constructor Fabric. I used [Constructor Studio](https://github.com/constructorfabric/studio), from the Fabric organization, as the development workflow. It holds the requirements, architecture decisions, design and feature specifications, and checks that they link to each other and to the code. The predictor itself is Python and PyTorch; Studio does not train models.

## Artifacts

The chain runs **PRD → ADR → DESIGN → DECOMPOSITION → FEATURE → CODE**:

- [PRD](architecture/PRD.md): the event vocabulary, simulator, prediction contract and evaluation requirements.
- [Four decisions](architecture/ADR/): the domain, the exact oracle, the GRU and the session-level bootstrap.
- [Design](architecture/DESIGN.md) and [decomposition](architecture/DECOMPOSITION.md): the information boundaries and which module owns what.
- [Four features](architecture/features/): simulator, predictors, evaluation and pipeline. Their algorithm steps map to `@cpt-` markers in the source.

For example, step 2 of the paired bootstrap in [evaluation.md](architecture/features/evaluation.md) is `inst-resample`. The code that implements it in `src/nextgear/evaluation.py` sits between `@cpt-begin:cpt-nextgear-algo-evaluation-bootstrap:p1:inst-resample` and the matching `@cpt-end` marker. If the step is renamed in the specification or its markers are deleted from the code, `cfs validate` reports an error.

The documents describe the implementation as it now stands. Several specifications were revised after code review, so they do not show that requirements were written first. The workflow was most useful in two ways. It made the information boundary and the evaluation contract explicit. It also flagged stale references whenever a module changed.

## Reproduce validation

From the repository root, in the Python environment used for Nextgear:

```sh
python -m pip install "constructor-studio @ git+https://github.com/constructorfabric/studio.git@3e73a118af4108fa45b306e02f20c9692d1bc1d6"
cfs validate
```

That commit is Studio v1.8.0. SDLC kit v1.2.1 is vendored under `.cf-studio/config/kits/sdlc/` with its Apache license and notice. The five-line root `AGENTS.md` points the CLI to `.cf-studio`, so a clean checkout needs no `cfs init`. On first use the CLI downloads its pinned skill engine. Generated IDE integrations and runtime caches are ignored by Git. CI runs validation alongside the tests and a small end-to-end experiment.

The last local check validated 11 artifacts and scanned 9 marked source files, with 21/21 traced identifiers and no errors or warnings. The behavioural suite has 33 passing tests. These are local results; hosted CI results are on GitHub.

Validation checks artifact structure, identifier links and the markers between specifications and code. The tests check the simulator, probabilities, the rule that forecasts use only earlier events, paired scoring and the pipeline. Neither shows that the authored simulator describes real Fabric systems.

## Public sources and authored assumptions

The [gear documentation at a fixed revision](https://github.com/constructorfabric/gears-rust/blob/60db50e2482d9eae1a78da6a4f6372579eb9d8e3/docs/GEARS.md) supplies the domain vocabulary. It also motivates the request-path order, mandatory authentication and outbound adapters. The [internship description](https://job-boards.eu.greenhouse.io/constructorknowledgelabs/jobs/4979107101) motivates the focus on synthetic architecture data, baseline experiments and reproducible evaluation.

The simulator's stochastic policy, requirement frequencies, verdict precedence, latency values, budget distribution and cache effects are this project's assumptions. No Rust checker, GearSpec/AppGraph implementation or private company system is reproduced. The Bayes oracle shares transition code with the generator, so it is a mathematical reference inside the simulator, not independent external validation.
