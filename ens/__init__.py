"""RIA's ENSv2 identity layer (Sepolia testnet).

Each core agent (RECON, ORACLE, EXEC, AUDIT) carries its own ENS subname
under `agentria.eth` with ENSIP-26 text records, isolated by a Permissioned
Resolver so one agent's key can never overwrite another's records. See
README.md > "Layer 3 — Identity & Visibility" > "ENSv2 agent identity
(Sepolia)" for the fixed subname table this module implements.
"""
