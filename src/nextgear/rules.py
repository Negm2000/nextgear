"""The checks that accept or reject an assembly.

The rules come from constructorfabric/gears-rust at the commit in fabric_gears.py:

- docs/GEARS.md gives the request order "API Gateway → Auth Resolver → Policy Manager → License
  Resolver → Execution Gear → Tenant Resolver → Audit / Usage Collector" (line 63), says "bypassing
  middlewares is not permitted" (line 49) and "only integration/adapters talk to external
  components" (line 52).
- Every gear's `#[toolkit::gear(deps = [...])]` declaration lists the gears it depends on, and the
  toolkit's registry refuses to build an application in which a declared dependency is absent
  (`RegistryError::UnknownDependency`). fabric_gears.py holds those declarations.

The completeness, cost and latency rules, and all numbers below, are this project's own assumptions.
"""

from dataclasses import dataclass
from functools import cache

from .fabric_gears import DEPS as DECLARED
from .fabric_gears import UNDECLARED

ORDER: dict[str, int] = {
    "API_GATEWAY": 0, "AUTH_RESOLVER": 1, "POLICY_MANAGER": 2, "LICENSE_RESOLVER": 3,
    "CHAT_ENGINE": 4, "BILLING_LEDGER": 4, "SERVERLESS_RUNTIME": 4,
    "TENANT_RESOLVER": 5, "USAGE_COLLECTOR": 6,
}
EXECUTION_GEARS: frozenset[str] = frozenset({"CHAT_ENGINE", "BILLING_LEDGER", "SERVERLESS_RUNTIME"})
CALLS_EXTERNAL: frozenset[str] = frozenset({"CHAT_ENGINE", "SERVERLESS_RUNTIME"})
OUTBOUND = "OUTBOUND_API_GATEWAY"
# Gears off the request path that other gears declare as dependencies.
PLATFORM: tuple[str, ...] = ("GRPC_HUB", "TYPES_REGISTRY", "AUTHZ_RESOLVER", "CREDENTIALS_STORE", "ACCOUNT_MANAGER",
                             "RESOURCE_GROUP")

# Each simulated gear and the gears-rust gear it stands for. GEARS.md's Auth Resolver validates tokens
# (authn-resolver), its Policy Manager manages authorization policies (policy-engine), and its Outbound
# API Gateway and Billing Ledger are the oagw and bss-ledger gears.
CRATES: dict[str, str] = {
    "API_GATEWAY": "api-gateway", "AUTH_RESOLVER": "authn-resolver", "POLICY_MANAGER": "policy-engine",
    "LICENSE_RESOLVER": "license-resolver", "CHAT_ENGINE": "chat-engine", "BILLING_LEDGER": "bss-ledger",
    "SERVERLESS_RUNTIME": "serverless-runtime", "TENANT_RESOLVER": "tenant-resolver",
    "USAGE_COLLECTOR": "usage-collector", OUTBOUND: "oagw", "GRPC_HUB": "grpc-hub", "TYPES_REGISTRY": "types-registry",
    "AUTHZ_RESOLVER": "authz-resolver", "CREDENTIALS_STORE": "credstore", "ACCOUNT_MANAGER": "account-management",
    "RESOURCE_GROUP": "resource-group",
}
_SIMULATED = {crate: gear for gear, crate in CRATES.items()}
if set(CRATES.values()) != set(DECLARED) | set(UNDECLARED):
    raise ImportError("fabric_gears.py and CRATES describe different gears; rerun tools/extract_gears.py.")
# Declared dependencies in simulated names. A gear with no declaration (serverless-runtime) has none.
DEPS: dict[str, frozenset[str]] = {
    gear: frozenset(_SIMULATED[d] for d in DECLARED.get(crate, ())) for gear, crate in CRATES.items()
}

LATENCY_MS: dict[str, float] = {
    "API_GATEWAY": 3, "AUTH_RESOLVER": 8, "POLICY_MANAGER": 6, "LICENSE_RESOLVER": 5,
    "CHAT_ENGINE": 40, "BILLING_LEDGER": 15, "SERVERLESS_RUNTIME": 25,
    "TENANT_RESOLVER": 4, "USAGE_COLLECTOR": 3, OUTBOUND: 10,
}
CACHED_GEARS: frozenset[str] = frozenset({"AUTH_RESOLVER", "POLICY_MANAGER", "LICENSE_RESOLVER", "TENANT_RESOLVER"})
BUDGET_MS: dict[str, float] = {"tight": 60.0, "loose": 120.0}


def closure(gears) -> frozenset[str]:
    """The gears together with everything they depend on, directly or indirectly."""
    return _closure(frozenset(gears))


@cache
def _closure(gears: frozenset[str]) -> frozenset[str]:
    result, queue = set(gears), list(gears)
    while queue:
        for dep in DEPS[queue.pop()] - result:
            result.add(dep)
            queue.append(dep)
    return frozenset(result)


