-- ============================================================================
-- Blockchain-AI Enhanced ONDC Implementation — PostgreSQL schema
-- ============================================================================
-- This is the source of truth for the relational model. The SQLAlchemy
-- models in backend/app/models/ and the Alembic migration in
-- backend/alembic/versions/ mirror this file exactly — if you change one,
-- change all three (or regenerate the migration with `alembic revision
-- --autogenerate` after editing the SQLAlchemy models).
--
-- Design notes:
--   * UUID primary keys everywhere (gen_random_uuid(), from pgcrypto) so IDs
--     are safe to expose in URLs/APIs and don't leak row counts.
--   * `users` is the identity table for all three roles (buyer/seller/admin).
--     `buyers` and `sellers` are 1:1 extension tables holding role-specific
--     fields, rather than one wide nullable-everything table.
--   * `blockchain_hashes` is an append-only audit trail linking any
--     off-chain row (an order, a trust score update, a dispute resolution)
--     to the on-chain transaction that recorded it, so every state change
--     that matters is independently verifiable on Etherscan.
--   * `trust_scores` is a time series (one row per computation), not a
--     single mutable column on `sellers`, so the dashboard can chart trust
--     drift over time and audits can see exactly which factors moved the
--     score at each point.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----------------------------------------------------------------------------
-- users — identity + auth for all three roles
-- ----------------------------------------------------------------------------
CREATE TYPE user_role AS ENUM ('buyer', 'seller', 'admin');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    role            user_role NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);

