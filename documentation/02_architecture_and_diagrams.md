# Architecture and Diagrams

All diagrams are Mermaid — they render natively on GitHub and in most
modern markdown viewers. Every component named here corresponds to a real
file in the repository; none of this is aspirational.

## System architecture

```mermaid
graph TB
    UI["React SPA<br/>(Vite + Tailwind, frontend/)"]
    NGINX["nginx<br/>static files + /api proxy<br/>(frontend/nginx.conf)"]

    subgraph Backend["FastAPI Backend (backend/app/)"]
        AUTH["Auth<br/>JWT access + refresh"]
        CATALOG["Products / Orders"]
        FRAUD["Fraud Service<br/>RandomForest"]
        TRUST["Trust Service"]
        REC["Recommendation Service"]
        DISP["Dispute Service"]
        ADMIN["Admin Module"]
        BRIDGE["Blockchain Bridge<br/>(Web3.py)"]
    end

    PG[("PostgreSQL")]
    REDIS[("Redis<br/>provisioned, not yet used")]
    MODEL[["fraud_model.joblib"]]

    subgraph Chain["Ethereum — Sepolia or local Hardhat"]
        TS["TrustScore.sol"]
        ESC["EscrowDispute.sol"]
    end

    UI --> NGINX --> AUTH
    NGINX --> CATALOG
    NGINX --> FRAUD
    NGINX --> TRUST
    NGINX --> REC
    NGINX --> DISP
    NGINX --> ADMIN

    AUTH --> PG
    CATALOG --> PG
    FRAUD --> PG
    FRAUD --> MODEL
    TRUST --> PG
    REC --> PG
    DISP --> PG
    ADMIN --> PG
    Backend -.->|provisioned, unused| REDIS

    CATALOG -->|order delivered| TRUST
    CATALOG -->|order created| FRAUD
    TRUST -->|record_trust_event| BRIDGE
    DISP -->|raise / resolve| BRIDGE
    FRAUD -->|fraud flagged| BRIDGE
    BRIDGE --> TS
    BRIDGE --> ESC
```

The blockchain bridge is best-effort by design: every arrow into `BRIDGE`
is caught-and-logged if the chain is disabled or unreachable, never a hard
dependency of the request that triggered it (see `backend/README.md`'s
design-decisions section).

## Data Flow Diagram (Level 1)

```mermaid
flowchart LR
    Buyer((Buyer))
    Seller((Seller))
    Admin((Admin))

    P1(["1.0<br/>Authenticate"])
    P2(["2.0<br/>Manage Catalog<br/>&amp; Orders"])
    P3(["3.0<br/>Detect Fraud"])
    P4(["4.0<br/>Compute Trust<br/>Score"])
    P5(["5.0<br/>Recommend<br/>Products"])
    P6(["6.0<br/>Resolve<br/>Disputes"])
    P7(["7.0<br/>Admin<br/>Oversight"])

    D1[("Users /<br/>Buyers / Sellers")]
    D2[("Products /<br/>Orders / Transactions")]
    D3[("Fraud Logs")]
    D4[("Trust Scores")]
    D5[("Recommendations")]
    D6[("Disputes")]
    D7[("Blockchain<br/>Hashes")]

    Buyer --> P1
    Seller --> P1
    Admin --> P1
    P1 <--> D1

    Buyer --> P2
    Seller --> P2
    P2 <--> D2
    P2 --> P3
    P2 --> P5

    P3 <--> D3
    P3 -.->|flag| P4

    P2 -->|order delivered| P4
    P4 <--> D4
    P4 -.->|event| D7

    P5 <--> D5
    P5 <--> D1
    P5 <--> D2

    Buyer --> P6
    Seller --> P6
    P6 <--> D6
    P6 -.->|event| D7

    Admin --> P7
    P7 <--> D3
    P7 <--> D6
    P7 <--> D7
    P7 <--> D1
```

## Entity-Relationship Diagram

13 tables — the original 12 from `database/schema.sql` plus `wishlists`
(added for the buyer wishlist feature; see
[03_database_schema.md](03_database_schema.md)).

