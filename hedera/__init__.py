"""ORACLE's Hedera-side code: wallet, x402 client, HCS audit writer.

Containment rule (see README.md > Layer 2): ORACLE is the *only* agent with
HBAR payment authority. `hedera/wallet.py` and `hedera/x402_client.py` are
the only modules in this repo allowed to hold wallet credentials or sign a
transaction. `agents/recon.py`, `scout.py`, `risk.py`, `exec.py`, `audit.py`
must never import from this package's payment-holding modules.
"""
