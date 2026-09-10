"""Tests for ens/factory.py's VerifiableFactory deployment + address
prediction.

Regression coverage for a real live-run bug: deploy_proxy() simulated
VerifiableFactory.deployProxy() via eth_call without passing `from`, so
the returned "predicted" address was computed for sender=0x0 while the
real transaction (correctly sent `from=signer.address`) deployed
somewhere else entirely. Every write callers then sent to that wrong
address silently no-opped (calling a codeless address never reverts in
the EVM), which is why this got past several apparently-successful
transactions before the first *read* failed to decode an empty response.

tests/fake_chain.py's own address-prediction formula used to ignore
sender too, for the same reason -- so it couldn't have caught this
either. It's now sender-aware, matching the real factory's
keccak256(abi.encode(sender, salt)) salt.
"""

from __future__ import annotations

from eth_account import Account

from ens.factory import DEPLOY_PROXY_FN, deploy_proxy, find_deployed_proxy
from ens.registry import USER_REGISTRY_INITIALIZE_FN
from ens.constants import SUBREGISTRY_ADMIN_ROLE_BITMAP
from tests.fake_chain import FakeChain

ADMIN_KEY = "0x" + "dd" * 32
OTHER_KEY = "0x" + "ee" * 32


def test_deploy_proxy_returned_address_actually_has_code():
    """The direct regression check: whatever address deploy_proxy() hands
    back must be where the contract really landed, not just where a
    mis-simulated eth_call guessed it would."""
    chain = FakeChain()
    admin = Account.from_key(ADMIN_KEY)
    init_data = USER_REGISTRY_INITIALIZE_FN.encode_call(admin.address, SUBREGISTRY_ADMIN_ROLE_BITMAP)

    address = deploy_proxy(
        chain, chain.factory_address, chain.user_registry_impl, 12345, init_data, signer=admin
    )

    assert chain.get_code(address) != b""


def test_deploy_proxy_predicts_differently_for_different_signers():
    """Proves the fake actually models sender-dependence (the real bug's
    root cause) rather than happening to pass by coincidence: the same
    (implementation, salt) simulated for two different `from_address`
    values must predict two different addresses, matching
    keccak256(abi.encode(sender, salt))'s real dependence on sender."""
    chain = FakeChain()
    admin = Account.from_key(ADMIN_KEY)
    other = Account.from_key(OTHER_KEY)
    init_data = USER_REGISTRY_INITIALIZE_FN.encode_call(admin.address, SUBREGISTRY_ADMIN_ROLE_BITMAP)

    calldata = DEPLOY_PROXY_FN.encode_call(chain.user_registry_impl, 999, init_data)
    result_admin = chain.eth_call(chain.factory_address, calldata, from_address=admin.address)
    result_other = chain.eth_call(chain.factory_address, calldata, from_address=other.address)
    (predicted_admin,) = DEPLOY_PROXY_FN.decode_output(result_admin)
    (predicted_other,) = DEPLOY_PROXY_FN.decode_output(result_other)

    assert predicted_admin.lower() != predicted_other.lower()


def test_deploy_proxy_redeploy_self_heals_to_the_same_address():
    """VerifiableFactory's CREATE2 is deterministic per (sender, salt), so
    a literal second deployProxy() call for the same pair reverts on-chain
    -- but deploy_proxy() recovers the address of the *existing* proxy via
    its ProxyDeployed event log (find_deployed_proxy()) instead of
    surfacing that revert. Regression test for a real live-run failure:
    the simulation that would normally report the address can't run once
    a salt is already used (it reverts too), so before this fix there was
    no way to learn the real address short of a manual eth_getLogs query."""
    chain = FakeChain()
    admin = Account.from_key(ADMIN_KEY)
    init_data = USER_REGISTRY_INITIALIZE_FN.encode_call(admin.address, SUBREGISTRY_ADMIN_ROLE_BITMAP)

    first = deploy_proxy(chain, chain.factory_address, chain.user_registry_impl, 777, init_data, signer=admin)
    second = deploy_proxy(chain, chain.factory_address, chain.user_registry_impl, 777, init_data, signer=admin)

    assert second.lower() == first.lower()


def test_find_deployed_proxy_returns_none_when_nothing_matches():
    """The other half of deploy_proxy()'s fallback: find_deployed_proxy()
    finding nothing must let a genuinely wrong factory/implementation
    address (not "this salt was already used") surface as
    ProxyDeploymentError rather than silently returning something wrong."""
    chain = FakeChain()
    admin = Account.from_key(ADMIN_KEY)

    assert find_deployed_proxy(chain, chain.factory_address, admin.address, chain.user_registry_impl) is None
