# How Constructor Fabric was used

Two parts of Fabric are built in. **Gears** supplies the domain the model learns, and **Studio** is the workflow the project was specified and checked with. The predictor itself is Python and PyTorch.

## Gears: the rules come from Fabric's code

Every gear in [gears-rust](https://github.com/constructorfabric/gears-rust) declares what it depends on, for example `#[toolkit::gear(name = "oagw", deps = [types_registry, authz_resolver, credstore, tenant_resolver])]`. The toolkit's registry refuses to assemble an application in which a declared dependency is absent (`RegistryError::UnknownDependency`). Nextgear applies the same rule and reports it as `MISSING_DEPENDENCY`.

- [`tools/extract_gears.py`](tools/extract_gears.py) reads those declarations at commit `fc765fe` into [`fabric_gears.py`](src/nextgear/fabric_gears.py). Six platform gears join the vocabulary because the declarations require them.
- The real graph shapes the data. For example, the outbound gateway needs the Credentials Store, and the Billing Ledger needs the Resource Group through the Account Manager.
- The same commit's [`docs/GEARS.md`](https://github.com/constructorfabric/gears-rust/blob/fc765feb8e328ae31c44bfb3a0c981b42e32a105/docs/GEARS.md) supplies the request order (lines 62–63), the no-bypass rule (line 49) and outbound adapters (line 52).
- Matching documented names to crates is my reading. For example, Auth Resolver is `authn-resolver`, and Policy Manager is `policy-engine`.

**Checked against the real implementation.** A small Rust program, [`tools/registry_check`](tools/registry_check/src/main.rs), builds against the toolkit at the same commit and asks its registry about each assembly. On 24,910 assemblies it agrees with Nextgear every time. They are every assembly submitted in 2,000 simulated sessions, plus 20,000 random gear subsets. The harness registers stub gears with the extracted declarations, so this checks the dependency rule, not request handling. CI reruns it on every push, and also re-extracts the declarations from gears-rust and fails if they no longer match.

```sh
cargo build --release --manifest-path tools/registry_check/Cargo.toml
python tools/crosscheck_registry.py
```

**Assumed, not from Fabric:** the agent's behaviour, the requirement frequencies, the order of the checks, latencies and budgets. Two choices depart from Fabric:

- Its documentation (line 62) makes the Policy Manager, License Resolver and Usage Collector mandatory on every external request; here they are optional, so that sessions differ in what they need.
- Serverless Runtime is documented but not implemented at the pinned commit, so it has no declaration; the simulator assumes it has no dependencies.

No production gear runs here.

## Studio: specified, traced and validated

The project follows Studio's chain, **PRD → ADR → DESIGN → DECOMPOSITION → FEATURE → CODE**:

- [requirements](architecture/PRD.md);
- [five decisions](architecture/ADR/);
- [design](architecture/DESIGN.md) and [decomposition](architecture/DECOMPOSITION.md);
- [four feature specifications](architecture/features/), whose algorithm steps map to `@cpt-` markers in the code.

`cfs validate` fails if a step and its code drift apart.

Changes went through the same chain. Adopting the gears-rust dependencies took three steps:

1. A new decision, [ADR 0005](architecture/ADR/0005-fabric-dependencies-v1.md).
2. An updated requirement.
3. A new specification step, `inst-dependencies`, traced to its code in `src/nextgear/rules.py`.

The workflow was most useful in two ways. It forced the information boundary and the evaluation contract to be written down. It also flagged stale references whenever a module changed. Several specifications were revised after code review, so they describe the current implementation rather than prove that requirements came first.

```sh
python -m pip install "constructor-studio @ git+https://github.com/constructorfabric/studio.git@3e73a118af4108fa45b306e02f20c9692d1bc1d6"
cfs validate
```

That commit is Studio v1.8.0, with SDLC kit v1.2.1 vendored under `.cf-studio/`. CI runs validation on every push: 12 artifacts and 21/21 traced identifiers, with no errors. Validation checks structure and links, not whether the simulator's assumptions are true.
