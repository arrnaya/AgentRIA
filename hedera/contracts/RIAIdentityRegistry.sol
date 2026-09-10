// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title RIAIdentityRegistry
/// @notice Minimal ERC-8004 (draft, https://eips.ethereum.org/EIPS/eip-8004)
/// Identity Registry for RIA's agents on Hedera testnet. Scope is
/// deliberately limited to the Identity Registry -- the Reputation and
/// Validation registries the draft EIP also defines are out of scope for
/// this repo (see README.md > Layer 3 -- Identity & Visibility and
/// hedera/erc8004.py's module docstring).
///
/// ERC-721-lite by design: this implements only the read surface an
/// ERC-721-aware indexer needs to resolve an agent id to its owner and
/// registration document (`ownerOf`, `tokenURI`) plus the write surface
/// ERC-8004 itself defines (`register`, `setAgentURI`, `setMetadata`,
/// `getMetadata`) -- NOT the full ERC-721 transfer/approval mechanics
/// (`transferFrom`, `approve`, `safeTransferFrom`, ...). Agent identities
/// here are permanent registration records, not tradable tokens, and the
/// draft EIP only requires the registry to be "ERC-721-based", not fully
/// ERC-721 compliant. A production deployment wanting marketplace/wallet
/// compatibility would want full ERC-721 (e.g. OpenZeppelin's
/// implementation) -- deliberately skipped here to keep this a
/// single-file, dependency-free contract that's easy to read, compile,
/// and audit for a hackathon-scope identity registry.
///
/// Verified directly against a fresh fetch of the EIP-8004 draft text
/// (2026-09-10) for the exact interface this contract implements:
/// MetadataEntry{metadataKey,metadataValue}, register(string,
/// MetadataEntry[]) returns (uint256 agentId), setAgentURI(uint256,
/// string), getMetadata/setMetadata(uint256,string[,bytes]), and the
/// Registered/URIUpdated/MetadataSet events. The two extra `register`
/// overloads (no args, agentURI-only) are also defined directly in the
/// EIP text and are used here specifically so hedera/erc8004.py's Python
/// caller never has to ABI-encode a dynamic array of structs through
/// hiero_sdk_python's ContractFunctionParameters helper (which has no
/// struct/tuple encoding support at all -- confirmed by reading
/// contract_function_parameters.py in the installed 0.2.10 package: only
/// scalar/array-of-scalar add_* methods exist). Metadata is instead
/// attached with one setMetadata() call per key after the agentURI-only
/// register() -- functionally equivalent on-chain state, just two
/// transactions instead of one atomic call.
contract RIAIdentityRegistry {
    struct MetadataEntry {
        string metadataKey;
        bytes metadataValue;
    }

    event Registered(uint256 indexed agentId, string agentURI, address indexed owner);
    event URIUpdated(uint256 indexed agentId, string newURI, address indexed updatedBy);
    event MetadataSet(uint256 indexed agentId, string indexed indexedMetadataKey, string metadataKey, bytes metadataValue);

    uint256 private _nextAgentId = 1;

    mapping(uint256 => address) private _owners;
    mapping(uint256 => string) private _agentURIs;
    mapping(uint256 => mapping(string => bytes)) private _metadata;

    function _register(address owner, string memory agentURI) private returns (uint256 agentId) {
        agentId = _nextAgentId++;
        _owners[agentId] = owner;
        _agentURIs[agentId] = agentURI;
        emit Registered(agentId, agentURI, owner);
    }

    function _requireOwner(uint256 agentId) private view {
        require(_owners[agentId] != address(0), "agent does not exist");
        require(_owners[agentId] == msg.sender, "not agent owner");
    }

    /// @notice register() with no agentURI, per the EIP-8004 interface.
    function register() external returns (uint256 agentId) {
        return _register(msg.sender, "");
    }

    /// @notice register() with an agentURI but no inline metadata -- the
    /// overload hedera/erc8004.py actually calls (see contract docstring).
    function register(string calldata agentURI) external returns (uint256 agentId) {
        return _register(msg.sender, agentURI);
    }

    /// @notice Full EIP-8004 signature: register with an agentURI and an
    /// inline metadata array in one atomic call. Present for interface
    /// completeness / any ERC-8004-aware caller that *can* encode
    /// MetadataEntry[] (e.g. via eth_abi or a Solidity/JS client) -- not
    /// exercised by this repo's own Python caller, which uses the
    /// agentURI-only overload above plus separate setMetadata() calls.
    function register(string calldata agentURI, MetadataEntry[] calldata metadata) external returns (uint256 agentId) {
        agentId = _register(msg.sender, agentURI);
        for (uint256 i = 0; i < metadata.length; i++) {
            _metadata[agentId][metadata[i].metadataKey] = metadata[i].metadataValue;
            emit MetadataSet(agentId, metadata[i].metadataKey, metadata[i].metadataKey, metadata[i].metadataValue);
        }
    }

    function setAgentURI(uint256 agentId, string calldata newURI) external {
        _requireOwner(agentId);
        _agentURIs[agentId] = newURI;
        emit URIUpdated(agentId, newURI, msg.sender);
    }

    function setMetadata(uint256 agentId, string calldata metadataKey, bytes calldata metadataValue) external {
        _requireOwner(agentId);
        _metadata[agentId][metadataKey] = metadataValue;
        emit MetadataSet(agentId, metadataKey, metadataKey, metadataValue);
    }

    function getMetadata(uint256 agentId, string calldata metadataKey) external view returns (bytes memory) {
        return _metadata[agentId][metadataKey];
    }

    function ownerOf(uint256 agentId) external view returns (address) {
        address owner = _owners[agentId];
        require(owner != address(0), "agent does not exist");
        return owner;
    }

    function tokenURI(uint256 agentId) external view returns (string memory) {
        require(_owners[agentId] != address(0), "agent does not exist");
        return _agentURIs[agentId];
    }

    /// @notice Total number of agents registered so far. Used by
    /// hedera/erc8004.py to determine a just-registered agent's id
    /// without needing to decode a ContractExecuteTransaction's return
    /// value (Hedera contract calls don't return function results through
    /// the transaction receipt -- only a TransactionRecord's
    /// contractFunctionResult does, which this repo's simpler
    /// register-then-query pattern avoids depending on).
    function agentCount() external view returns (uint256) {
        return _nextAgentId - 1;
    }
}
