// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title TrustScore
/// @notice On-chain decentralized trust ledger for ONDC network participants.
/// Mirrors the scoring rules implemented in blockchain/chain.py, which is
/// used to demo this behavior instantly in the Streamlit dashboard without
/// a wallet or testnet RPC connection.
contract TrustScore {
    address public owner;

    uint256 public constant BASE_SCORE = 50;
    uint256 public constant MAX_SCORE = 100;

    mapping(address => uint256) public scores;
    mapping(address => bool) public registered;
    mapping(address => bool) public authorizedReporters;

    event ParticipantRegistered(address indexed participant);
    event ScoreUpdated(address indexed participant, int256 delta, uint256 newScore, string eventType);
    event ReporterAuthorized(address indexed reporter, bool authorized);

    modifier onlyOwner() {
        require(msg.sender == owner, "TrustScore: caller is not owner");
        _;
    }

    modifier onlyAuthorized() {
        require(authorizedReporters[msg.sender] || msg.sender == owner, "TrustScore: not authorized");
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedReporters[msg.sender] = true;
    }

    function setReporter(address reporter, bool authorized) external onlyOwner {
        authorizedReporters[reporter] = authorized;
        emit ReporterAuthorized(reporter, authorized);
    }

    function register(address participant) external onlyAuthorized {
        require(!registered[participant], "TrustScore: already registered");
        registered[participant] = true;
        scores[participant] = BASE_SCORE;
        emit ParticipantRegistered(participant);
    }

    function recordEvent(address participant, string calldata eventType) external onlyAuthorized {
        require(registered[participant], "TrustScore: not registered");

        int256 delta = _deltaFor(eventType);
        int256 newScoreSigned = int256(scores[participant]) + delta;

        if (newScoreSigned < 0) newScoreSigned = 0;
        if (newScoreSigned > int256(MAX_SCORE)) newScoreSigned = int256(MAX_SCORE);

        scores[participant] = uint256(newScoreSigned);
        emit ScoreUpdated(participant, delta, scores[participant], eventType);
    }

    function _deltaFor(string calldata eventType) internal pure returns (int256) {
        bytes32 e = keccak256(bytes(eventType));
        if (e == keccak256("successful_delivery")) return 2;
        if (e == keccak256("on_time")) return 1;
        if (e == keccak256("late_delivery")) return -1;
        if (e == keccak256("dispute_raised")) return -3;
        if (e == keccak256("dispute_resolved_seller")) return 2;
        if (e == keccak256("dispute_resolved_buyer")) return -5;
        if (e == keccak256("fraud_flagged")) return -20;
        revert("TrustScore: unknown event type");
    }

    function scoreOf(address participant) external view returns (uint256) {
        return scores[participant];
    }
}
