import plotly.graph_objects as go
import streamlit as st

from ml.recommender import recommend_for_buyer, simulate_ctr
from state import get_catalog_and_buyers
from theme import BLUE, INK_MUTED, page_header, status_pill

page_header(
    "Discovery Layer",
    "Intelligent Product/Service Matching",
    "Content-based recommender blending category match, price sensitivity, "
    "and on-chain seller trust score, benchmarked against random placement.",
)

catalog, buyers = get_catalog_and_buyers()

buyer_ids = [b["buyer_id"] for b in buyers]
selected_id = st.selectbox("Preview recommendations for buyer", buyer_ids)
selected_buyer = next(b for b in buyers if b["buyer_id"] == selected_id)
st.caption(
    f"Preferred categories: {', '.join(selected_buyer['preferred_categories'])} "
    f"· Price sensitivity: {selected_buyer['price_sensitivity']}"
)

top_k = st.slider("Recommendations to show", 3, 10, 5)
recs = recommend_for_buyer(catalog, selected_buyer, top_k=top_k)
st.dataframe(
    recs[["product_id", "category", "price", "seller_id", "seller_trust_score", "match_score"]],
    use_container_width=True,
)

st.markdown('<div class="section-title">CTR backtest vs. random baseline</div>', unsafe_allow_html=True)
if st.button("Run CTR simulation", type="primary"):
    with st.spinner("Simulating impressions across all buyers..."):
        st.session_state.ctr_result = simulate_ctr(catalog, buyers, top_k=top_k)

if "ctr_result" in st.session_state:
    ctr = st.session_state.ctr_result
    c1, c2, c3 = st.columns(3)
    c1.metric("Random baseline CTR", f"{ctr['random_ctr']*100:.1f}%")
    c2.metric("Recommender CTR", f"{ctr['reco_ctr']*100:.1f}%")
    c3.metric("Lift", f"{ctr['lift_pct']:.0f}%", help="Target: 20%+ improvement")

    status_pill(
        f"KPI met — {ctr['lift_pct']:.0f}% ≥ 20% target",
        ctr["lift_pct"] >= 20,
        pending_label=f"{ctr['lift_pct']:.0f}% — below 20% target",
    )

    with st.container(border=True):
        fig = go.Figure(
            go.Bar(
                x=["Random baseline", "Recommender"],
                y=[ctr["random_ctr"] * 100, ctr["reco_ctr"] * 100],
                marker_color=[INK_MUTED, BLUE],
                marker_line_width=0,
                text=[f"{ctr['random_ctr']*100:.1f}%", f"{ctr['reco_ctr']*100:.1f}%"],
                textposition="outside",
                hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
            )
        )
        fig.update_layout(height=320, yaxis_title="CTR (%)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

st.caption(
    "CTR is a simulated backtest: clicks are drawn from a synthetic "
    "probability model driven by category match and seller trust, not "
    "real user behavior."
)