```mermaid
erDiagram
    USERS ||--o| BUYERS : "has profile"
    USERS ||--o| SELLERS : "has profile"
    SELLERS ||--o{ PRODUCTS : lists
    BUYERS ||--o{ ORDERS : places
    SELLERS ||--o{ ORDERS : fulfills
    PRODUCTS ||--o{ ORDERS : "ordered as"
    ORDERS ||--o{ TRANSACTIONS : "paid via"
    ORDERS ||--o| REVIEWS : "reviewed once"
    ORDERS ||--o{ DISPUTES : "disputed on"
    USERS ||--o{ DISPUTES : raises
    SELLERS ||--o{ TRUST_SCORES : "scored over time"
    TRANSACTIONS ||--o{ FRAUD_LOGS : "scored as"
    BUYERS ||--o{ RECOMMENDATIONS : "shown to"
    PRODUCTS ||--o{ RECOMMENDATIONS : recommended
    BUYERS ||--o{ WISHLISTS : saves
    PRODUCTS ||--o{ WISHLISTS : "saved as"
    BUYERS ||--o{ REVIEWS : writes
    SELLERS ||--o{ REVIEWS : "reviewed as"

    USERS {
        uuid id PK
        string email UK
        string password_hash
        enum role
        bool is_active
    }
    BUYERS {
        uuid id PK
        uuid user_id FK
        string wallet_address
        text_array preferred_categories
        string city
    }
    SELLERS {
        uuid id PK
        uuid user_id FK
        string business_name
        string city
        int delivery_radius_km
        numeric current_trust_score
        bool is_onchain_registered
    }
    PRODUCTS {
        uuid id PK
        uuid seller_id FK
        string category
        numeric price
        int stock_quantity
    }
    ORDERS {
        uuid id PK
        uuid buyer_id FK
        uuid seller_id FK
        uuid product_id FK
        enum status
        numeric amount
    }
    TRANSACTIONS {
        uuid id PK
        uuid order_id FK
        enum payment_method
        bool is_fraud_flagged
        numeric fraud_probability
    }
    FRAUD_LOGS {
        uuid id PK
        uuid transaction_id FK
        numeric fraud_probability
        jsonb risk_factors
    }
    TRUST_SCORES {
        uuid id PK
        uuid seller_id FK
        numeric score
        int dispute_count
    }
    DISPUTES {
        uuid id PK
        uuid order_id FK
        uuid raised_by_user_id FK
        enum status
        int seller_share_bps
    }
    RECOMMENDATIONS {
        uuid id PK
        uuid buyer_id FK
        uuid product_id FK
        string algorithm
        bool was_clicked
    }
    REVIEWS {
        uuid id PK
        uuid order_id FK
        smallint rating
    }
    WISHLISTS {
        uuid id PK
        uuid buyer_id FK
        uuid product_id FK
    }
    BLOCKCHAIN_HASHES {
        uuid id PK
        string entity_type
        uuid entity_id
        string tx_hash
        string event_type
    }
```

`blockchain_hashes` references other rows by `(entity_type, entity_id)`
rather than a typed foreign key — deliberate, since it's a single
append-only audit trail for events on several different entity types
(sellers today; orders/disputes as the blockchain bridge grows), not
scoped to one table.

## Sequence Diagram — Placing an order (fraud scoring + optional on-chain event)

```mermaid
sequenceDiagram
    actor Buyer
    participant UI as React SPA
    participant API as FastAPI (orders.py)
    participant Fraud as Fraud Service
    participant Model as RandomForest Model
    participant DB as PostgreSQL
    participant Chain as Blockchain Bridge

    Buyer->>UI: Click "Buy now"
    UI->>API: POST /api/v1/orders
    API->>DB: Check product stock
    API->>DB: Create Order + Transaction
    API->>Fraud: score_transaction(transaction, buyer, seller, product)
    Fraud->>DB: Gather live features (velocity, disputes, rating...)
    Fraud->>Model: predict_proba(features)
    Model-->>Fraud: fraud_probability
    Fraud->>DB: Write Transaction.fraud_probability + FraudLog
    alt fraud_probability >= threshold
        Fraud->>Chain: record_trust_event(seller, "fraud_flagged")
        Chain-->>Fraud: tx hash (or no-op if chain disabled)
    end
    API->>DB: Attribute recommendation purchase (if applicable)
    API-->>UI: 201 Created { order, transaction }
    UI-->>Buyer: Order confirmation
```

## Sequence Diagram — Dispute lifecycle

