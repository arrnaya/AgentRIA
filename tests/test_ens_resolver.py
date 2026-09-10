import pytest
from eth_account import Account

from ens.constants import DEFAULT_PUBLIC_RESOLVER_ADDRESS
from ens.namehash import namehash
from ens.resolver import PermissionedResolver, ResolverPermissionError
from tests.fake_chain import ChainRevert, FakeChain

ADMIN_KEY = "0x" + "aa" * 32
ORACLE_NODE = namehash("oracle.agentria.eth")
EXEC_NODE = namehash("exec.agentria.eth")


def _setup():
    chain = FakeChain()
    admin = Account.from_key(ADMIN_KEY)
    chain.set_owner(ORACLE_NODE, admin.address)
    chain.set_owner(EXEC_NODE, admin.address)
    resolver = PermissionedResolver(rpc=chain, address=DEFAULT_PUBLIC_RESOLVER_ADDRESS)
    return chain, admin, resolver


def test_admin_is_always_approved_for_its_own_node():
    chain, admin, resolver = _setup()
    assert resolver.is_approved(ORACLE_NODE, admin.address) is True


def test_random_address_is_not_approved_by_default():
    chain, admin, resolver = _setup()
    stranger = Account.from_key(b"\x99" * 32)
    assert resolver.is_approved(ORACLE_NODE, stranger.address) is False


def test_grant_operator_requires_signer_to_be_node_owner():
    chain, admin, resolver = _setup()
    not_the_owner = Account.from_key(b"\x77" * 32)
    oracle_agent = Account.from_key(b"\x01" * 32)
    with pytest.raises(ResolverPermissionError):
        resolver.grant_operator(ORACLE_NODE, oracle_agent.address, signer=not_the_owner)


def test_grant_operator_by_admin_makes_delegate_approved():
    chain, admin, resolver = _setup()
    oracle_agent = Account.from_key(b"\x01" * 32)
    resolver.grant_operator(ORACLE_NODE, oracle_agent.address, signer=admin)
    assert resolver.is_approved(ORACLE_NODE, oracle_agent.address) is True


def test_set_text_by_unauthorised_signer_raises_client_side():
    chain, admin, resolver = _setup()
    stranger = Account.from_key(b"\x66" * 32)
    with pytest.raises(ResolverPermissionError):
        resolver.set_text(ORACLE_NODE, "endpoint", "https://evil.example", signer=stranger)
    # And nothing was actually written.
    assert resolver.text(ORACLE_NODE, "endpoint") == ""


def test_set_text_by_approved_operator_succeeds():
    chain, admin, resolver = _setup()
    oracle_agent = Account.from_key(b"\x01" * 32)
    resolver.grant_operator(ORACLE_NODE, oracle_agent.address, signer=admin)

    resolver.set_text(ORACLE_NODE, "endpoint", "https://oracle.agentria.eth.example", signer=oracle_agent)

    assert resolver.text(ORACLE_NODE, "endpoint") == "https://oracle.agentria.eth.example"


def test_exec_cannot_overwrite_oracles_records():
    """The actual judging bar: EXEC's operator key must not be able to
    write ORACLE's node, even after EXEC has legitimately been granted
    write access to its *own* node. Enforced here at two layers: (1)
    resolver.set_text()'s client-side is_approved() check raises before
    building a transaction, and (2) even bypassing that guard by hitting
    the fake chain's send_raw_transaction() directly (as a real Sepolia
    node's authorised(node) modifier would), the write is rejected."""
    chain, admin, resolver = _setup()
    oracle_agent = Account.from_key(b"\x01" * 32)
    exec_agent = Account.from_key(b"\x02" * 32)
    resolver.grant_operator(ORACLE_NODE, oracle_agent.address, signer=admin)
    resolver.grant_operator(EXEC_NODE, exec_agent.address, signer=admin)

    # Layer 1: the Python wrapper itself refuses.
    with pytest.raises(ResolverPermissionError):
        resolver.set_text(ORACLE_NODE, "endpoint", "https://exec-takeover.example", signer=exec_agent)

    # Layer 2: even going around resolver.py and hitting the chain
    # directly with a correctly-signed setText call from EXEC's own key
    # -- exactly what a malicious/buggy client could attempt -- the fake
    # chain's authorised(node) equivalent still reverts it.
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


def test_operator_approved_for_all_is_also_honoured():
    chain, admin, resolver = _setup()
    global_operator = Account.from_key(b"\x03" * 32)
    chain.operator_approvals[(admin.address.lower(), global_operator.address.lower())] = True
    assert resolver.is_approved(ORACLE_NODE, global_operator.address) is True
