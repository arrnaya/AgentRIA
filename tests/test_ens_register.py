import pytest
from eth_account import Account

from ens.accounts import derive_agent_account
from ens.constants import ENS_ETH_REGISTRY_ADDRESS, SUBNAME_TABLE
from ens.register import (
    FUNDING_WEI,
    ensure_resolver,
    ensure_subregistry,
    register_all,
    register_subname,
    verify_isolation,
)
from ens.factory import ProxyDeploymentError
from ens.registry import PermissionedRegistryClient
from ens.resolver import ResolverPermissionError
from tests.fake_chain import FakeChain

ADMIN_KEY = "0x" + "bb" * 32
FUTURE_EXPIRY = 4_102_444_800  # 2100-01-01, matches a live agentria.eth-style expiry


def _setup():
    chain = FakeChain()
    admin = Account.from_key(ADMIN_KEY)
    chain.seed_agentria(admin.address, expiry=FUTURE_EXPIRY)
    root_registry = PermissionedRegistryClient(rpc=chain, address=ENS_ETH_REGISTRY_ADDRESS)
    subregistry = ensure_subregistry(chain, root_registry, admin)
    resolver = ensure_resolver(chain, admin)
    return chain, admin, root_registry, subregistry, resolver


def test_ensure_subregistry_deploys_one_when_none_exists():
    chain, admin, root_registry, subregistry, resolver = _setup()
    assert root_registry.get_subregistry("agentria").lower() == subregistry.address.lower()


def test_ensure_subregistry_reuses_an_existing_one():
    chain, admin, root_registry, subregistry, resolver = _setup()
    # Calling it again (as a second register_agents_live.py run might)
    # must not try to redeploy -- it should find the one just attached.
    again = ensure_subregistry(chain, root_registry, admin)
    assert again.address.lower() == subregistry.address.lower()


def test_ensure_subregistry_attaches_a_deployed_but_unattached_override():
    """Regression test for a real failure: register_agents_live.py deployed
    a subregistry, then the very next transaction (attaching it to
    agentria.eth) was rejected by the RPC provider before broadcast (an
    Infura "in-flight transaction limit" policy error) -- leaving a real,
    live subregistry that agentria.eth's registry entry still didn't point
    at. An earlier version of ensure_subregistry() trusted `override_address`
    to mean "already fully done" and would have returned without attaching
    it, silently leaving every subname unresolvable. It must always attach
    on re-run if it isn't attached yet, override or not."""
    chain = FakeChain()
    admin = Account.from_key(ADMIN_KEY)
    chain.seed_agentria(admin.address, expiry=FUTURE_EXPIRY)
    root_registry = PermissionedRegistryClient(rpc=chain, address=ENS_ETH_REGISTRY_ADDRESS)

    # Deploy a subregistry directly, bypassing ensure_subregistry() entirely
    # -- so it exists on-chain but is NOT attached, exactly the stuck state
    # a partially-completed live run leaves behind.
    from ens.constants import ENS_USER_REGISTRY_IMPL_ADDRESS, ENS_VERIFIABLE_FACTORY_ADDRESS, SUBREGISTRY_ADMIN_ROLE_BITMAP
    from ens.factory import deploy_proxy
    from ens.registry import USER_REGISTRY_INITIALIZE_FN

    init_data = USER_REGISTRY_INITIALIZE_FN.encode_call(admin.address, SUBREGISTRY_ADMIN_ROLE_BITMAP)
    deployed_address = deploy_proxy(
        chain, ENS_VERIFIABLE_FACTORY_ADDRESS, ENS_USER_REGISTRY_IMPL_ADDRESS, 999, init_data, signer=admin
    )
    assert root_registry.get_subregistry("agentria").lower() == "0x" + "00" * 20  # confirm: not attached yet

    result = ensure_subregistry(chain, root_registry, admin, override_address=deployed_address)

    assert result.address.lower() == deployed_address.lower()
    assert root_registry.get_subregistry("agentria").lower() == deployed_address.lower()


def test_ensure_subregistry_override_is_a_noop_once_already_attached():
    """The common case on a clean re-run: nothing to do, and it must not
    attempt a second set_subregistry call (which would be a redundant, but
    harmless, transaction) -- verified by asserting the returned address
    is exactly the already-attached one even when a *different* stray
    override is passed, proving the live lookup wins over the override."""
    chain, admin, root_registry, subregistry, resolver = _setup()

    again = ensure_subregistry(chain, root_registry, admin, override_address="0x" + "ab" * 20)

    assert again.address.lower() == subregistry.address.lower()


def test_ensure_resolver_does_not_redeploy_when_reused_via_override():
    chain, admin, root_registry, subregistry, resolver = _setup()
    again = ensure_resolver(chain, admin, override_address=resolver.address)
    assert again.address.lower() == resolver.address.lower()


def test_ensure_resolver_without_override_refuses_to_silently_redeploy():
    """VerifiableFactory's CREATE2 deploy is deterministic per (signer,
    salt) and reverts on a second attempt (ens/factory.py's module
    docstring) -- a second ensure_resolver() call with the same admin key
    and no override must surface that clearly rather than pretending it
    deployed a second, different resolver."""
    chain, admin, root_registry, subregistry, resolver = _setup()
    with pytest.raises(ProxyDeploymentError):
        ensure_resolver(chain, admin)