def missing_dependency(gears) -> bool:
    """True when the registry would refuse to build: some gear's declared dependency is absent."""
    present = set(gears)
    return any(DEPS[g] - present for g in present)


@dataclass(frozen=True)
class Spec:
    """What the application must provide. Only the oracle and the checks may read it."""

    execution: str
    policy: bool
    license: bool
    usage: bool
    budget: str

    def needs_outbound(self) -> bool:
        return self.execution in CALLS_EXTERNAL

    @cache  # specs are few, frozen and hashable
    def required(self) -> frozenset[str]:
        """Every gear the application needs: the requested gears and everything they depend on."""
        wanted = ["API_GATEWAY", "AUTH_RESOLVER", self.execution]
        wanted += ["POLICY_MANAGER"] * self.policy + ["LICENSE_RESOLVER"] * self.license
        wanted += ["USAGE_COLLECTOR"] * self.usage + [OUTBOUND] * self.needs_outbound()
        return closure(wanted)

    @cache
    def required_path(self) -> tuple[str, ...]:
        """The required gears that sit on the request path, in request order. Every outbound gateway
        and Billing Ledger depends on the Tenant Resolver, so it is always among them."""
        return tuple(sorted((g for g in self.required() if g in ORDER), key=ORDER.get))


def present(path: tuple[str, ...], outbound: bool, platform: frozenset[str]) -> frozenset[str]:
    return frozenset(path) | platform | ({OUTBOUND} if outbound else frozenset())


# @cpt-algo:cpt-nextgear-algo-simulator-local-check:p1
def local_verdict(path: tuple[str, ...], outbound: bool, platform: frozenset[str], gear: str) -> str:
    """Check one proposed gear against the current assembly."""
    # @cpt-begin:cpt-nextgear-algo-simulator-local-check:p1:inst-outbound
    if gear == OUTBOUND:
        return "ORDER_VIOLATION" if outbound else "STEP_ACCEPTED"
    if gear in PLATFORM:
        return "ORDER_VIOLATION" if gear in platform else "STEP_ACCEPTED"
    # @cpt-end:cpt-nextgear-algo-simulator-local-check:p1:inst-outbound
    # @cpt-begin:cpt-nextgear-algo-simulator-local-check:p1:inst-bypass
    if gear in EXECUTION_GEARS and "AUTH_RESOLVER" not in path:
        return "BYPASS_VIOLATION"
    # @cpt-end:cpt-nextgear-algo-simulator-local-check:p1:inst-bypass
    # @cpt-begin:cpt-nextgear-algo-simulator-local-check:p1:inst-order
    if not path:
        return "STEP_ACCEPTED" if gear == "API_GATEWAY" else "ORDER_VIOLATION"
    return "STEP_ACCEPTED" if ORDER[gear] > ORDER[path[-1]] else "ORDER_VIOLATION"
    # @cpt-end:cpt-nextgear-algo-simulator-local-check:p1:inst-order


def latency_ms(path: tuple[str, ...], outbound: bool, cache: bool) -> float:
    total = sum(LATENCY_MS[g] * (0.5 if cache and g in CACHED_GEARS else 1.0) for g in path)
    return total + (LATENCY_MS[OUTBOUND] if outbound else 0.0)


# @cpt-algo:cpt-nextgear-algo-simulator-system-check:p1
def system_verdict(spec: Spec, path: tuple[str, ...], outbound: bool, platform: frozenset[str], cache: bool) -> str:
    """Check a submitted assembly against the specification, first failure wins."""
    gears, required = present(path, outbound, platform), spec.required()
    # @cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-complete
    if any(g not in path for g in spec.required_path()):
        return "MISSING_CAPABILITY"
    # @cpt-end:cpt-nextgear-algo-simulator-system-check:p1:inst-complete
    # @cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-dependencies
    if missing_dependency(gears):
        return "MISSING_DEPENDENCY"
    # @cpt-end:cpt-nextgear-algo-simulator-system-check:p1:inst-dependencies
    # @cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-external
    if spec.needs_outbound() and not outbound:
        return "EXTERNAL_CALL_VIOLATION"
    # @cpt-end:cpt-nextgear-algo-simulator-system-check:p1:inst-external
    # @cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-cost
    if gears - required:
        return "COST_VIOLATION"
    # @cpt-end:cpt-nextgear-algo-simulator-system-check:p1:inst-cost
    # @cpt-begin:cpt-nextgear-algo-simulator-system-check:p1:inst-latency
    if latency_ms(path, outbound, cache) > BUDGET_MS[spec.budget]:
        return "LATENCY_VIOLATION"
    return "ASSEMBLY_ADMISSIBLE"
    # @cpt-end:cpt-nextgear-algo-simulator-system-check:p1:inst-latency
