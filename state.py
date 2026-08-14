"""Session-wide state shared across pages: the blockchain trust ledger, the
cached ML models, and the synthetic ONDC catalog. Centralized here so every
page reads/writes the same underlying objects instead of re-deriving them."""

import time

import numpy as np
import streamlit as st

from blockchain.chain import TrustChain
from ml.data import generate_buyers, generate_catalog, generate_transactions
from ml.fraud_model import train_fraud_model
from ml.recommender import simulate_ctr

SELLERS = [f"SLR-{i:03d}" for i in range(12)]

EVENT_WEIGHTS = {
    "successful_delivery": 0.55,
    "on_time": 0.15,
    "late_delivery": 0.10,
    "dispute_raised": 0.08,
    "dispute_resolved_seller": 0.05,
    "dispute_resolved_buyer": 0.04,
    "fraud_flagged": 0.03,
}


def get_chain() -> TrustChain:
    """Returns the session's trust chain, seeded with history on first access
    so the dashboard reads as an active network rather than an empty demo."""
    if "chain" not in st.session_state:
        st.session_state.chain = TrustChain()
        st.session_state.sellers = SELLERS
        st.session_state.activity_log = []
        _apply_events(st.session_state.chain, 220, seed=7)
    return st.session_state.chain


def simulate_activity(n, seed=None):
    chain = get_chain()
    _apply_events(chain, n, seed=seed)
    return chain


def _apply_events(chain, n, seed=None):
    rng = np.random.default_rng(seed if seed is not None else int(time.time() * 1000) % (2**32))
    types = list(EVENT_WEIGHTS.keys())
    weights = list(EVENT_WEIGHTS.values())

    t0 = time.perf_counter()
    log = st.session_state.setdefault("activity_log", [])
    for _ in range(n):
        seller = str(rng.choice(st.session_state.get("sellers", SELLERS)))
        event_type = str(rng.choice(types, p=weights))
        block = chain.record_event(seller, event_type)
        log.append({"seller_id": seller, "type": event_type, "block": block.index, "timestamp": block.timestamp})
    st.session_state.activity_log = log[-300:]
    st.session_state.last_batch_ms = (time.perf_counter() - t0) * 1000
    return chain


@st.cache_data(show_spinner=False)
def get_transactions(n=6000):
    return generate_transactions(n=n)


@st.cache_resource(show_spinner="Training fraud detection model...")
def get_fraud_model(n=6000):
    df = get_transactions(n)
    return train_fraud_model(df)


@st.cache_data(show_spinner=False)
def get_catalog_and_buyers():
    return generate_catalog(), generate_buyers()


@st.cache_data(show_spinner=False)
def get_ctr_snapshot(top_k=5):
    catalog, buyers = get_catalog_and_buyers()
    return simulate_ctr(catalog, buyers, top_k=top_k)
