"""ENSv2's VerifiableFactory: deterministic CREATE2 proxy deployment.

ENSv2 gives every ENS name owner its own dedicated contract instances (a
subregistry to hold its subnames, a Permissioned Resolver to hold their
records) rather than routing everyone through one shared contract per
feature. Those instances are deployed on demand via ENS's
VerifiableFactory, which clones a minimal UUPS proxy pointing at a chosen
implementation and initializes it in the same transaction.

Verified against the real, currently-deployed
src/VerifiableFactory.sol + src/UUPSProxyLogic.sol in
ensdomains/verifiable-factory (fetched directly from GitHub):

    function deployProxy(address implementation, uint256 salt, bytes data)
        external returns (address proxy)

`data` is delegatecalled into `implementation` as-is, inside the same
transaction (UUPSProxyLogic.initialize -> `delegatecall(implementation,
data)`) -- so `data` must be the fully ABI-encoded call to whatever
`initialize(...)` function the target implementation exposes. See
ens/registry.py's UserRegistry.initialize() and
ens/resolver.py's PermissionedResolver.initialize() for the two calls
register.py actually builds.

CREATE2 means the deployed address is deterministic from
(factory, msg.sender, salt) -- `outerSalt = keccak256(abi.encode(sender,
salt))` per the real source -- so calling deployProxy twice with the same
(sender, salt) reverts the second time (CREATE2 to an address that
already has code fails). This module never tries to reimplement that
address-prediction math client-side (it would need the factory's
`proxyLogic` immutable and its exact clone-bytecode template, which is
more surface area than a hackathon-deadline-facing script should gamble
on getting byte-perfect) -- instead it *simulates* the exact deployProxy
call via eth_call first. A state-changing function called through
eth_call still executes CREATE2 locally and returns its result without
committing anything, which is exactly how a real node would answer "what
address would this produce" -- so the simulated return value is the real
one, without duplicating VerifiableFactory's internals.

The simulation MUST be called with `from` set to the real deployer's
address, not omitted. Confirmed the hard way in a live run: since the
salt depends on `sender`, simulating with no `from` (defaulting to the
zero address on every node tested) computed the address CREATE2 would
produce for sender=0x0, while the real transaction -- correctly sent
`from=signer.address` -- deployed to a *different* address. Every write
this module and callers then sent to the wrong ("predicted") address
silently no-opped (calling a codeless address never reverts in the EVM --
there's simply nothing to execute), which masked the mistake through
several successful-looking transactions until the first *read* against
that address failed to decode 0 returned bytes as a uint256. `eth_call`
below always passes `from_address=signer.address` for exactly this
reason.

register.py never guesses whether a proxy already exists from a previous
run either: ens/constants.py-style env var overrides
(RIA_SUBREGISTRY_ADDRESS / RIA_RESOLVER_ADDRESS, read by
scripts/register_agents_live.py) are the supported way to point at an
already-deployed proxy instead of redeploying.

Even without an override, deploy_proxy() below now recovers on its own if
this exact (signer, salt) pair already deployed successfully: simulating
(or really sending) deployProxy() to a salt that's already been used
reverts -- confirmed live, an empty `data: "0x"` revert with no reason
string -- so there's no return value to read the real address from at
that point. find_deployed_proxy() gets it a different way: VerifiableFactory
emits a ProxyDeployed(address indexed sender, address indexed proxy,
bytes32 salt, address implementation) event (topic0 confirmed live:
0x0a2c575ff341b41da136c9ccae74ec230a927a024d18f0dccf46d123f28f5f54) on
every successful deployment, so eth_getLogs filtered by factory + sender
finds it even when the simulation that would normally report it can't
run.
"""

from __future__ import annotations

from eth_account.signers.local import LocalAccount
from eth_utils import to_checksum_address

from ens.abi import Function
from ens.rpc import EthRpc, build_and_send

DEPLOY_PROXY_FN = Function("deployProxy", ("address", "uint256", "bytes"), ("address",))

# VerifiableFactory's ProxyDeployed(address indexed sender, address indexed
# proxy, bytes32 salt, address implementation) -- confirmed against a real
# emitted log on Sepolia, not computed from a guessed event signature.
PROXY_DEPLOYED_TOPIC = "0x0a2c575ff341b41da136c9ccae74ec230a927a024d18f0dccf46d123f28f5f54"

