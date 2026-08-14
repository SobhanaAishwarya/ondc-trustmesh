const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("TrustScore", function () {
  it("registers participants at the base score", async function () {
    const [, seller] = await ethers.getSigners();
    const TrustScore = await ethers.getContractFactory("TrustScore");
    const trustScore = await TrustScore.deploy();
    await trustScore.register(seller.address);
    expect(await trustScore.scoreOf(seller.address)).to.equal(50);
  });

  it("increases score on successful delivery and decreases on fraud", async function () {
    const [, seller] = await ethers.getSigners();
    const TrustScore = await ethers.getContractFactory("TrustScore");
    const trustScore = await TrustScore.deploy();
    await trustScore.register(seller.address);

    await trustScore.recordEvent(seller.address, "successful_delivery");
    expect(await trustScore.scoreOf(seller.address)).to.equal(52);

    await trustScore.recordEvent(seller.address, "fraud_flagged");
    expect(await trustScore.scoreOf(seller.address)).to.equal(32);
  });

  it("clamps score between 0 and 100", async function () {
    const [, seller] = await ethers.getSigners();
    const TrustScore = await ethers.getContractFactory("TrustScore");
    const trustScore = await TrustScore.deploy();
    await trustScore.register(seller.address);

    for (let i = 0; i < 5; i++) {
      await trustScore.recordEvent(seller.address, "fraud_flagged");
    }
    expect(await trustScore.scoreOf(seller.address)).to.equal(0);
  });

  it("rejects events from unauthorized reporters", async function () {
    const [, seller, stranger] = await ethers.getSigners();
    const TrustScore = await ethers.getContractFactory("TrustScore");
    const trustScore = await TrustScore.deploy();
    await trustScore.register(seller.address);

    await expect(
      trustScore.connect(stranger).recordEvent(seller.address, "successful_delivery")
    ).to.be.revertedWith("TrustScore: not authorized");
  });
});
