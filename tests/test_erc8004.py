"""Tests for hedera/erc8004.py -- no live credentials, no network.

Mocks the hiero_sdk_python SDK surface the same way test_wallet.py and
test_hcs_logger.py do: substitute the names hedera.erc8004 imported,
never touch the network. The one real, unmocked dependency is the
checked-in hedera/contracts/RIAIdentityRegistry.json artifact -- reading
it is a local file read, not network access.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

import pytest

import hedera.erc8004 as erc8004_module
import hedera.key_loader as key_loader_module
from hedera.erc8004 import (
    AGENT_TABLE,
    Erc8004ConfigError,
    Erc8004DeployError,
    Erc8004RegisterError,
    build_agent_uri,
    build_operator,
    deploy_registry,
    load_artifact,
    register_agent,
    verify_agent,
)

DEFAULT_PUBLIC_KEY_HEX = "aabbccddeeff"


class _FakeAccountId:
    def __init__(self, raw: str):
        self.raw = raw

    @classmethod
    def from_string(cls, s: str) -> "_FakeAccountId":
        if s == "bad-account":
            raise ValueError("bad account id")
        return cls(s)

    def __str__(self) -> str:
        return self.raw


class _FakePublicKey:
    def __init__(self, raw_hex: str):
        self._raw_hex = raw_hex

    def to_string_raw(self) -> str:
        return self._raw_hex


class _FakePrivateKey:
    public_key_hex = DEFAULT_PUBLIC_KEY_HEX

    def __init__(self, raw: str = "key"):
        self.raw = raw

    @classmethod
    def from_string_ecdsa(cls, s: str) -> "_FakePrivateKey":
        return cls(s)

    @classmethod
    def from_string_ed25519(cls, s: str) -> "_FakePrivateKey":
        return cls(s)

    def public_key(self) -> _FakePublicKey:
        return _FakePublicKey(self.public_key_hex)


class _FakeFileId:
    def __init__(self, raw: str = "0.0.5001"):
        self.raw = raw

    def __str__(self) -> str:
        return self.raw


class _FakeContractId:
    def __init__(self, raw: str = "0.0.6001", evm: str = "00" * 20):
        self.raw = raw
        self._evm = evm

    def __str__(self) -> str:
        return self.raw

    def to_evm_address(self) -> str:
        return self._evm


def _patch_sdk(monkeypatch, fake_client: MagicMock | None = None):
    fake_client = fake_client or MagicMock(name="Client")
    monkeypatch.setattr(erc8004_module, "AccountId", _FakeAccountId)
    monkeypatch.setattr(key_loader_module, "PrivateKey", _FakePrivateKey)
    monkeypatch.setattr(erc8004_module, "Client", MagicMock(for_testnet=MagicMock(return_value=fake_client)))
    _FakePrivateKey.public_key_hex = DEFAULT_PUBLIC_KEY_HEX
    return fake_client


def _patch_mirror_node(monkeypatch, *, key_type: str = "ECDSA_SECP256K1", public_key_hex: str = DEFAULT_PUBLIC_KEY_HEX):
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"key": {"_type": key_type, "key": public_key_hex}}
    monkeypatch.setattr(key_loader_module.httpx, "get", MagicMock(return_value=fake_response))


# --- build_operator -----------------------------------------------------


def test_build_operator_rejects_malformed_account_id(monkeypatch):
    _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch)
    with pytest.raises(Erc8004ConfigError, match="not a valid Hedera account id"):
        build_operator("bad-account", "302e...")


def test_build_operator_builds_and_sets_operator(monkeypatch):
    fake_client = _patch_sdk(monkeypatch)
    _patch_mirror_node(monkeypatch)

    account_id, private_key, client = build_operator("0.0.1234", "302e...")

    assert account_id.raw == "0.0.1234"
    assert client is fake_client
    fake_client.set_operator.assert_called_once_with(account_id, private_key)


# --- load_artifact --------------------------------------------------------


def test_load_artifact_reads_checked_in_json():
    artifact = load_artifact()
    assert artifact["contractName"] == "RIAIdentityRegistry"
    assert "abi" in artifact and "bytecode" in artifact
    function_names = {e["name"] for e in artifact["abi"] if e["type"] == "function"}
    assert {"register", "setAgentURI", "setMetadata", "getMetadata", "ownerOf", "tokenURI", "agentCount"} <= function_names


def test_load_artifact_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(erc8004_module, "CONTRACT_ARTIFACT_PATH", tmp_path / "does-not-exist.json")
    with pytest.raises(Erc8004ConfigError, match="not found"):
        load_artifact()


# --- build_agent_uri --------------------------------------------------------


def test_build_agent_uri_unknown_agent_raises():
    with pytest.raises(Erc8004ConfigError, match="Unknown agent_key"):
        build_agent_uri("nonexistent")


@pytest.mark.parametrize("agent_key", sorted(AGENT_TABLE))
def test_build_agent_uri_encodes_expected_fields(agent_key):
    uri = build_agent_uri(agent_key)
    assert uri.startswith("data:application/json;base64,")
    payload = base64.b64decode(uri.split(",", 1)[1])
    doc = json.loads(payload)
    assert doc["name"] == AGENT_TABLE[agent_key]["name"]
    assert doc["capabilities"] == AGENT_TABLE[agent_key]["capabilities"]
    assert doc["active"] is True
    assert doc["x402Support"] == (agent_key == "oracle")


# --- deploy_registry --------------------------------------------------------


def _patch_deploy_transactions(monkeypatch, *, file_id=None, contract_id=None):
    file_id = file_id or _FakeFileId()
    contract_id = contract_id or _FakeContractId()

    fake_file_tx = MagicMock()
    fake_file_tx.set_keys.return_value = fake_file_tx
    fake_file_tx.set_contents.return_value = fake_file_tx
    fake_file_tx.set_file_memo.return_value = fake_file_tx
    fake_file_receipt = MagicMock(file_id=file_id)
    fake_file_tx.execute.return_value = fake_file_receipt
    monkeypatch.setattr(erc8004_module, "FileCreateTransaction", MagicMock(return_value=fake_file_tx))

    fake_append_tx = MagicMock()
    fake_append_tx.set_file_id.return_value = fake_append_tx
    fake_append_tx.set_contents.return_value = fake_append_tx
    monkeypatch.setattr(erc8004_module, "FileAppendTransaction", MagicMock(return_value=fake_append_tx))

    fake_contract_tx = MagicMock()
    fake_contract_tx.set_bytecode_file_id.return_value = fake_contract_tx
    fake_contract_tx.set_gas.return_value = fake_contract_tx
    fake_contract_tx.set_admin_key.return_value = fake_contract_tx
    fake_contract_tx.set_contract_memo.return_value = fake_contract_tx
    fake_contract_receipt = MagicMock(contract_id=contract_id)
    fake_contract_tx.execute.return_value = fake_contract_receipt
    monkeypatch.setattr(erc8004_module, "ContractCreateTransaction", MagicMock(return_value=fake_contract_tx))

    return fake_file_tx, fake_append_tx, fake_contract_tx


def test_deploy_registry_skips_append_when_bytecode_fits_in_one_chunk(monkeypatch):
    fake_file_tx, fake_append_tx, fake_contract_tx = _patch_deploy_transactions(monkeypatch)
    client = MagicMock()
    private_key = _FakePrivateKey()

    # The real checked-in artifact is ~3.5KB, under FIRST_FILE_CHUNK_BYTES
    # (4000), so no FileAppendTransaction should be constructed at all.
    result = deploy_registry(client, private_key)

    fake_file_tx.execute.assert_called_once_with(client, validate_status=True)
    fake_append_tx.execute_all.assert_not_called()
    fake_contract_tx.execute.assert_called_once_with(client, validate_status=True)
    assert result.file_id == "0.0.5001"
    assert result.contract_id == "0.0.6001"
    assert result.contract_evm_address == "00" * 20


def test_deploy_registry_appends_remainder_when_bytecode_exceeds_first_chunk(monkeypatch):
    fake_file_tx, fake_append_tx, fake_contract_tx = _patch_deploy_transactions(monkeypatch)
    # Force a larger-than-one-chunk bytecode via a fake artifact.
    big_bytecode_hex = ("ab" * 5000)
    monkeypatch.setattr(erc8004_module, "load_artifact", lambda: {"bytecode": big_bytecode_hex})
    client = MagicMock()
    private_key = _FakePrivateKey()

    deploy_registry(client, private_key)

    fake_append_tx.set_contents.assert_called_once()
    (remainder,), _ = fake_append_tx.set_contents.call_args
    assert len(remainder) == 5000 - erc8004_module.FIRST_FILE_CHUNK_BYTES
    fake_append_tx.execute_all.assert_called_once_with(client)


def test_deploy_registry_raises_when_file_create_receipt_has_no_file_id(monkeypatch):
    fake_file_tx, _, _ = _patch_deploy_transactions(monkeypatch, file_id=None)
    fake_file_tx.execute.return_value = MagicMock(file_id=None)
    client = MagicMock()

    with pytest.raises(Erc8004DeployError, match="no file_id"):
        deploy_registry(client, _FakePrivateKey())


def test_deploy_registry_raises_when_contract_create_receipt_has_no_contract_id(monkeypatch):
    _patch_deploy_transactions(monkeypatch, contract_id=None)
    client = MagicMock()

    # Patch the contract tx's execute return to have contract_id=None
    fake_contract_tx = erc8004_module.ContractCreateTransaction.return_value
    fake_contract_tx.execute.return_value = MagicMock(contract_id=None)

    with pytest.raises(Erc8004DeployError, match="no contract_id"):
        deploy_registry(client, _FakePrivateKey())


def test_deploy_registry_wraps_unexpected_sdk_errors(monkeypatch):
    monkeypatch.setattr(
        erc8004_module, "FileCreateTransaction", MagicMock(side_effect=RuntimeError("grpc unavailable"))
    )
    with pytest.raises(Erc8004DeployError, match="Failed to deploy"):
        deploy_registry(MagicMock(), _FakePrivateKey())


# --- register_agent --------------------------------------------------------


def _make_call_query_factory(results):
    """Each ContractCallQuery() call returns a fresh chainable mock whose
    final .execute(client) pops the next canned result off `results`."""
    queue = list(results)

    def factory(*args, **kwargs):
        q = MagicMock()
        q.set_contract_id.return_value = q
        q.set_gas.return_value = q
        q.set_function.return_value = q
        q.execute.return_value = queue.pop(0)
        return q

    return MagicMock(side_effect=factory)


def _fake_count_result(n: int) -> MagicMock:
    result = MagicMock()
    result.get_uint256.return_value = n
    return result


def _patch_execute_transaction(monkeypatch, *, tx_id="0.0.1234@1700000000.000000000"):
    fake_tx = MagicMock()
    fake_tx.set_contract_id.return_value = fake_tx
    fake_tx.set_gas.return_value = fake_tx
    fake_tx.set_function.return_value = fake_tx

    fake_receipt = MagicMock()
    fake_receipt.transaction_id = tx_id
    fake_response = MagicMock()
    fake_response.get_receipt.return_value = fake_receipt
    fake_tx.execute.return_value = fake_response

    monkeypatch.setattr(erc8004_module, "ContractExecuteTransaction", MagicMock(return_value=fake_tx))
    return fake_tx, fake_response, fake_receipt


def test_register_agent_happy_path_computes_agent_id_from_count_delta(monkeypatch):
    monkeypatch.setattr(erc8004_module, "ContractCallQuery", _make_call_query_factory([_fake_count_result(2), _fake_count_result(3)]))
    fake_tx, fake_response, _ = _patch_execute_transaction(monkeypatch)
    client = MagicMock()
    account_id = _FakeAccountId("0.0.1234")
    private_key = _FakePrivateKey()
    contract_id = _FakeContractId()

    result = register_agent(client, account_id, private_key, contract_id, agent_key="oracle")

    assert result.agent_id == 3
    assert result.agent_key == "oracle"
    assert result.name == "ORACLE"
    assert result.owner_account_id == "0.0.1234"
    assert result.global_agent_id == f"eip155:296:0x{contract_id.to_evm_address()}:3"
    assert result.register_tx_id == "0.0.1234@1700000000.000000000"
    fake_tx.set_function.assert_called_once()
    name_arg, params_arg = fake_tx.set_function.call_args[0]
    assert name_arg == "register"


def test_register_agent_unknown_agent_key_raises():
    with pytest.raises(Erc8004ConfigError, match="Unknown agent_key"):
        register_agent(MagicMock(), _FakeAccountId("0.0.1"), _FakePrivateKey(), _FakeContractId(), agent_key="nope")


def test_register_agent_raises_when_agent_count_does_not_increment_by_one(monkeypatch):
    # before=2, after=2 -- register() silently didn't create a new agent.
    monkeypatch.setattr(erc8004_module, "ContractCallQuery", _make_call_query_factory([_fake_count_result(2), _fake_count_result(2)]))
    _patch_execute_transaction(monkeypatch)

    with pytest.raises(Erc8004RegisterError, match=r"went from 2 to 2"):
        register_agent(MagicMock(), _FakeAccountId("0.0.1"), _FakePrivateKey(), _FakeContractId(), agent_key="recon")


def test_register_agent_sets_metadata_for_each_key(monkeypatch):
    monkeypatch.setattr(erc8004_module, "ContractCallQuery", _make_call_query_factory([_fake_count_result(0), _fake_count_result(1)]))
    fake_tx, _, _ = _patch_execute_transaction(monkeypatch)

    result = register_agent(
        MagicMock(),
        _FakeAccountId("0.0.1234"),
        _FakePrivateKey(),
        _FakeContractId(),
        agent_key="audit",
        metadata={"hcs-topic-id": b"0.0.7777", "version": b"1.0.0"},
    )

    assert set(result.metadata_tx_ids) == {"hcs-topic-id", "version"}
    # 1 register call + 2 setMetadata calls == 3 total set_function calls.
    assert fake_tx.set_function.call_count == 3
    function_names = [call.args[0] for call in fake_tx.set_function.call_args_list]
    assert function_names == ["register", "setMetadata", "setMetadata"]


def test_register_agent_wraps_unexpected_sdk_errors(monkeypatch):
    monkeypatch.setattr(erc8004_module, "ContractCallQuery", _make_call_query_factory([_fake_count_result(0)]))
    monkeypatch.setattr(
        erc8004_module, "ContractExecuteTransaction", MagicMock(side_effect=RuntimeError("grpc unavailable"))
    )
    with pytest.raises(Erc8004RegisterError, match="Failed to register agent"):
        register_agent(MagicMock(), _FakeAccountId("0.0.1"), _FakePrivateKey(), _FakeContractId(), agent_key="exec")


# --- verify_agent --------------------------------------------------------


def test_verify_agent_reads_owner_and_token_uri(monkeypatch):
    owner_result = MagicMock()
    owner_result.get_address.return_value = "abc123"
    uri_result = MagicMock()
    uri_result.get_string.return_value = "data:application/json;base64,xyz"

    monkeypatch.setattr(erc8004_module, "ContractCallQuery", _make_call_query_factory([owner_result, uri_result]))

    info = verify_agent(MagicMock(), _FakeContractId(), 3)

    assert info == {"owner": "abc123", "token_uri": "data:application/json;base64,xyz"}
