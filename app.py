import streamlit as st

from theme import brand_header, inject_css, register_plotly_theme

st.set_page_config(
    page_title="TrustMesh — Blockchain-AI Trust Layer for ONDC",
    page_icon="⚛️",
    layout="wide",
)

register_plotly_theme()
inject_css()
brand_header()

pages = [
    st.Page("pages/1_home.py", title="Overview", icon=":material/home:", default=True),
    st.Page("pages/2_trust_ledger.py", title="Trust Ledger", icon=":material/link:"),
    st.Page("pages/3_fraud_detection.py", title="Fraud Detection", icon=":material/security:"),
    st.Page("pages/4_recommendations.py", title="Recommendations", icon=":material/recommend:"),
    st.Page("pages/5_dispute_resolution.py", title="Dispute Resolution", icon=":material/balance:"),
    st.Page("pages/6_smart_contracts.py", title="Smart Contracts", icon=":material/description:"),
]

nav = st.navigation(pages, position="sidebar")

st.sidebar.markdown(
    """
    <div style="font-size:11.5px; color:#9fb0c9; line-height:1.5; margin-top: 10px;">
    Synthetic ONDC data · Solidity contracts included · see the Overview tab
    for what's live vs. simulated.
    </div>
    """,
    unsafe_allow_html=True,
)

nav.run()
