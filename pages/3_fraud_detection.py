import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from state import get_fraud_model, get_transactions
from theme import BLUE, GRIDLINE, ORANGE, SEQ_BLUE, page_header, status_pill

page_header(
    "Fraud Layer",
    "AI Fraud Detection",
    "Random Forest classifier trained on synthetic ONDC transactions — seller "
    "trust score, dispute history, velocity, delivery time, payment method, and more.",
)

n_txns = st.slider("Synthetic transactions to generate", 2000, 20000, 6000, step=1000)
df_txns = get_transactions(n_txns)
model, metrics = get_fraud_model(n_txns)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Accuracy", f"{metrics['accuracy']*100:.1f}%", help="Target: 85%+")
m2.metric("Precision", f"{metrics['precision']*100:.1f}%")
m3.metric("Recall", f"{metrics['recall']*100:.1f}%")
m4.metric("F1 score", f"{metrics['f1']*100:.1f}%")
m5.metric("ROC-AUC", f"{metrics['roc_auc']:.3f}")

status_pill(
    f"KPI met — {metrics['accuracy']*100:.1f}% ≥ 85% target",
    metrics["accuracy"] >= 0.85,
    pending_label=f"{metrics['accuracy']*100:.1f}% — below 85% target",
)

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.markdown("#### Confusion matrix")
        cm = metrics["confusion_matrix"]
        labels = ["Legit", "Fraud"]
        fig = go.Figure(
            go.Heatmap(
                z=cm,
                x=labels,
                y=labels,
                colorscale=[[i / (len(SEQ_BLUE) - 1), c] for i, c in enumerate(SEQ_BLUE)],
                text=cm,
                texttemplate="%{text}",
                textfont=dict(size=16, color="#0b0b0b"),
                hovertemplate="Actual: %{y}<br>Predicted: %{x}<br>Count: %{z}<extra></extra>",
                showscale=False,
            )
        )
        fig.update_layout(height=320, yaxis_title="Actual", xaxis_title="Predicted", yaxis_autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

with c2:
    with st.container(border=True):
        st.markdown("#### ROC curve")
        fpr, tpr, _ = metrics["fpr_tpr"]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=fpr, y=tpr, mode="lines", line=dict(color=BLUE, width=2.5),
                name=f"Model (AUC = {metrics['roc_auc']:.3f})",
                hovertemplate="FPR: %{x:.2f}<br>TPR: %{y:.2f}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[0, 1], y=[0, 1], mode="lines", line=dict(color=GRIDLINE, width=1.5, dash="dash"),
                name="Random guess", hoverinfo="skip",
            )
        )
        fig.update_layout(height=320, xaxis_title="False positive rate", yaxis_title="True positive rate")
        st.plotly_chart(fig, use_container_width=True)

with st.container(border=True):
    st.markdown("#### Top fraud signals (feature importance)")
    top_features = metrics["feature_importances"][:10]
    fi_df = pd.DataFrame(top_features, columns=["feature", "importance"]).sort_values("importance")
    fig = go.Figure(
        go.Bar(
            x=fi_df["importance"], y=fi_df["feature"], orientation="h",
            marker_color=ORANGE, marker_line_width=0,
            hovertemplate="%{y}: %{x:.3f}<extra></extra>",
        )
    )
    fig.update_layout(height=360, xaxis_title="Relative importance")
    st.plotly_chart(fig, use_container_width=True)

with st.expander("Sample of the synthetic training data"):
    st.dataframe(df_txns.head(50), use_container_width=True)
