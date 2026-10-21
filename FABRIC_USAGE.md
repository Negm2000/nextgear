# How Constructor Fabric was used

Two parts of Constructor Fabric are built into this project:

- **Gears** supplies the domain. The simulator's gears, their request order and every dependency between them come from [constructorfabric/gears-rust](https://github.com/constructorfabric/gears-rust) at a pinned commit. The dependency rule has been checked against the toolkit's real registry.
- **[Studio](https://github.com/constructorfabric/studio)** is the development workflow. It holds the requirements, architecture decisions, design and feature specifications, and checks that they link to each other and to the code.

The predictor itself is Python and PyTorch; neither part of Fabric trains models.

## Gears: where the simulator's rules come from

Every gear in gears-rust declares the gears it depends on, for example `#[toolkit::gear(name = "oagw", deps = [types_registry, authz_resolver, credstore, tenant_resolver])]`. When an application is assembled, the toolkit's `RegistryBuilder::build_topo_sorted` rejects it with `RegistryError::UnknownDependency` if a declared dependency is absent. Nextgear's system check applies the same rule and reports it as `MISSING_DEPENDENCY`.

[`tools/extract_gears.py`](tools/extract_gears.py) reads those declarations at commit `fc765fe` for the ten gears the agent assembles and everything they depend on. It writes them to [`src/nextgear/fabric_gears.py`](src/nextgear/fabric_gears.py). Six platform gears join the vocabulary because the declarations require them: gRPC Hub, Types Registry, Authorization Resolver, Credentials Store, Account Manager and Resource Group. The graph shapes the data directly:

- The outbound gateway depends on the Credentials Store.
- The Billing Ledger depends on the Account Manager and, through it, on the Resource Group.
- The outbound gateway, the Billing Ledger and the Policy Manager all depend on the Tenant Resolver, so every valid assembly needs it.
- Serverless Runtime has no gear declaration at this commit, so it has no dependencies.

To check the rule against the real implementation, [`tools/registry_check`](tools/registry_check/src/main.rs) is a small Rust program. It depends on the toolkit at the same commit and asks the real registry about each assembly it is given. [`tools/crosscheck_registry.py`](tools/crosscheck_registry.py) sends it 24,910 assemblies: the 4,910 submitted in 2,000 simulated sessions, 1,544 of which have a missing dependency, and 20,000 random subsets of the sixteen gears. The registry and Nextgear agree on all of them.

```sh
git clone https://github.com/constructorfabric/gears-rust && git -C gears-rust checkout fc765feb8e328ae31c44bfb3a0c981b42e32a105
python tools/extract_gears.py gears-rust          # regenerates src/nextgear/fabric_gears.py
cargo build --release --manifest-path tools/registry_check/Cargo.toml
python tools/crosscheck_registry.py
```

The same commit's [`docs/GEARS.md`](https://github.com/constructorfabric/gears-rust/blob/fc765feb8e328ae31c44bfb3a0c981b42e32a105/docs/GEARS.md) supplies the rest of the domain:

- the request order "API Gateway → Auth Resolver → Policy Manager → License Resolver → Execution Gear → Tenant Resolver → Audit / Usage Collector" (line 63);
- "bypassing middlewares is not permitted" (line 49);
- "only integration/adapters talk to external components" (line 52).

Matching the documented names to crates is my reading of the gear descriptions. Auth Resolver, which validates tokens, is `authn-resolver`; Policy Manager, which manages authorization policies, is `policy-engine`; Outbound API Gateway is `oagw`.

Everything else is this project's assumption:

- the agent's stochastic policy;
- the requirement frequencies;
- which system check runs first;
- the latency values, budgets and cache effects.

No production gear runs here, and no GearSpec/AppGraph implementation or private company system is reproduced. The Bayes oracle shares transition code with the generator, so it is a mathematical reference inside the simulator, not independent validation.

## Studio: how the project is specified and checked

The chain runs **PRD → ADR → DESIGN → DECOMPOSITION → FEATURE → CODE**:

- [PRD](architecture/PRD.md): the event vocabulary, simulator, prediction contract and evaluation requirements.
- [Five decisions](architecture/ADR/): the domain, the exact oracle, the GRU, the session-level bootstrap, and taking dependencies from gears-rust.
- [Design](architecture/DESIGN.md) and [decomposition](architecture/DECOMPOSITION.md): the information boundaries and which module owns what.
- [Four features](architecture/features/): simulator, predictors, evaluation and pipeline. Their algorithm steps map to `@cpt-` markers in the source.

The switch to the gears-rust dependencies went through that chain:

- [ADR 0005](architecture/ADR/0005-fabric-dependencies-v1.md) records the decision.
- The PRD's check requirement now names the gears-rust declarations and the registry cross-check.
- The simulator specification gained a step, `inst-dependencies`. Its code sits between `@cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-dependencies` and the matching `@cpt-end` marker in `src/nextgear/rules.py`.

If a step is renamed in a specification or its markers are deleted from the code, `cfs validate` reports an error.

The documents describe the implementation as it now stands. Several specifications were revised after code review, so they do not show that requirements were written first. The workflow was most useful in two ways. It made the information boundary and the evaluation contract explicit. It also flagged stale references whenever a module changed.

From the repository root, in the Python environment used for Nextgear:

```sh
python -m pip install "constructor-studio @ git+https://github.com/constructorfabric/studio.git@3e73a118af4108fa45b306e02f20c9692d1bc1d6"
cfs validate
```

- **Versions.** That commit is Studio v1.8.0. SDLC kit v1.2.1 is vendored under `.cf-studio/config/kits/sdlc/` with its Apache license and notice.
- **Setup.** The five-line root `AGENTS.md` points the CLI to `.cf-studio`, so a clean checkout needs no `cfs init`. On first use the CLI downloads its pinned skill engine. Generated IDE integrations and runtime caches are ignored by Git.
- **CI.** Validation runs alongside the tests and a small end-to-end experiment.

The last local check validated ARTIFACTS artifacts and scanned 9 marked source files, with COVERAGE traced identifiers and no errors or warnings. The behavioural suite has TESTS passing tests. These are local results; hosted CI results are on GitHub.

Validation checks artifact structure, identifier links and the markers between specifications and code. The tests check the simulator, the extracted dependencies, probabilities, the rule that forecasts use only earlier events, paired scoring and the pipeline. Neither shows that the authored parts of the simulator describe real Fabric systems.

The [internship description](https://job-boards.eu.greenhouse.io/constructorknowledgelabs/jobs/4979107101) motivates the focus on synthetic architecture data, baseline experiments and reproducible evaluation.
