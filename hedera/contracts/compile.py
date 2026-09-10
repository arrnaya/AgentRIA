"""Regenerates `hedera/contracts/RIAIdentityRegistry.json` (abi + bytecode)
from `RIAIdentityRegistry.sol`.

NOT run by pytest and NOT imported by `hedera/erc8004.py` at runtime --
`erc8004.py` only ever reads the checked-in `.json` artifact, so deploying
or testing this module never requires `solc`/`py-solc-x` to be installed.
Run this by hand only when you've edited the `.sol` source and need to
regenerate the artifact:

    pip install py-solc-x   # not in requirements.txt -- compile-time only
    python -m hedera.contracts.compile

Requires network access the first time (py-solc-x downloads the solc
0.8.24 binary from GitHub releases) -- fine for a local dev machine, not
something CI or the sandboxed agent environment should need to do again
once the artifact is committed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SOURCE_PATH = Path(__file__).parent / "RIAIdentityRegistry.sol"
ARTIFACT_PATH = Path(__file__).parent / "RIAIdentityRegistry.json"
SOLC_VERSION = "0.8.24"


def main() -> int:
    try:
        import solcx
    except ImportError:
        print("py-solc-x is not installed. Run: pip install py-solc-x", file=sys.stderr)
        return 1

    installed = solcx.get_installed_solc_versions()
    if not any(str(v) == SOLC_VERSION for v in installed):
        print(f"Installing solc {SOLC_VERSION} (one-time, needs network access)...")
        solcx.install_solc(SOLC_VERSION)

    solcx.set_solc_version(SOLC_VERSION)
    out = solcx.compile_files(
        [str(SOURCE_PATH)],
        output_values=["abi", "bin"],
        optimize=True,
        optimize_runs=200,
        solc_version=SOLC_VERSION,
    )
    matches = [k for k in out if k.endswith(":RIAIdentityRegistry") or k.endswith("RIAIdentityRegistry")]
    if not matches:
        print(f"Could not find RIAIdentityRegistry in solc output: {list(out)}", file=sys.stderr)
        return 1
    contract = out[matches[0]]

    artifact = {
        "contractName": "RIAIdentityRegistry",
        "solcVersion": SOLC_VERSION,
        "optimizer": {"enabled": True, "runs": 200},
        "abi": contract["abi"],
        "bytecode": contract["bin"],
    }
    with ARTIFACT_PATH.open("w") as f:
        json.dump(artifact, f, indent=2)
        f.write("\n")

    print(f"Wrote {ARTIFACT_PATH} ({len(contract['bin']) // 2} bytes of bytecode)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