-- ----------------------------------------------------------------------------
-- buyers — 1:1 extension of users where role = 'buyer'
-- ----------------------------------------------------------------------------
CREATE TABLE buyers (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    wallet_address          VARCHAR(42),
    -- True only once ownership was proven by signature over a one-time
    -- server nonce (0005_wallet_verified.py) — PATCH /auth/me can no
    -- longer set wallet_address as unverified free text.
    wallet_verified         BOOLEAN NOT NULL DEFAULT FALSE,
    price_sensitivity       NUMERIC(3, 2) NOT NULL DEFAULT 0.5 CHECK (price_sensitivity BETWEEN 0 AND 1),
    preferred_categories    TEXT[] NOT NULL DEFAULT '{}',
    -- One of app.core.geo.CITY_NAMES, or NULL if unset. Added by
    -- 0004_add_location_fields.py — feeds the recommendation service's
    -- buyer-seller proximity signal.
    city                    VARCHAR(100),
    account_age_days        INTEGER NOT NULL DEFAULT 0,
    is_flagged_fraud        BOOLEAN NOT NULL DEFAULT FALSE,
    -- Added by 0003_add_buyer_onchain_registered.py — mirrors
    -- sellers.is_onchain_registered below; TrustScore.sol's register() is
    -- generic over any participant address, not seller-only.
    is_onchain_registered   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_buyers_wallet ON buyers (wallet_address);

-- ----------------------------------------------------------------------------
-- sellers — 1:1 extension of users where role = 'seller'
-- ----------------------------------------------------------------------------
CREATE TABLE sellers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    business_name       VARCHAR(255) NOT NULL,
    wallet_address      VARCHAR(42),
    -- True only once ownership was proven by signature over a one-time
    -- server nonce (0005_wallet_verified.py).
    wallet_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    gstin               VARCHAR(15),
    seller_age_days     INTEGER NOT NULL DEFAULT 0,
    -- One of app.core.geo.CITY_NAMES, or NULL if unset (0004_add_location_fields.py).
    city                VARCHAR(100),
    -- How far this seller ships, in km; shapes the proximity score's decay.
    delivery_radius_km  INTEGER NOT NULL DEFAULT 50,
    current_trust_score NUMERIC(5, 2) NOT NULL DEFAULT 50.00,
    is_onchain_registered BOOLEAN NOT NULL DEFAULT FALSE,
    is_flagged_fraud    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sellers_wallet ON sellers (wallet_address);
CREATE INDEX idx_sellers_trust_score ON sellers (current_trust_score);

-- ----------------------------------------------------------------------------
-- products — seller catalog
-- ----------------------------------------------------------------------------
CREATE TABLE products (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id       UUID NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    category        VARCHAR(100) NOT NULL,
    tags            TEXT[] NOT NULL DEFAULT '{}',
    price           NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    stock_quantity  INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    image_url       TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_products_seller ON products (seller_id);
CREATE INDEX idx_products_category ON products (category);
CREATE INDEX idx_products_active ON products (is_active);

-- ----------------------------------------------------------------------------
-- orders
-- ----------------------------------------------------------------------------
CREATE TYPE order_status AS ENUM (
    'created', 'confirmed', 'shipped', 'delivered', 'disputed', 'resolved', 'cancelled'
);

CREATE TABLE orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id            UUID NOT NULL REFERENCES buyers(id),
    seller_id           UUID NOT NULL REFERENCES sellers(id),
    product_id          UUID NOT NULL REFERENCES products(id),
    quantity            INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    amount              NUMERIC(10, 2) NOT NULL CHECK (amount >= 0),
    status              order_status NOT NULL DEFAULT 'created',
    onchain_order_id    BIGINT,
    escrow_tx_hash      VARCHAR(66),
    delivered_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_orders_buyer ON orders (buyer_id);
CREATE INDEX idx_orders_seller ON orders (seller_id);
CREATE INDEX idx_orders_status ON orders (status);

-- ----------------------------------------------------------------------------
-- transactions — payment attempts tied to an order (1 order can retry)
-- ----------------------------------------------------------------------------
CREATE TYPE payment_method AS ENUM ('upi', 'card', 'cod', 'wallet');
CREATE TYPE transaction_status AS ENUM ('pending', 'success', 'failed', 'refunded');

CREATE TABLE transactions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id                UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    buyer_id                UUID NOT NULL REFERENCES buyers(id),
    seller_id               UUID NOT NULL REFERENCES sellers(id),
    amount                  NUMERIC(10, 2) NOT NULL,
    payment_method          payment_method NOT NULL,
    status                  transaction_status NOT NULL DEFAULT 'pending',
    is_fraud_flagged        BOOLEAN NOT NULL DEFAULT FALSE,
    fraud_probability       NUMERIC(5, 4),
    onchain_tx_hash         VARCHAR(66),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transactions_order ON transactions (order_id);
CREATE INDEX idx_transactions_buyer ON transactions (buyer_id);
CREATE INDEX idx_transactions_seller ON transactions (seller_id);
CREATE INDEX idx_transactions_fraud_flagged ON transactions (is_fraud_flagged);

-- ----------------------------------------------------------------------------
-- blockchain_hashes — append-only audit trail: off-chain row <-> on-chain tx
-- ----------------------------------------------------------------------------
CREATE TABLE blockchain_hashes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     VARCHAR(50) NOT NULL,   -- 'order', 'trust_score', 'dispute', 'registration'
    entity_id       UUID NOT NULL,
    tx_hash         VARCHAR(66) NOT NULL,
    block_number    BIGINT,
    network         VARCHAR(50) NOT NULL DEFAULT 'sepolia',
    event_type      VARCHAR(100) NOT NULL,
    payload_hash    VARCHAR(66),
    confirmed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_blockchain_hashes_entity ON blockchain_hashes (entity_type, entity_id);
CREATE INDEX idx_blockchain_hashes_tx ON blockchain_hashes (tx_hash);

-- ----------------------------------------------------------------------------
-- trust_scores — time series of computed seller trust scores
-- ----------------------------------------------------------------------------
CREATE TABLE trust_scores (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id                   UUID NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,
    score                       NUMERIC(5, 2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    transaction_success_rate    NUMERIC(5, 4),
    delivery_success_rate       NUMERIC(5, 4),
    avg_customer_rating         NUMERIC(3, 2),
    complaint_ratio             NUMERIC(5, 4),
    dispute_count                INTEGER NOT NULL DEFAULT 0,
    fraud_probability           NUMERIC(5, 4),
    refund_ratio                NUMERIC(5, 4),
    late_delivery_ratio         NUMERIC(5, 4),
    order_completion_rate       NUMERIC(5, 4),
    onchain_tx_hash              VARCHAR(66),
    computed_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_trust_scores_seller ON trust_scores (seller_id);
CREATE INDEX idx_trust_scores_computed_at ON trust_scores (computed_at);

-- ----------------------------------------------------------------------------
-- disputes
-- ----------------------------------------------------------------------------
CREATE TYPE dispute_status AS ENUM ('open', 'under_review', 'auto_resolved', 'arbitrated', 'closed');
CREATE TYPE dispute_reason AS ENUM (
    'item_not_received', 'item_not_as_described', 'buyer_unresponsive', 'damaged_in_transit', 'other'
);

CREATE TABLE disputes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    raised_by_user_id   UUID NOT NULL REFERENCES users(id),
    reason              dispute_reason NOT NULL,
    description         TEXT,
    evidence_buyer_score NUMERIC(3, 2) DEFAULT 0,
    evidence_seller_score NUMERIC(3, 2) DEFAULT 0,
    status              dispute_status NOT NULL DEFAULT 'open',
    resolution_outcome  VARCHAR(100),
    seller_share_bps    INTEGER CHECK (seller_share_bps BETWEEN 0 AND 10000),
    resolved_by         VARCHAR(20),   -- 'rule_auto' | 'arbitrator' | 'auto_return'
    onchain_tx_hash     VARCHAR(66),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ
);

CREATE INDEX idx_disputes_order ON disputes (order_id);
CREATE INDEX idx_disputes_status ON disputes (status);

-- ----------------------------------------------------------------------------
-- recommendations — logged impressions for CTR evaluation
-- ----------------------------------------------------------------------------
CREATE TABLE recommendations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id        UUID NOT NULL REFERENCES buyers(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    algorithm       VARCHAR(50) NOT NULL,   -- 'content_based' | 'collaborative' | 'hybrid'
    score           NUMERIC(6, 5) NOT NULL,
    rank            INTEGER NOT NULL,
    was_clicked     BOOLEAN NOT NULL DEFAULT FALSE,
    was_purchased   BOOLEAN NOT NULL DEFAULT FALSE,
    shown_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    clicked_at      TIMESTAMPTZ
);

CREATE INDEX idx_recommendations_buyer ON recommendations (buyer_id);
CREATE INDEX idx_recommendations_product ON recommendations (product_id);

-- ----------------------------------------------------------------------------
-- fraud_logs — every scored transaction, not just flagged ones (audit trail)
-- ----------------------------------------------------------------------------
CREATE TABLE fraud_logs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id          UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    model_name              VARCHAR(50) NOT NULL,   -- 'random_forest' | 'xgboost' | 'lightgbm' | 'ensemble'
    model_version           VARCHAR(20) NOT NULL,
    fraud_probability       NUMERIC(5, 4) NOT NULL,
    is_flagged              BOOLEAN NOT NULL,
    risk_factors            JSONB,
    reviewed_by_admin_id    UUID REFERENCES users(id),
    admin_decision          VARCHAR(20),   -- 'confirmed_fraud' | 'false_positive' | null (pending)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fraud_logs_transaction ON fraud_logs (transaction_id);
CREATE INDEX idx_fraud_logs_flagged ON fraud_logs (is_flagged);

-- ----------------------------------------------------------------------------
-- reviews
-- ----------------------------------------------------------------------------
CREATE TABLE reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
    buyer_id        UUID NOT NULL REFERENCES buyers(id),
    seller_id       UUID NOT NULL REFERENCES sellers(id),
    rating          SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_reviews_seller ON reviews (seller_id);

-- ----------------------------------------------------------------------------
-- wishlists — not one of the original 12 tables; added for the buyer
-- wishlist feature (backend/alembic/versions/0002_add_wishlist.py)
-- ----------------------------------------------------------------------------
CREATE TABLE wishlists (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id        UUID NOT NULL REFERENCES buyers(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (buyer_id, product_id)
);

CREATE INDEX idx_wishlists_buyer ON wishlists (buyer_id);

-- ============================================================================
-- End of schema
-- ============================================================================