# Confirmed against a real provider (Infura) in practice: eth_getLogs
# rejects any single fromBlock/toBlock span over 10,000 blocks with
# {"code": -32602, "message": "range ... exceeds limit of 10000"} rather
# than paginating for you. find_deployed_proxy() below scans backward from
# the chain tip in chunks safely under that limit, stopping as soon as it
# finds a match. RIA's own deployments are always recent (this whole
# system is built during one hackathon), so LOG_LOOKBACK_MAX_BLOCKS --
# several days' worth even on Sepolia's ~12s blocks -- comfortably covers
# a real search without scanning arbitrarily far into chain history.
LOG_LOOKBACK_CHUNK_BLOCKS = 9_000
LOG_LOOKBACK_MAX_BLOCKS = 200_000


class ProxyDeploymentError(RuntimeError):
    """Raised when a VerifiableFactory proxy can't be deployed, its address
    predicted, or an already-deployed one found via its event log."""


def _topic_address(address: str) -> str:
    return "0x" + address[2:].lower().rjust(64, "0")


def find_deployed_proxy(
    rpc: EthRpc, factory_address: str, deployer: str, implementation: str
) -> str | None:
    """Find an already-deployed proxy for (deployer, implementation) via
    VerifiableFactory's ProxyDeployed event, for when deploy_proxy() can't
    simulate a fresh deployment because this salt was already used
    successfully -- see module docstring. Returns the most recent match,
    or None if this factory has no such deployment on record for this
    deployer/implementation pair within LOG_LOOKBACK_MAX_BLOCKS.

    Scans backward from the chain tip in LOG_LOOKBACK_CHUNK_BLOCKS-sized
    windows (see that constant's comment for why a single unbounded query
    doesn't work against a real provider), stopping at the first match --
    the most recent deployment is almost always the relevant one, and this
    avoids scanning further than necessary.
    """
    target = implementation.lower()
    topics = [PROXY_DEPLOYED_TOPIC, _topic_address(deployer)]

    tip = rpc.block_number()
    window_end = tip
    scanned = 0
    while scanned <= LOG_LOOKBACK_MAX_BLOCKS:
        window_start = max(0, window_end - LOG_LOOKBACK_CHUNK_BLOCKS)
        logs = rpc.get_logs(factory_address, topics, from_block=hex(window_start), to_block=hex(window_end))
        match = _match_proxy_deployed_log(logs, target)
        if match is not None:
            return match
        if window_start == 0:
            break
        scanned += window_end - window_start
        window_end = window_start - 1

    return None


def _match_proxy_deployed_log(logs: list[dict], target_implementation_lower: str) -> str | None:
    for log in reversed(logs):  # most recent first
        proxy = "0x" + log["topics"][2][-40:]
        data = log["data"][2:]
        logged_implementation = "0x" + data[64:128][-40:]
        if logged_implementation.lower() == target_implementation_lower:
            return to_checksum_address(proxy)
    return None


def deploy_proxy(
    rpc: EthRpc,
    factory_address: str,
    implementation: str,
    salt: int,
    init_data: bytes,
    *,
    signer: LocalAccount,
) -> str:
    """Deploy (and initialize) one VerifiableFactory proxy, returning its
    address. See module docstring for why the address comes from
    eth_call-simulating deployProxy first rather than computed locally,
    and how a failed simulation still recovers the real address via
    find_deployed_proxy() rather than assuming failure means "broken"."""
    calldata = DEPLOY_PROXY_FN.encode_call(implementation, salt, init_data)
    try:
        result = rpc.eth_call(factory_address, calldata, from_address=signer.address)
        (predicted_address,) = DEPLOY_PROXY_FN.decode_output(result)
        # eth_abi always decodes `address` as lowercase hex -- checksum it
        # before it's used as a transaction `to` (eth_account validates
        # that strictly) or handed back to the caller for reuse.
        predicted_address = to_checksum_address(predicted_address)
    except Exception as exc:  # noqa: BLE001 -- simulation failing isn't necessarily fatal, see below
        existing = find_deployed_proxy(rpc, factory_address, signer.address, implementation)
        if existing is not None:
            return existing
        raise ProxyDeploymentError(
            f"Could not simulate deployProxy(implementation={implementation}, "
            f"salt={salt}) on factory {factory_address}, and no matching "
            "ProxyDeployed event was found for this signer/implementation "
            "either -- the factory/implementation address may be wrong, or "
            "the deployer isn't funded. If a deployment genuinely exists "
            "somewhere this lookup can't see, pass its address via the "
            "matching RIA_*_ADDRESS override instead of redeploying."
        ) from exc

    build_and_send(rpc, factory_address, calldata, signer)
    return predicted_address
