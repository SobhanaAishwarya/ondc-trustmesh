from datetime import datetime

import pandas as pd
import streamlit as st

from state import get_chain, get_ctr_snapshot, get_fraud_model, simulate_activity
from theme import EVENT_META, STATUS_GOOD, page_header, status_pill

page_header(
    "TrustMesh · Project 3 Prototype",
    "Blockchain-AI Enhanced ONDC Implementation",
    "Decentralized trust scoring, AI fraud detection, personalized discovery, "
    "and automated dispute resolution for the Open Network for Digital Commerce.",
)

st.markdown(
    """
    <div class="note-card">
    <b>What's real vs. simulated:</b> the fraud model, recommender, and dispute
    logic run live on synthetic ONDC-style data (no public ONDC dataset exists).
    The trust ledger below is a pure-Python hash-chain simulation for instant,
    wallet-free demoing — the equivalent Solidity contracts are on the
    <b>Smart Contracts</b> page for real testnet deployment.
    </div>
    """,
    unsafe_allow_html=True,
)

chain = get_chain()
model, fraud_metrics = get_fraud_model()
ctr = get_ctr_snapshot()

# ---------------------------------------------------
# LIVE NETWORK SNAPSHOT
# ---------------------------------------------------
st.markdown('<div class="section-title">Live Network Snapshot</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
avg_trust = sum(chain.trust_scores.values()) / len(chain.trust_scores) if chain.trust_scores else 0
c1.metric("Sellers on network", len(chain.trust_scores))
c2.metric("Avg. trust score", f"{avg_trust:.1f} / 100")
c3.metric("Ledger blocks mined", len(chain.chain) - 1)
c4.metric("Fraud model accuracy", f"{fraud_metrics['accuracy']*100:.1f}%")

if st.button("Simulate 15 minutes of network activity", type="primary"):
    simulate_activity(25)
    st.rerun()

# ---------------------------------------------------
# ARCHITECTURE
# ---------------------------------------------------
st.markdown('<div class="section-title">Architecture</div>', unsafe_allow_html=True)
a1, a2 = st.columns(2)
with a1:
    st.markdown(
        """
        <div class="insight-card"><b>1. Trust layer (blockchain)</b><br/>
        Every delivery, dispute, and fraud flag is written as a hash-linked
        ledger event. Seller trust scores are derived deterministically from
        that event history — tamper-evident and auditable.</div>
        <div class="insight-card"><b>2. Fraud layer (AI)</b><br/>
        A Random Forest classifier scores each transaction using seller
        trust, buyer behavior, and transaction features to flag likely fraud
        before funds move.</div>
        """,
        unsafe_allow_html=True,
    )
with a2:
    st.markdown(
        """
        <div class="insight-card"><b>3. Discovery layer (AI)</b><br/>
        A content-based recommender blends category match, price fit, and
        on-chain seller trust to rank product/service matches for each buyer.</div>
        <div class="insight-card"><b>4. Settlement layer (smart contracts)</b><br/>
        Orders are held in escrow; disputes are resolved automatically from
        each party's trust score, with an arbitrator override path.</div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------
# KPI STATUS
# ---------------------------------------------------
st.markdown('<div class="section-title">Target KPIs</div>', unsafe_allow_html=True)

kpi_rows = [
    ("Smart contract deployment for trust scoring", True, "TrustScore.sol + EscrowDispute.sol", "Ready"),
    ("AI fraud detection accuracy (target 85%+)", fraud_metrics["accuracy"] >= 0.85, f"{fraud_metrics['accuracy']*100:.1f}% on synthetic test data", None),
    ("Recommendation CTR lift (target 20%+)", ctr["lift_pct"] >= 20, f"{ctr['lift_pct']:.0f}% over random baseline", None),
    ("Blockchain transaction time (target <30s)", True, f"~{max(st.session_state.get('last_batch_ms', 0.1), 0.01):.2f} ms/block (local sim)", "Ready"),
    ("Comprehensive testnet test suite", True, "Hardhat + Chai tests in test/", "Ready"),
]

for label, met, detail, ready_label in kpi_rows:
    cols = st.columns([5, 2, 3])
    cols[0].markdown(f"**{label}**")
    with cols[1]:
        status_pill(ready_label or "Met", met, pending_label="In progress")
    cols[2].caption(detail)

# ---------------------------------------------------
# LIVE ACTIVITY FEED
# ---------------------------------------------------
st.markdown('<div class="section-title">Recent Network Activity</div>', unsafe_allow_html=True)

log = st.session_state.get("activity_log", [])
if not log:
    st.caption("No activity yet — click \"Simulate\" above.")
else:
    rows_html = []
    for entry in reversed(log[-12:]):
        icon, color, label = EVENT_META.get(entry["type"], ("&#8226;", STATUS_GOOD, entry["type"]))
        ts = datetime.fromtimestamp(entry["timestamp"]).strftime("%H:%M:%S")
        rows_html.append(
            f"""<div class="activity-row">
                <div class="badge" style="background:{color}1a;">{icon}</div>
                <div style="flex:1;">
                    <div><b>{entry['seller_id']}</b> — {label}</div>
                    <div class="meta">Block #{entry['block']} · {ts}</div>
                </div>
            </div>"""
        )
    st.markdown(f'<div class="card">{"".join(rows_html)}</div>', unsafe_allow_html=True)
