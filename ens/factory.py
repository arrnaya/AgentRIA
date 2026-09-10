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

register.py never guesses whether a proxy already exists from a previous
run either: ens/constants.py-style env var overrides
(RIA_SUBREGISTRY_ADDRESS / RIA_RESOLVER_ADDRESS, read by
scripts/register_agents_live.py) are the supported way to point at an
already-deployed proxy instead of redeploying.
"""

from __future__ import annotations

from eth_account.signers.local import LocalAccount
from eth_utils import to_checksum_address

from ens.abi import Function
from ens.rpc import EthRpc, build_and_send

DEPLOY_PROXY_FN = Function("deployProxy", ("address", "uint256", "bytes"), ("address",))


class ProxyDeploymentError(RuntimeError):
    """Raised when a VerifiableFactory proxy can't be deployed or its
    address predicted -- most likely because this exact (signer, salt)
    pair already deployed one."""


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
    eth_call-simulating deployProxy first rather than computed locally."""
    calldata = DEPLOY_PROXY_FN.encode_call(implementation, salt, init_data)
    try:
        result = rpc.eth_call(factory_address, calldata)
        (predicted_address,) = DEPLOY_PROXY_FN.decode_output(result)
        # eth_abi always decodes `address` as lowercase hex -- checksum it
        # before it's used as a transaction `to` (eth_account validates
        # that strictly) or handed back to the caller for reuse.
        predicted_address = to_checksum_address(predicted_address)
    except Exception as exc:  # noqa: BLE001 -- any failure means "can't trust an address"
        raise ProxyDeploymentError(
            f"Could not simulate deployProxy(implementation={implementation}, "
            f"salt={salt}) on factory {factory_address} -- it may already be "
            "deployed under this exact (signer, salt) pair, or the factory/"
            "implementation address may be wrong. If it's already deployed, "
            "pass its existing address via the matching RIA_*_ADDRESS "
            "override instead of redeploying."
        ) from exc

    build_and_send(rpc, factory_address, calldata, signer)
    return predicted_address