def test_register_subname_writes_all_records_for_one_agent():
    chain, admin, root_registry, subregistry, resolver = _setup()
    identity = SUBNAME_TABLE["oracle"]

    result = register_subname(
        identity, rpc=chain, subregistry=subregistry, resolver=resolver, admin=admin, expiry=FUTURE_EXPIRY
    )

    assert result.name == "oracle.agentria.eth"
    assert result.agent_id == "oracle"
    for key, value in identity.text_records().items():
        assert resolver.text(result.node, key) == value


def test_register_subname_grants_only_that_agents_own_derived_address():
    chain, admin, root_registry, subregistry, resolver = _setup()
    identity = SUBNAME_TABLE["exec"]

    result = register_subname(
        identity, rpc=chain, subregistry=subregistry, resolver=resolver, admin=admin, expiry=FUTURE_EXPIRY
    )

    assert resolver.is_authorized_for_node(result.node, result.operator_address) is True
    stranger = Account.from_key(b"\x55" * 32)
    assert resolver.is_authorized_for_node(result.node, stranger.address) is False
    # admin itself never gets write access through this resolver either
    # (see ens/resolver.py's RESOLVER_ADMIN_ROLE_BITMAP note).
    assert resolver.is_authorized_for_node(result.node, admin.address) is False


def test_register_all_registers_the_fixed_four_agent_table():
    chain, admin, root_registry, subregistry, resolver = _setup()

    registrations = register_all(
        rpc=chain, subregistry=subregistry, resolver=resolver, admin=admin, root_registry=root_registry
    )

    agent_ids = {r.agent_id for r in registrations}
    assert agent_ids == {"recon", "oracle", "exec", "audit"}
    names = {r.name for r in registrations}
    assert names == {
        "recon.agentria.eth",
        "oracle.agentria.eth",
        "exec.agentria.eth",
        "audit.agentria.eth",
    }
    # every agent got its own distinct operator address
    operators = {r.operator_address for r in registrations}
    assert len(operators) == 4


def test_register_all_reads_the_parent_names_live_expiry_when_not_given():
    chain, admin, root_registry, subregistry, resolver = _setup()
    registrations = register_all(
        rpc=chain, subregistry=subregistry, resolver=resolver, admin=admin, root_registry=root_registry
    )
    # PermissionedRegistryClient.get_expiry reads back what
    # subregistry.register() wrote -- confirm it matches agentria.eth's
    # own seeded expiry (register_all() looked it up live), not some
    # hardcoded default.
    from ens.namehash import label_id

    for reg in registrations:
        label = reg.name.split(".")[0]
        assert subregistry.get_expiry(label_id(label)) == FUTURE_EXPIRY


def test_register_subname_funds_the_agents_derived_account():
    """The agent's derived key signs its own set_text calls next and would
    revert with insufficient funds on a real chain if never funded --
    assert register_subname() actually sends it gas money first."""
    chain, admin, root_registry, subregistry, resolver = _setup()
    identity = SUBNAME_TABLE["oracle"]

    result = register_subname(
        identity, rpc=chain, subregistry=subregistry, resolver=resolver, admin=admin, expiry=FUTURE_EXPIRY
    )

    assert chain.get_balance(result.operator_address) == FUNDING_WEI


def test_audit_record_includes_hcs_topic_id():
    chain, admin, root_registry, subregistry, resolver = _setup()
    result = register_subname(
        SUBNAME_TABLE["audit"], rpc=chain, subregistry=subregistry, resolver=resolver, admin=admin, expiry=FUTURE_EXPIRY
    )
    assert "hcs-topic-id" in result.records


def test_verify_isolation_passes_after_a_normal_register_all():
    chain, admin, root_registry, subregistry, resolver = _setup()
    registrations = register_all(
        rpc=chain, subregistry=subregistry, resolver=resolver, admin=admin, root_registry=root_registry
    )

    verify_isolation(resolver, registrations)  # should not raise


def test_verify_isolation_catches_a_real_isolation_break():
    """If registration ever granted one agent's key access to another
    agent's node, verify_isolation() must catch it -- prove the checker
    itself isn't a no-op by deliberately breaking isolation and confirming
    it raises."""
    chain, admin, root_registry, subregistry, resolver = _setup()
    registrations = register_all(
        rpc=chain, subregistry=subregistry, resolver=resolver, admin=admin, root_registry=root_registry
    )

    oracle_reg = next(r for r in registrations if r.agent_id == "oracle")
    exec_reg = next(r for r in registrations if r.agent_id == "exec")

    # Simulate a bug: admin mistakenly authorises EXEC's operator on
    # ORACLE's node too.
    resolver.authorize_agent(oracle_reg.name, exec_reg.operator_address, signer=admin)

    with pytest.raises(AssertionError, match="write isolation is broken"):
        verify_isolation(resolver, registrations)


def test_exec_operator_cannot_write_oracle_after_full_registration():
    """End-to-end version of the isolation guarantee through the full
    register_all() path, not just a hand-built resolver test."""
    chain, admin, root_registry, subregistry, resolver = _setup()
    registrations = register_all(
        rpc=chain, subregistry=subregistry, resolver=resolver, admin=admin, root_registry=root_registry
    )
    oracle_reg = next(r for r in registrations if r.agent_id == "oracle")
    exec_reg = next(r for r in registrations if r.agent_id == "exec")

    exec_account = derive_agent_account(admin, "exec")
    assert exec_account.address == exec_reg.operator_address

    with pytest.raises(ResolverPermissionError):
        resolver.set_text(oracle_reg.node, "endpoint", "https://hijacked.example", signer=exec_account)
