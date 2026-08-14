const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

/// Deploys TrustScore + EscrowDispute and writes their addresses to
/// deployments/<network>.json so the backend's Web3.py bridge
/// (backend/app/blockchain/client.py) knows where to find them without
/// hardcoding an address per environment.
async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  const TrustScore = await hre.ethers.getContractFactory("TrustScore");
  const trustScore = await TrustScore.deploy();
  await trustScore.waitForDeployment();
  const trustScoreAddress = await trustScore.getAddress();
  console.log("TrustScore deployed to:", trustScoreAddress);

  const EscrowDispute = await hre.ethers.getContractFactory("EscrowDispute");
  const escrow = await EscrowDispute.deploy(trustScoreAddress, deployer.address);
  await escrow.waitForDeployment();
  const escrowAddress = await escrow.getAddress();
  console.log("EscrowDispute deployed to:", escrowAddress);

  const tx = await trustScore.setReporter(escrowAddress, true);
  await tx.wait();
  console.log("EscrowDispute authorized as a TrustScore reporter");

  const network = await hre.ethers.provider.getNetwork();
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(deploymentsDir, { recursive: true });

  const outFile = path.join(deploymentsDir, `${hre.network.name}.json`);
  fs.writeFileSync(
    outFile,
    JSON.stringify(
      {
        network: hre.network.name,
        chainId: Number(network.chainId),
        deployer: deployer.address,
        arbitrator: deployer.address,
        contracts: {
          TrustScore: trustScoreAddress,
          EscrowDispute: escrowAddress,
        },
        deployedAt: new Date().toISOString(),
      },
      null,
      2
    )
  );
  console.log(`Wrote deployment addresses to ${outFile}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
