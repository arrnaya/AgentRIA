from ens.namehash import ZERO_NODE, labelhash, namehash


def test_namehash_of_empty_string_is_zero_node():
    assert namehash("") == ZERO_NODE
    assert len(ZERO_NODE) == 32


def test_namehash_is_32_bytes_and_deterministic():
    h1 = namehash("ria.eth")
    h2 = namehash("ria.eth")
    assert h1 == h2
    assert len(h1) == 32


def test_namehash_differs_per_label():
    names = [
        "ria.eth",
        "ria-recon.ria.eth",
        "ria-oracle.ria.eth",
        "ria-exec.ria.eth",
        "ria-audit.ria.eth",
    ]
    hashes = {namehash(n) for n in names}
    assert len(hashes) == len(names)  # every subname gets a distinct node


def test_namehash_matches_manual_recursion():
    # namehash("a.b") == keccak(namehash("b") + labelhash("a")) by
    # definition (EIP-137) -- check our implementation actually recurses
    # that way rather than e.g. hashing labels left-to-right.
    from eth_utils import keccak

    expected = keccak(namehash("eth") + labelhash("ria"))
    assert namehash("ria.eth") == expected


def test_labelhash_is_keccak_of_the_label_text():
    from eth_utils import keccak

    assert labelhash("ria-oracle") == keccak(text="ria-oracle")