```mermaid
sequenceDiagram
    actor Buyer
    actor Seller
    actor Admin
    participant API as FastAPI (disputes.py)
    participant Svc as Dispute Service
    participant DB as PostgreSQL
    participant Chain as Blockchain Bridge

    Buyer->>API: POST /disputes (reason, evidence_score)
    API->>DB: Create Dispute (status=open), Order.status=disputed
    API->>Chain: record_trust_event(seller, "dispute_raised")

    Seller->>API: POST /disputes/{id}/evidence (evidence_score)
    API->>DB: Store seller evidence, status=under_review
    alt both evidence scores present
        API->>Svc: resolve(seller_trust, buyer_trust, evidence, delivery_confirmed, reason)
        Svc-->>API: outcome, seller_share_bps
        API->>DB: status=auto_resolved, Order.status=resolved
        API->>Chain: record_trust_event(seller, "dispute_resolved_seller|buyer")
    end

    opt Admin overrides
        Admin->>API: PATCH /disputes/{id}/arbitrate (seller_share_bps)
        API->>DB: status=arbitrated, Order.status=resolved
        API->>Chain: record_trust_event(seller, "dispute_resolved_seller|buyer")
    end
```

## Use Case Diagram

```mermaid
flowchart LR
    Buyer((Buyer))
    Seller((Seller))
    Admin((Admin))

    subgraph BuyerUC["Buyer Use Cases"]
        UC1(Search / Browse Products)
        UC2(View Recommendations)
        UC3(View Seller Trust Score)
        UC4(Purchase Product)
        UC5(Track Orders)
        UC6(Raise Dispute)
        UC7(Manage Wishlist)
        UC8(Leave Review)
        UC9(View Fraud Alerts)
        UC10(Edit Profile)
    end

    subgraph SellerUC["Seller Use Cases"]
        UC11(Manage Products / Inventory)
        UC12(Accept / Ship / Deliver Orders)
        UC13(View Trust Dashboard)
        UC14(View Fraud Risk)
        UC15(Respond to Disputes)
        UC16(Register Wallet On-Chain)
    end

    subgraph AdminUC["Admin Use Cases"]
        UC17(Manage Users)
        UC18(Monitor Fraud Dashboard)
        UC19(Arbitrate Disputes)
        UC20(Monitor Trust Scores)
        UC21(View Blockchain Explorer)
        UC22(View Analytics)
        UC23(Review Fraud Logs)
    end

    Buyer --> UC1 & UC2 & UC3 & UC4 & UC5 & UC6 & UC7 & UC8 & UC9 & UC10
    Seller --> UC11 & UC12 & UC13 & UC14 & UC15 & UC16 & UC10
    Admin --> UC17 & UC18 & UC19 & UC20 & UC21 & UC22 & UC23
```

## Class Diagram (core domain models)

Mirrors `backend/app/models/` — the SQLAlchemy ORM classes — not a
speculative design; every field shown exists in the actual model.

```mermaid
classDiagram
    class User {
        +UUID id
        +str email
        +str password_hash
        +UserRole role
        +bool is_active
        +bool is_verified
    }
    class Buyer {
        +UUID id
        +UUID user_id
        +str wallet_address
        +list~str~ preferred_categories
        +int account_age_days
    }
    class Seller {
        +UUID id
        +UUID user_id
        +str business_name
        +Decimal current_trust_score
        +bool is_onchain_registered
    }
    class Product {
        +UUID id
        +UUID seller_id
        +str category
        +Decimal price
        +int stock_quantity
        +bool is_active
    }
    class Order {
        +UUID id
        +UUID buyer_id
        +UUID seller_id
        +UUID product_id
        +OrderStatus status
        +Decimal amount
    }
    class Transaction {
        +UUID id
        +UUID order_id
        +PaymentMethod payment_method
        +bool is_fraud_flagged
        +Decimal fraud_probability
    }
    class FraudLog {
        +UUID id
        +UUID transaction_id
        +Decimal fraud_probability
        +dict risk_factors
        +str admin_decision
    }
    class TrustScore {
        +UUID id
        +UUID seller_id
        +Decimal score
        +int dispute_count
        +datetime computed_at
    }
    class Dispute {
        +UUID id
        +UUID order_id
        +DisputeReason reason
        +DisputeStatus status
        +int seller_share_bps
    }
    class Recommendation {
        +UUID id
        +UUID buyer_id
        +UUID product_id
        +str algorithm
        +bool was_clicked
    }
    class Review {
        +UUID id
        +UUID order_id
        +SmallInt rating
    }
    class Wishlist {
        +UUID id
        +UUID buyer_id
        +UUID product_id
    }
    class BlockchainHash {
        +UUID id
        +str entity_type
        +UUID entity_id
        +str tx_hash
        +str event_type
    }

    User "1" --> "0..1" Buyer
    User "1" --> "0..1" Seller
    Seller "1" --> "*" Product
    Buyer "1" --> "*" Order
    Seller "1" --> "*" Order
    Order "1" --> "*" Transaction
    Transaction "1" --> "*" FraudLog
    Seller "1" --> "*" TrustScore
    Order "1" --> "*" Dispute
    Order "1" --> "0..1" Review
    Buyer "1" --> "*" Recommendation
    Buyer "1" --> "*" Wishlist
```

