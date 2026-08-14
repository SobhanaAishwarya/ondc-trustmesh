import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from state import get_chain, simulate_activity
from theme import STATUS_CRITICAL, STATUS_GOOD, STATUS_WARNING, page_header

page_header(
    "Trust Layer",
    "Blockchain Trust Ledger",
    "Each event is mined into a hash-linked block. Tampering with any past "
    "event breaks the chain from that point forward — try it below.",
)

chain = get_chain()

col1, col2, col3 = st.columns(3)
with col1:
    n_events = st.slider("Events to simulate", 5, 100, 20)
    if st.button("Add simulated transactions", type="primary"):
        simulate_activity(n_events)
        st.session_state.validity = None
with col2:
    if st.button("Verify chain integrity"):
        st.session_state.validity = chain.is_valid()
with col3:
    if st.button("Tamper with a block (demo)"):
        if len(chain.chain) > 2:
            target = chain.chain[2]
            if target.events:
                target.events[0]["type"] = "fraud_flagged"
            st.session_state.validity = None

m1, m2, m3 = st.columns(3)
m1.metric("Blocks mined", len(chain.chain) - 1)
m2.metric("Sellers tracked", len(chain.trust_scores))
avg_ms = st.session_state.get("last_batch_ms", 0) / max(n_events, 1)
m3.metric("Avg. block append time", f"{avg_ms:.3f} ms", help="Simulated locally — comfortably under the 30s target")

if st.session_state.get("validity") is not None:
    valid, message = st.session_state.validity
    (st.success if valid else st.error)(message)

if chain.trust_scores:
    scores_df = pd.DataFrame(
        {"seller_id": list(chain.trust_scores.keys()), "trust_score": list(chain.trust_scores.values())}
    ).sort_values("trust_score", ascending=False)

    def tier_color(score):
        if score >= 70:
            return STATUS_GOOD
        if score >= 40:
            return STATUS_WARNING
        return STATUS_CRITICAL

    colors = [tier_color(s) for s in scores_df["trust_score"]]

    with st.container(border=True):
        st.markdown("#### Seller trust scores")
        fig = go.Figure(
            go.Bar(
                x=scores_df["seller_id"],
                y=scores_df["trust_score"],
                marker_color=colors,
                marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>Trust score: %{y:.1f}<extra></extra>",
            )
        )
        fig.update_layout(height=340, yaxis_range=[0, 100], yaxis_title="Trust score (0-100)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("🟢 trusted (≥70)  ·  🟡 needs monitoring (40-69)  ·  🔴 high risk (<40)")

with st.expander("Raw ledger (hash-linked blocks)"):
    records = chain.to_records()
    if len(records) > 1:
        st.dataframe(pd.DataFrame(records[1:]), use_container_width=True, height=320)
    else:
        st.caption('No events yet — click "Add simulated transactions".')
