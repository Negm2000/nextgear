"""The 31 events of an assembly session, each with a short description."""

EVENTS: dict[str, str] = {
    "SESSION_STARTED": "The agent received a specification and started assembling gears.",
    "ADD_API_GATEWAY": "The agent proposed adding the API Gateway to the request path.",
    "ADD_AUTH_RESOLVER": "The agent proposed adding the Auth Resolver to the request path.",
    "ADD_POLICY_MANAGER": "The agent proposed adding the Policy Manager to the request path.",
    "ADD_LICENSE_RESOLVER": "The agent proposed adding the License Resolver to the request path.",
    "ADD_CHAT_ENGINE": "The agent proposed the Chat Engine as the execution gear.",
    "ADD_BILLING_LEDGER": "The agent proposed the Billing Ledger as the execution gear.",
    "ADD_SERVERLESS_RUNTIME": "The agent proposed a Serverless Runtime as the execution gear.",
    "ADD_TENANT_RESOLVER": "The agent proposed adding the Tenant Resolver to the request path.",
    "ADD_USAGE_COLLECTOR": "The agent proposed adding the Usage Collector to the request path.",
    "ADD_OUTBOUND_API_GATEWAY": "The agent proposed the Outbound API Gateway for external calls.",
    "ADD_GRPC_HUB": "The agent proposed adding the gRPC Hub platform gear.",
    "ADD_TYPES_REGISTRY": "The agent proposed adding the Types Registry platform gear.",
    "ADD_AUTHZ_RESOLVER": "The agent proposed adding the Authorization Resolver platform gear.",
    "ADD_CREDENTIALS_STORE": "The agent proposed adding the Credentials Store platform gear.",
    "ADD_ACCOUNT_MANAGER": "The agent proposed adding the Account Manager platform gear.",
    "ADD_RESOURCE_GROUP": "The agent proposed adding the Resource Group platform gear.",
    "SUBMIT_ASSEMBLY": "The agent submitted the assembly for whole-system checks.",
    "STEP_ACCEPTED": "The local check accepted the proposed gear.",
    "ORDER_VIOLATION": "The local check rejected the gear: wrong pipeline position or a duplicate.",
    "BYPASS_VIOLATION": "The local check rejected the gear: it would let requests skip the Auth Resolver.",
    "STEP_REVERTED": "The agent withdrew the rejected gear.",
    "MISSING_DEPENDENCY": "The system check found a gear whose declared dependency is absent.",
    "MISSING_CAPABILITY": "The system check found a required capability with no gear.",
    "EXTERNAL_CALL_VIOLATION": "The system check found external calls without the Outbound API Gateway.",
    "COST_VIOLATION": "The system check found gears the specification does not need.",
    "LATENCY_VIOLATION": "The system check estimated latency above the specification's budget.",
    "ROLLBACK_ASSEMBLY": "The agent discarded the assembly to rebuild it from scratch.",
    "ENABLE_RESOLVER_CACHE": "The agent enabled caching of resolver decisions to cut latency.",
    "ASSEMBLY_ADMISSIBLE": "Every check passed: the assembly is admissible.",
    "SESSION_ABANDONED": "The agent gave up without an admissible assembly.",
}

VOCAB: tuple[str, ...] = tuple(EVENTS)
INDEX: dict[str, int] = {name: i for i, name in enumerate(VOCAB)}

GEARS: tuple[str, ...] = (
    "API_GATEWAY", "AUTH_RESOLVER", "POLICY_MANAGER", "LICENSE_RESOLVER", "CHAT_ENGINE",
    "BILLING_LEDGER", "SERVERLESS_RUNTIME", "TENANT_RESOLVER", "USAGE_COLLECTOR", "OUTBOUND_API_GATEWAY",
    "GRPC_HUB", "TYPES_REGISTRY", "AUTHZ_RESOLVER", "CREDENTIALS_STORE", "ACCOUNT_MANAGER", "RESOURCE_GROUP",
)
ADD_EVENTS: dict[str, str] = {f"ADD_{gear}": gear for gear in GEARS}
PROPOSALS: frozenset[str] = frozenset(ADD_EVENTS) | {"SUBMIT_ASSEMBLY"}
LOCAL_VERDICTS: tuple[str, ...] = ("STEP_ACCEPTED", "ORDER_VIOLATION", "BYPASS_VIOLATION")
SYSTEM_VERDICTS: tuple[str, ...] = (
    "MISSING_DEPENDENCY", "MISSING_CAPABILITY", "EXTERNAL_CALL_VIOLATION", "COST_VIOLATION", "LATENCY_VIOLATION",
    "ASSEMBLY_ADMISSIBLE",
)
TERMINALS: frozenset[str] = frozenset({"ASSEMBLY_ADMISSIBLE", "SESSION_ABANDONED"})
