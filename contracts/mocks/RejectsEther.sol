// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title RejectsEther
/// @notice Test-only contract with no payable receive/fallback, so any ETH
/// sent to it reverts. Used by test/EscrowDispute.test.js to prove fund
/// transfers fail loudly (a clear `require` message) rather than the
/// silent, opaque failure `.transfer()` produced — see EscrowDispute.sol's
/// `_sendFunds`. Never deployed as part of the real system.
contract RejectsEther {}
