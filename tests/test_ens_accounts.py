import pytest
from eth_account import Account

from ens.accounts import (
    ENS_PRIVATE_KEY_ENV,
    MissingCredentialError,
    derive_agent_account,
    has_admin_key,
    load_admin_account,
)

TEST_KEY = "0x" + "11" * 32


def test_has_admin_key_false_when_unset(monkeypatch):
    monkeypatch.delenv(ENS_PRIVATE_KEY_ENV, raising=False)
    assert has_admin_key() is False


def test_has_admin_key_true_when_set(monkeypatch):
    monkeypatch.setenv(ENS_PRIVATE_KEY_ENV, TEST_KEY)
    assert has_admin_key() is True


def test_load_admin_account_raises_without_key(monkeypatch):
    monkeypatch.delenv(ENS_PRIVATE_KEY_ENV, raising=False)
    with pytest.raises(MissingCredentialError, match=ENS_PRIVATE_KEY_ENV):
        load_admin_account()


def test_load_admin_account_reads_key(monkeypatch):
    monkeypatch.setenv(ENS_PRIVATE_KEY_ENV, TEST_KEY)
    account = load_admin_account()
    assert account.address == Account.from_key(TEST_KEY).address


def test_derive_agent_account_is_deterministic():
    admin = Account.from_key(TEST_KEY)
    a1 = derive_agent_account(admin, "oracle")
    a2 = derive_agent_account(admin, "oracle")
    assert a1.address == a2.address


def test_derive_agent_account_differs_per_agent_and_from_admin():
    admin = Account.from_key(TEST_KEY)
    addresses = {admin.address}
    for agent_id in ("recon", "oracle", "exec", "audit"):
        derived = derive_agent_account(admin, agent_id)
        assert derived.address not in addresses  # distinct from admin + every prior agent
        addresses.add(derived.address)
    assert len(addresses) == 5
