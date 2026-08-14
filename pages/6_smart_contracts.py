import streamlit as st

from theme import page_header

page_header(
    "Settlement Layer",
    "Solidity Smart Contracts",
    "These implement the same trust-scoring and dispute-resolution rules shown "
    "elsewhere in this dashboard, for real deployment on an EVM-compatible testnet.",
)

contract_choice = st.radio("View contract", ["TrustScore.sol", "EscrowDispute.sol"], horizontal=True)
with open(f"contracts/{contract_choice}", encoding="utf-8") as f:
    st.code(f.read(), language="solidity", line_numbers=True)

st.markdown('<div class="section-title">Contract test suite</div>', unsafe_allow_html=True)
st.write(
    "`test/TrustScore.test.js` and `test/EscrowDispute.test.js` cover "
    "registration, score deltas and clamping, authorization checks, escrow "
    "release on delivery, dispute-triggered trust drops, proportional "
    "auto-resolution, and arbitrator overrides."
)

st.markdown('<div class="section-title">Deploying to a testnet</div>', unsafe_allow_html=True)
st.code(
    """# from the project root
npm install
cp .env.example .env        # fill in SEPOLIA_RPC_URL and PRIVATE_KEY
npx hardhat test            # run the contract test suite (test/*.test.js)
npx hardhat run scripts/deploy.js --network sepolia""",
    language="bash",
)
st.caption(
    "Deployment requires your own Sepolia RPC endpoint (e.g. Alchemy/Infura) "
    "and a funded testnet wallet — neither is provisioned here, and this "
    "hasn't been deployed to a live testnet as part of building this prototype."
)
