// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "./TrustScore.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title EscrowDispute
/// @notice Holds buyer funds in escrow per ONDC order and automates dispute
/// resolution using each party's on-chain trust score, with an arbitrator
/// able to override when the case needs manual review.
contract EscrowDispute is ReentrancyGuard {
    enum Status { Created, Delivered, Disputed, Resolved }

    struct Order {
        address buyer;
        address seller;
        uint256 amount;
        Status status;
        uint256 createdAt;
        string disputeReason;
    }

    TrustScore public trustScore;
    address public arbitrator;
    uint256 public orderCount;
    mapping(uint256 => Order) public orders;

    uint256 public constant AUTO_RESOLVE_THRESHOLD_BPS = 6500; // 65% share -> counted as a seller win

    event OrderCreated(uint256 indexed orderId, address indexed buyer, address indexed seller, uint256 amount);
    event DeliveryConfirmed(uint256 indexed orderId);
    event DisputeRaised(uint256 indexed orderId, string reason);
    event DisputeResolved(uint256 indexed orderId, address winner, uint256 sellerShareBps);

    modifier onlyArbitrator() {
        require(msg.sender == arbitrator, "EscrowDispute: not arbitrator");
        _;
    }

    constructor(address trustScoreAddress, address arbitratorAddress) {
        trustScore = TrustScore(trustScoreAddress);
        arbitrator = arbitratorAddress;
    }

    function createOrder(address seller) external payable returns (uint256 orderId) {
        require(msg.value > 0, "EscrowDispute: amount required");
        orderId = orderCount++;
        orders[orderId] = Order({
            buyer: msg.sender,
            seller: seller,
            amount: msg.value,
            status: Status.Created,
            createdAt: block.timestamp,
            disputeReason: ""
        });
        emit OrderCreated(orderId, msg.sender, seller, msg.value);
    }

    function confirmDelivery(uint256 orderId) external nonReentrant {
        Order storage order = orders[orderId];
        require(msg.sender == order.buyer, "EscrowDispute: only buyer");
        require(order.status == Status.Created, "EscrowDispute: invalid status");

        // Effects before interaction: status flips and the trust event
        // records before the external transfer, so a reentrant call back
        // into this contract sees Status.Delivered (the require above
        // blocks it) even without the nonReentrant guard — the guard is
        // defense in depth, not the only thing preventing reentrancy here.
        order.status = Status.Delivered;
        trustScore.recordEvent(order.seller, "successful_delivery");
        _sendFunds(order.seller, order.amount);
        emit DeliveryConfirmed(orderId);
    }

    function raiseDispute(uint256 orderId, string calldata reason) external {
        Order storage order = orders[orderId];
        require(msg.sender == order.buyer || msg.sender == order.seller, "EscrowDispute: not a party");
        require(order.status == Status.Created, "EscrowDispute: invalid status");

        order.status = Status.Disputed;
        order.disputeReason = reason;
        trustScore.recordEvent(order.seller, "dispute_raised");
        emit DisputeRaised(orderId, reason);
    }

    /// @notice Automated resolution using both parties' trust scores. Splits
    /// the escrowed amount in proportion to relative trust. The arbitrator
    /// can override via arbitratorResolve when the split needs manual review.
    function autoResolve(uint256 orderId) external nonReentrant {
        Order storage order = orders[orderId];
        require(order.status == Status.Disputed, "EscrowDispute: not disputed");

        uint256 sellerScore = trustScore.scoreOf(order.seller);
        uint256 buyerScore = trustScore.scoreOf(order.buyer);
        uint256 total = sellerScore + buyerScore;
        require(total > 0, "EscrowDispute: no trust data");

        uint256 sellerShareBps = (sellerScore * 10000) / total;
        _settle(orderId, sellerShareBps);
    }

    function arbitratorResolve(uint256 orderId, uint256 sellerShareBps) external onlyArbitrator nonReentrant {
        require(sellerShareBps <= 10000, "EscrowDispute: invalid share");
        _settle(orderId, sellerShareBps);
    }

    function _settle(uint256 orderId, uint256 sellerShareBps) internal {
        Order storage order = orders[orderId];
        require(order.status == Status.Disputed, "EscrowDispute: not disputed");

        // All state (status, trust event) settles before either fund
        // transfer below — checks-effects-interactions, so neither
        // transfer can be replayed against this order even in principle.
        order.status = Status.Resolved;
        uint256 sellerAmount = (order.amount * sellerShareBps) / 10000;
        uint256 buyerAmount = order.amount - sellerAmount;

        if (sellerShareBps >= AUTO_RESOLVE_THRESHOLD_BPS) {
            trustScore.recordEvent(order.seller, "dispute_resolved_seller");
        } else {
            trustScore.recordEvent(order.seller, "dispute_resolved_buyer");
        }

        emit DisputeResolved(orderId, sellerShareBps >= 5000 ? order.seller : order.buyer, sellerShareBps);

        if (sellerAmount > 0) _sendFunds(order.seller, sellerAmount);
        if (buyerAmount > 0) _sendFunds(order.buyer, buyerAmount);
    }

    /// @dev `call` with an explicit success check, not `.transfer()`.
    /// `.transfer()` forwards a fixed 2300-gas stipend, which reverts
    /// unpredictably against any recipient whose receive/fallback needs
    /// more than that (a Gnosis Safe, an upgradeable proxy wallet, or any
    /// future recipient after an EIP-1884-style gas-cost repricing) —
    /// exactly the kind of "past protocol change silently broke this"
    /// bug that shows up years after a contract like this was deployed.
    function _sendFunds(address to, uint256 amount) private {
        (bool success, ) = payable(to).call{value: amount}("");
        require(success, "EscrowDispute: fund transfer failed");
    }
}
