from eth_utils import keccak

from ens.abi import Function


def test_signature_and_selector_match_solidity_convention():
    fn = Function("setText", ("bytes32", "string", "string"))
    assert fn.signature == "setText(bytes32,string,string)"
    assert fn.selector == keccak(text="setText(bytes32,string,string)")[:4]
    assert len(fn.selector) == 4


def test_encode_call_starts_with_selector():
    fn = Function("approve", ("bytes32", "address", "bool"))
    node = b"\x01" * 32
    data = fn.encode_call(node, "0x" + "22" * 20, True)
    assert data[:4] == fn.selector
    assert len(data) > 4


def test_encode_then_decode_round_trips():
    fn = Function("text", ("bytes32", "string"), ("string",))
    call = fn.encode_call(b"\x02" * 32, "endpoint")
    assert call[:4] == fn.selector
    # Simulate what a contract would return for this call.
    from eth_abi import encode as abi_encode

    result = abi_encode(["string"], ["https://example.com"])
    (decoded,) = fn.decode_output(result)
    assert decoded == "https://example.com"
