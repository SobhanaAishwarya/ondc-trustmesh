"""Shared visual identity for the TrustMesh dashboard: color tokens (from a
validated, colorblind-safe palette), a Plotly template, and small reusable
UI components (brand header, stat tiles, status pills)."""

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------
# COLOR TOKENS
# (validated categorical + status palette — fixed hue order, never cycled)
# ---------------------------------------------------

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
MAGENTA = "#e87ba4"
GREEN = "#008300"
VIOLET = "#4a3aa7"
RED = "#e34948"
CATEGORICAL = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]

STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_SERIOUS = "#ec835a"
STATUS_CRITICAL = "#d03b3b"

SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#ffffff"
PAGE_PLANE = "#f5f7fa"
BRAND_NAVY = "#0f1b2d"


def register_plotly_theme():
    pio.templates["trustmesh"] = go.layout.Template(
        layout=go.Layout(
            font=dict(family="Segoe UI, system-ui, sans-serif", color=INK_PRIMARY, size=13),
            paper_bgcolor=SURFACE,
            plot_bgcolor=SURFACE,
            colorway=CATEGORICAL,
            xaxis=dict(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, linecolor=BASELINE, showline=True, ticks=""),
            yaxis=dict(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, linecolor=BASELINE, showline=True, ticks=""),
            legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.12, x=0),
            margin=dict(l=10, r=10, t=36, b=10),
            hoverlabel=dict(bgcolor=BRAND_NAVY, font_color="#ffffff", font_size=12),
        )
    )
    pio.templates.default = "trustmesh"


def inject_css():
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {PAGE_PLANE}; font-family: 'Segoe UI', system-ui, sans-serif; }}
        .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1240px; }}
        h1, h2, h3 {{ color: {BRAND_NAVY}; font-weight: 700; }}

        section[data-testid="stSidebar"] {{ background: {BRAND_NAVY}; }}
        section[data-testid="stSidebar"] * {{ color: #e7ebf3 !important; }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {{
            border-radius: 8px; margin: 1px 0;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
            background: rgba(255,255,255,0.08);
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background: rgba(42,120,214,0.35);
        }}

        .brand-mark {{
            display: flex; align-items: center; gap: 10px; margin-bottom: 4px;
        }}
        .brand-mark .logo {{
            width: 30px; height: 30px; border-radius: 8px;
            background: linear-gradient(135deg, {BLUE}, {VIOLET});
            display: flex; align-items: center; justify-content: center;
            font-size: 15px; flex-shrink: 0;
        }}
        .brand-mark .name {{ font-size: 19px; font-weight: 800; color: #f5f7fb; letter-spacing: -0.01em; }}
        .brand-mark .tag {{ font-size: 11px; color: #9fb0c9; margin-top: -2px; }}

        .app-header {{ margin-bottom: 6px; }}
        .app-header .eyebrow {{
            font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
            text-transform: uppercase; color: {BLUE}; margin-bottom: 4px;
        }}
        .app-header h1 {{ font-size: 27px; margin: 0; }}
        .app-header p {{ font-size: 14px; color: {INK_SECONDARY}; margin: 4px 0 0; max-width: 720px; }}

        [data-testid="stMetric"] {{
            background: {SURFACE}; border: 1px solid {GRIDLINE}; border-radius: 14px;
            padding: 16px 18px; box-shadow: 0 2px 10px rgba(15,27,45,0.05);
        }}
        [data-testid="stMetricLabel"] {{ color: {INK_SECONDARY}; font-weight: 600; }}
        [data-testid="stMetricValue"] {{ color: {BRAND_NAVY}; font-weight: 800; }}

        .section-title {{
            font-size: 12.5px; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.06em; color: {INK_SECONDARY}; margin: 30px 0 14px;
        }}

        .card {{
            background: {SURFACE}; border: 1px solid {GRIDLINE}; border-radius: 14px;
            padding: 18px 20px; box-shadow: 0 2px 10px rgba(15,27,45,0.05);
            margin-bottom: 16px;
        }}
        .card h4 {{ margin: 0 0 8px; font-size: 13px; font-weight: 700; color: {BRAND_NAVY}; }}

        .insight-card {{
            background: {SURFACE}; border: 1px solid {GRIDLINE}; border-left: 4px solid {BLUE};
            border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; font-size: 13.5px; color: {INK_SECONDARY};
        }}
        .note-card {{
            background: #fff8ec; border: 1px solid #f0ddb0; border-left: 4px solid {YELLOW};
            border-radius: 10px; padding: 14px 16px; margin: 14px 0; font-size: 13px; color: #6b5216;
        }}

        .status-pill {{
            display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px;
            border-radius: 999px; font-size: 12px; font-weight: 700;
        }}

        .activity-row {{
            display: flex; align-items: center; gap: 12px; padding: 9px 4px;
            border-bottom: 1px solid {GRIDLINE}; font-size: 13px;
        }}
        .activity-row .badge {{
            width: 26px; height: 26px; border-radius: 7px; display: flex; align-items: center;
            justify-content: center; font-size: 13px; flex-shrink: 0;
        }}
        .activity-row .meta {{ color: {INK_MUTED}; font-size: 11.5px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def brand_header():
    st.sidebar.markdown(
        """
        <div class="brand-mark">
            <div class="logo">&#9775;</div>
            <div>
                <div class="name">TrustMesh</div>
                <div class="tag">Blockchain-AI Trust Layer for ONDC</div>
            </div>
        </div>
        <hr style="border-color: rgba(255,255,255,0.12); margin: 10px 0 6px;">
        """,
        unsafe_allow_html=True,
    )


def page_header(eyebrow, title, subtitle):
    st.markdown(
        f"""
        <div class="app-header">
            <div class="eyebrow">{eyebrow}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_pill(label, ok, pending_label=None):
    if ok:
        color, icon, text = STATUS_GOOD, "&#10003;", label
    else:
        color, icon, text = INK_MUTED, "&#8230;", pending_label or label
    st.markdown(
        f'<span class="status-pill" style="background:{color}1a; color:{color}; '
        f'border:1px solid {color}55;">{icon} {text}</span>',
        unsafe_allow_html=True,
    )


EVENT_META = {
    "successful_delivery": ("&#9989;", STATUS_GOOD, "Delivered successfully"),
    "on_time": ("&#128337;", BLUE, "On-time delivery"),
    "late_delivery": ("&#9203;", STATUS_WARNING, "Late delivery"),
    "dispute_raised": ("&#9888;", STATUS_SERIOUS, "Dispute raised"),
    "dispute_resolved_seller": ("&#9878;", BLUE, "Dispute resolved — seller"),
    "dispute_resolved_buyer": ("&#9878;", VIOLET, "Dispute resolved — buyer"),
    "fraud_flagged": ("&#128680;", STATUS_CRITICAL, "Fraud flagged"),
}
