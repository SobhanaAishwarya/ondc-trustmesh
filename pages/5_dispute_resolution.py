import plotly.graph_objects as go
import streamlit as st

from ml.dispute_resolution import resolve_dispute
from theme import BLUE, VIOLET, page_header

page_header(
    "Settlement Layer",
    "Automated Dispute Resolution",
    "The off-chain decision logic mirrored by EscrowDispute.sol's autoResolve() "
    "— funds are split based on each party's trust score and submitted evidence.",
)

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Seller**")
    seller_trust = st.slider("Seller trust score", 0, 100, 72)
    evidence_seller = st.slider("Seller evidence strength", 0.0, 1.0, 0.6)
    delivery_confirmed = st.checkbox("Delivery confirmed on-chain", value=False)
with c2:
    st.markdown("**Buyer**")
    buyer_trust = st.slider("Buyer trust score", 0, 100, 55)
    evidence_buyer = st.slider("Buyer evidence strength", 0.0, 1.0, 0.5)
    dispute_reason = st.selectbox(
        "Dispute reason",
        ["item_not_received", "item_not_as_described", "damaged_in_transit", "buyer_unresponsive"],
    )

result = resolve_dispute(
    seller_trust, buyer_trust, evidence_seller, evidence_buyer, delivery_confirmed, dispute_reason
)

with st.container(border=True):
    st.markdown("#### Resolution")
    st.subheader(result["outcome"])

    c1, c2 = st.columns([2, 1])
    with c1:
        seller_pct = result["seller_share"] * 100
        buyer_pct = result["buyer_share"] * 100
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=[seller_pct], y=["Escrow split"], orientation="h", name="Seller",
                marker_color=BLUE, text=[f"Seller {seller_pct:.1f}%"], textposition="inside",
                hovertemplate="Seller: %{x:.1f}%<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                x=[buyer_pct], y=["Escrow split"], orientation="h", name="Buyer",
                marker_color=VIOLET, text=[f"Buyer {buyer_pct:.1f}%"], textposition="inside",
                hovertemplate="Buyer: %{x:.1f}%<extra></extra>",
            )
        )
        fig.update_layout(
            barmode="stack", height=140, showlegend=False,
            xaxis_visible=False, yaxis_visible=False, xaxis_range=[0, 100],
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.metric("Seller share", f"{seller_pct:.1f}%")
        st.metric("Buyer share", f"{buyer_pct:.1f}%")

st.caption(
    "This mirrors EscrowDispute.sol's on-chain logic: seller and buyer "
    "\"case strength\" is a blend of trust score and evidence, adjusted for "
    "confirmed delivery and dispute reason, then normalized into an escrow split."
)
