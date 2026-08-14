require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

const { SEPOLIA_RPC_URL, PRIVATE_KEY, LOCAL_RPC_URL } = process.env;

module.exports = {
  solidity: {
    // Bumped from 0.8.19 for @openzeppelin/contracts v5's ReentrancyGuard
    // (pragma ^0.8.20) — both TrustScore.sol and EscrowDispute.sol declare
    // `pragma solidity ^0.8.19`, which is satisfied by any 0.8.x >= 0.8.19,
    // so this is a compiler-version bump, not a contract source change.
    version: "0.8.24",
    settings: { optimizer: { enabled: true, runs: 200 } },
  },
  networks: {
    hardhat: {},
    // A standalone local chain — `npx hardhat node` (port 8545) or Ganache
    // CLI (also 8545 by default; override LOCAL_RPC_URL for Ganache GUI's
    // default of 7545). Unlike the `hardhat` network above, this persists
    // state across separate `hardhat run`/backend invocations, which is
    // what a backend integration test against a real chain needs.
    localhost: {
      url: LOCAL_RPC_URL || "http://127.0.0.1:8545",
    },
    sepolia: {
      url: SEPOLIA_RPC_URL || "",
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
  },
};
