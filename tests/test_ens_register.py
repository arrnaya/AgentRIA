import pytest
from eth_account import Account

from ens.accounts import derive_agent_account
from ens.constants import DEFAULT_PUBLIC_RESOLVER_ADDRESS, PARENT_NAME, SUBNAME_TABLE
from ens.namehash import namehash
from ens.register import FUNDING_WEI, register_all, register_subname, verify_isolation
from ens.resolver import PermissionedResolver, ResolverPermissionError
from tests.fake_chain import FakeChain

ADMIN_KEY = "0x" + "bb" * 32


def _setup():
    chain = FakeChain()
    admin = Account.from_key(ADMIN_KEY)
    chain.set_owner(namehash(PARENT_NAME), admin.address)
    resolver = PermissionedResolver(rpc=chain, address=DEFAULT_PUBLIC_RESOLVER_ADDRESS)
    return chain, admin, resolver


def test_register_subname_writes_all_records_for_one_agent():
    chain, admin, resolver = _setup()
    identity = SUBNAME_TABLE["oracle"]

    result = register_subname(identity, rpc=chain, resolver=resolver, admin=admin)

    assert result.name == "ria-oracle.ria.eth"
    assert result.agent_id == "oracle"
    for key, value in identity.text_records().items():
        assert resolver.text(result.node, key) == value


def test_register_subname_grants_only_that_agents_own_derived_address():
    chain, admin, resolver = _setup()
    identity = SUBNAME_TABLE["exec"]

    result = register_subname(identity, rpc=chain, resolver=resolver, admin=admin)

    assert resolver.is_approved(result.node, result.operator_address) is True
    # admin itself remains authorised (registry owner), everyone else is not
    stranger = Account.from_key(b"\x55" * 32)
    assert resolver.is_approved(result.node, stranger.address) is False


def test_register_all_registers_the_fixed_four_agent_table():
    chain, admin, resolver = _setup()

    registrations = register_all(rpc=chain, resolver=resolver, admin=admin)

    agent_ids = {r.agent_id for r in registrations}
    assert agent_ids == {"recon", "oracle", "exec", "audit"}
    names = {r.name for r in registrations}
    assert names == {
        "ria-recon.ria.eth",
        "ria-oracle.ria.eth",
        "ria-exec.ria.eth",
        "ria-audit.ria.eth",
    }
    # every agent got its own distinct operator address
    operators = {r.operator_address for r in registrations}
    assert len(operators) == 4


def test_register_subname_funds_the_agents_derived_account():
    """The agent's derived key signs its own set_text calls next and would
    revert with insufficient funds on a real chain if never funded --
    assert register_subname() actually sends it gas money first."""
    chain, admin, resolver = _setup()
    identity = SUBNAME_TABLE["oracle"]

    result = register_subname(identity, rpc=chain, resolver=resolver, admin=admin)

    assert chain.get_balance(result.operator_address) == FUNDING_WEI


def test_audit_record_includes_hcs_topic_id():
    chain, admin, resolver = _setup()
    result = register_subname(SUBNAME_TABLE["audit"], rpc=chain, resolver=resolver, admin=admin)
    assert "hcs-topic-id" in result.records


def test_verify_isolation_passes_after_a_normal_register_all():
    chain, admin, resolver = _setup()
    registrations = register_all(rpc=chain, resolver=resolver, admin=admin)

    verify_isolation(resolver, registrations)  # should not raise


def test_verify_isolation_catches_a_real_isolation_break():
    """If registration ever granted one agent's key access to another
    agent's node, verify_isolation() must catch it -- prove the checker
    itself isn't a no-op by deliberately breaking isolation and confirming
    it raises."""
    chain, admin, resolver = _setup()
    registrations = register_all(rpc=chain, resolver=resolver, admin=admin)

    oracle_reg = next(r for r in registrations if r.agent_id == "oracle")
    exec_reg = next(r for r in registrations if r.agent_id == "exec")

    # Simulate a bug: admin mistakenly approves EXEC's operator on
    # ORACLE's node too.
    resolver.grant_operator(oracle_reg.node, exec_reg.operator_address, signer=admin)

    with pytest.raises(AssertionError, match="write isolation is broken"):
        verify_isolation(resolver, registrations)


def test_exec_operator_cannot_write_oracle_after_full_registration():
    """End-to-end version of the isolation guarantee through the full
    register_all() path, not just a hand-built resolver test."""
    chain, admin, resolver = _setup()
    registrations = register_all(rpc=chain, resolver=resolver, admin=admin)
    oracle_reg = next(r for r in registrations if r.agent_id == "oracle")
    exec_reg = next(r for r in registrations if r.agent_id == "exec")

    exec_account = derive_agent_account(admin, "exec")
    assert exec_account.address == exec_reg.operator_address

    with pytest.raises(ResolverPermissionError):
        resolver.set_text(oracle_reg.node, "endpoint", "https://hijacked.example", signer=exec_account)
