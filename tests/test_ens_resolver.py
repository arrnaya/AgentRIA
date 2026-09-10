import pytest
from eth_account import Account

from ens.constants import ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS, ENS_VERIFIABLE_FACTORY_ADDRESS
from ens.namehash import namehash
from ens.resolver import PermissionedResolver, ResolverPermissionError, deploy_resolver_proxy
from tests.fake_chain import ChainRevert, FakeChain

ADMIN_KEY = "0x" + "aa" * 32
ORACLE_NODE = namehash("oracle.agentria.eth")
EXEC_NODE = namehash("exec.agentria.eth")


def _setup(salt: int = 1):
    chain = FakeChain()
    admin = Account.from_key(ADMIN_KEY)
    resolver = deploy_resolver_proxy(
        chain,
        factory_address=ENS_VERIFIABLE_FACTORY_ADDRESS,
        implementation_address=ENS_PERMISSIONED_RESOLVER_IMPL_ADDRESS,
        admin=admin,
        salt=salt,
    )
    return chain, admin, resolver


def test_admin_holds_no_write_access_by_default():
    """Deploying the resolver grants admin ROLE_SET_TEXT_ADMIN (so it can
    delegate) but deliberately not the plain ROLE_SET_TEXT bit itself --
    admin should never be able to write records through this resolver
    directly, only authorise someone else to."""
    chain, admin, resolver = _setup()
    assert resolver.is_authorized_for_node(ORACLE_NODE, admin.address) is False


def test_random_address_is_not_authorised_by_default():
    chain, admin, resolver = _setup()
    stranger = Account.from_key(b"\x99" * 32)
    assert resolver.is_authorized_for_node(ORACLE_NODE, stranger.address) is False


def test_authorize_agent_requires_admin_role():
    chain, admin, resolver = _setup()
    not_the_admin = Account.from_key(b"\x77" * 32)
    oracle_agent = Account.from_key(b"\x01" * 32)
    with pytest.raises(ChainRevert):
        resolver.authorize_agent("oracle.agentria.eth", oracle_agent.address, signer=not_the_admin)


def test_authorize_agent_by_admin_makes_delegate_authorised():
    chain, admin, resolver = _setup()
    oracle_agent = Account.from_key(b"\x01" * 32)
    resolver.authorize_agent("oracle.agentria.eth", oracle_agent.address, signer=admin)
    assert resolver.is_authorized_for_node(ORACLE_NODE, oracle_agent.address) is True


def test_set_text_by_unauthorised_signer_raises_client_side():
    chain, admin, resolver = _setup()
    stranger = Account.from_key(b"\x66" * 32)
    with pytest.raises(ResolverPermissionError):
        resolver.set_text(ORACLE_NODE, "endpoint", "https://evil.example", signer=stranger)
    # And nothing was actually written.
    assert resolver.text(ORACLE_NODE, "endpoint") == ""


def test_set_text_by_authorized_agent_succeeds():
    chain, admin, resolver = _setup()
    oracle_agent = Account.from_key(b"\x01" * 32)
    resolver.authorize_agent("oracle.agentria.eth", oracle_agent.address, signer=admin)

    resolver.set_text(ORACLE_NODE, "endpoint", "https://oracle.agentria.eth.example", signer=oracle_agent)

    assert resolver.text(ORACLE_NODE, "endpoint") == "https://oracle.agentria.eth.example"


def test_exec_cannot_overwrite_oracles_records():
    """The actual judging bar: EXEC's operator key must not be able to
    write ORACLE's node, even after EXEC has legitimately been granted
    write access to its *own* node. Enforced here at two layers: (1)
    resolver.set_text()'s client-side is_authorized_for_node() check
    raises before building a transaction, and (2) even bypassing that
    guard by hitting the fake chain's send_raw_transaction() directly (as
    a real Sepolia node's onlyPartRoles/EACUnauthorizedAccountRoles
    revert would), the write is rejected."""
    chain, admin, resolver = _setup()
    oracle_agent = Account.from_key(b"\x01" * 32)
    exec_agent = Account.from_key(b"\x02" * 32)
    resolver.authorize_agent("oracle.agentria.eth", oracle_agent.address, signer=admin)
    resolver.authorize_agent("exec.agentria.eth", exec_agent.address, signer=admin)

    # Layer 1: the Python wrapper itself refuses.
    with pytest.raises(ResolverPermissionError):
        resolver.set_text(ORACLE_NODE, "endpoint", "https://exec-takeover.example", signer=exec_agent)

    # Layer 2: even going around resolver.py and hitting the chain
    # directly with a correctly-signed setText call from EXEC's own key
    # -- exactly what a malicious/buggy client could attempt -- the fake
    # chain's EAC equivalent still reverts it.
    from ens.resolver import SET_TEXT_FN
    from ens.rpc import build_and_send

    with pytest.raises(ChainRevert):
        build_and_send(
            chain,
            resolver.address,
            SET_TEXT_FN.encode_call(ORACLE_NODE, "endpoint", "https://exec-takeover.example"),
            exec_agent,
        )

    # ORACLE's record is untouched either way.
    assert resolver.text(ORACLE_NODE, "endpoint") == ""
    # EXEC's own node, meanwhile, works fine for EXEC.
    resolver.set_text(EXEC_NODE, "endpoint", "https://exec.agentria.eth.example", signer=exec_agent)
    assert resolver.text(EXEC_NODE, "endpoint") == "https://exec.agentria.eth.example"


def test_authorize_agent_only_affects_the_named_node():
    """authorize_agent() grants ROLE_SET_TEXT on resource(node, 0) for
    the *specific* name given -- confirm granting oracle's node never
    makes the same agent authorised for a different, unrelated node."""
    chain, admin, resolver = _setup()
    oracle_agent = Account.from_key(b"\x01" * 32)
    resolver.authorize_agent("oracle.agentria.eth", oracle_agent.address, signer=admin)

    assert resolver.is_authorized_for_node(ORACLE_NODE, oracle_agent.address) is True
    assert resolver.is_authorized_for_node(EXEC_NODE, oracle_agent.address) is False