## Deployment Diagram

Matches `docker-compose.yml` exactly — see
[deployment/README.md](../deployment/README.md) for what's actually been
run vs. reviewed-but-not-executed.

```mermaid
graph TB
    subgraph Host["Docker host"]
        subgraph net["Compose network"]
            FE["frontend container<br/>nginx:alpine<br/>:8080 → :80"]
            BE["backend container<br/>python:3.14-slim<br/>:8000 → :8000"]
            PG[("postgres container<br/>postgres:16-alpine")]
            RD[("redis container<br/>redis:7-alpine")]
        end
        VOL1[("trained_models/<br/>bind mount, read-only")]
        VOL2[("artifacts/ + deployments/<br/>bind mount, read-only")]
    end

    Browser["User's browser"] -->|:8080| FE
    FE -->|"/api/ proxy"| BE
    BE --> PG
    BE -.-> RD
    BE -.->|reads| VOL1
    BE -.->|reads| VOL2
    BE -.->|optional| ETH["Ethereum node<br/>(Sepolia or local Hardhat)"]
```

## Flowchart — Order status state machine

Enforced server-side in `backend/app/api/v1/endpoints/orders.py`
(`ALLOWED_TRANSITIONS`), not left to the client to get right.

```mermaid
stateDiagram-v2
    [*] --> created
    created --> confirmed
    created --> cancelled
    confirmed --> shipped
    confirmed --> cancelled
    shipped --> delivered
    created --> disputed: dispute raised
    confirmed --> disputed: dispute raised
    delivered --> disputed: dispute raised
    disputed --> resolved: auto-resolved or arbitrated
    cancelled --> [*]
    resolved --> [*]
    delivered --> [*]
```

Cancelling from `created`/`confirmed` restocks the product.
`disputed`/`resolved` are reachable only through the dispute-resolution
flow (`disputes.py`), never through the seller's own status-update
endpoint — a deliberate separation of concerns.

## Flowchart — Fraud detection decision

```mermaid
flowchart TD
    A[Order created] --> B[Extract live features:<br/>amount, buyer age, seller trust,<br/>disputes, velocity, rating, is_new_seller,<br/>payment_method, category]
    B --> C[RandomForest.predict_proba]
    C --> D{probability >= threshold<br/>0.5 default?}
    D -->|No| E[Transaction.is_fraud_flagged = false]
    D -->|Yes| F[Transaction.is_fraud_flagged = true]
    F --> G[Rank features by<br/>importance × deviation from mean]
    G --> H[Store top-3 as FraudLog.risk_factors]
    F --> I["record_trust_event(seller, 'fraud_flagged')<br/>best-effort, on-chain"]
    E --> J[FraudLog written either way —<br/>audit trail of every scored transaction]
    F --> J
```

## Flowchart — Dispute auto-resolution

```mermaid
flowchart TD
    A[Both evidence scores present] --> B["seller_case = 0.4×(seller_trust/100) + 0.6×evidence_seller"]
    A --> C["buyer_case = 0.4×(buyer_trust/100) + 0.6×evidence_buyer"]
    B --> D{delivery_confirmed?}
    D -->|Yes| E["seller_case += 0.15"]
    D -->|No, and reason=item_not_received| F["buyer_case += 0.20"]
    E --> G[Apply reason-specific adjustment]
    F --> G
    C --> G
    G --> H["seller_share = seller_case / (seller_case + buyer_case)"]
    H --> I{seller_share >= 0.65?}
    I -->|Yes| J[Release funds to seller]
    I -->|No| K{1 - seller_share >= 0.65?}
    K -->|Yes| L[Refund buyer]
    K -->|No| M[Split settlement<br/>partial refund]
```
