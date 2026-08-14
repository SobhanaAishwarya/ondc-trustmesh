const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("EscrowDispute", function () {
  async function deployFixture() {
    const [, buyer, seller, arbitrator] = await ethers.getSigners();

    const TrustScore = await ethers.getContractFactory("TrustScore");
    const trustScore = await TrustScore.deploy();

    const EscrowDispute = await ethers.getContractFactory("EscrowDispute");
    const escrow = await EscrowDispute.deploy(await trustScore.getAddress(), arbitrator.address);

    await trustScore.setReporter(await escrow.getAddress(), true);
    await trustScore.register(seller.address);
    await trustScore.register(buyer.address);

    return { trustScore, escrow, buyer, seller, arbitrator };
  }

  it("releases funds to the seller on confirmed delivery", async function () {
    const { escrow, buyer, seller } = await deployFixture();
    const amount = ethers.parseEther("1");

    await escrow.connect(buyer).createOrder(seller.address, { value: amount });
    const before = await ethers.provider.getBalance(seller.address);

    await escrow.connect(buyer).confirmDelivery(0);

    const after = await ethers.provider.getBalance(seller.address);
    expect(after - before).to.equal(amount);
  });

  it("records a dispute and drops the seller's trust score", async function () {
    const { trustScore, escrow, buyer, seller } = await deployFixture();
    const amount = ethers.parseEther("1");

    await escrow.connect(buyer).createOrder(seller.address, { value: amount });
    await escrow.connect(buyer).raiseDispute(0, "item_not_received");

    expect(await trustScore.scoreOf(seller.address)).to.equal(47);
  });

  it("splits escrow proportionally to trust score on auto-resolve", async function () {
    const { escrow, buyer, seller } = await deployFixture();
    const amount = ethers.parseEther("1");

    await escrow.connect(buyer).createOrder(seller.address, { value: amount });
    await escrow.connect(buyer).raiseDispute(0, "item_not_received");

    await expect(escrow.autoResolve(0)).to.emit(escrow, "DisputeResolved");
  });

  it("lets the arbitrator override the outcome", async function () {
    const { escrow, buyer, seller, arbitrator } = await deployFixture();
    const amount = ethers.parseEther("1");

    await escrow.connect(buyer).createOrder(seller.address, { value: amount });
    await escrow.connect(buyer).raiseDispute(0, "item_not_as_described");

    await expect(
      escrow.connect(arbitrator).arbitratorResolve(0, 10000)
    ).to.emit(escrow, "DisputeResolved");
  });

  it("rejects arbitrator overrides from non-arbitrators", async function () {
    const { escrow, buyer, seller } = await deployFixture();
    const amount = ethers.parseEther("1");

    await escrow.connect(buyer).createOrder(seller.address, { value: amount });
    await escrow.connect(buyer).raiseDispute(0, "item_not_as_described");

    await expect(
      escrow.connect(buyer).arbitratorResolve(0, 10000)
    ).to.be.revertedWith("EscrowDispute: not arbitrator");
  });

  it("reverts cleanly if the fund transfer to the recipient fails", async function () {
    // Proves _sendFunds's call+require actually surfaces a failed
    // transfer as a clear revert, rather than the old .transfer()'s
    // opaque failure — a contract with no payable receive/fallback can't
    // accept plain ETH, so this must revert, not silently drop the funds.
    const { trustScore, escrow, buyer } = await deployFixture();

    const RejectsEther = await ethers.getContractFactory("RejectsEther");
    const badSeller = await RejectsEther.deploy();
    const badSellerAddress = await badSeller.getAddress();
    await trustScore.register(badSellerAddress);

    const amount = ethers.parseEther("1");
    await escrow.connect(buyer).createOrder(badSellerAddress, { value: amount });

    await expect(escrow.connect(buyer).confirmDelivery(0)).to.be.revertedWith(
      "EscrowDispute: fund transfer failed"
    );
  });
});
