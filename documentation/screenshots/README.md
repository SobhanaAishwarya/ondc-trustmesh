# Screenshots

Captured with an automated headless browser (Playwright) driving the real
frontend against a real running backend — the same method used to verify
the frontend during development (see `frontend/README.md`'s "Verified
against the real backend" section) and the E2E test
(`frontend/e2e/purchase-flow.spec.ts`). Every number and product name
visible in these screenshots is real data returned by the actual API, not
mocked or hand-edited into the page.

| File | Shows |
|---|---|
| `01-landing.png` | Public landing page |
| `02-login.png` | Login page |
| `03-signup-seller.png` | Signup page, seller role selected |
| `04-seller-dashboard-light.png` | Seller dashboard, light theme |
| `05-seller-dashboard-dark.png` | Same dashboard immediately after the dark-mode toggle |
| `06-seller-products.png` | Seller product management, after adding a product |
| `07-seller-trust-dashboard.png` | Seller's own trust score, factor breakdown, and history panel — score `75 — Trusted`, correctly lazily computed on first read |
| `08-buyer-dashboard.png` | Buyer dashboard |
| `09-buyer-browse-products.png` | Buyer product catalog, showing the seller's product |
| `10-buyer-product-detail.png` | Product detail page with live seller trust score and purchase form |
| `11-buyer-orders.png` | Buyer's order history after a real purchase went through |
| `12-buyer-recommendations.png` | Recommendation engine output |
| `13-admin-analytics.png` | Admin analytics dashboard — real aggregate counts (users, revenue, orders-by-status chart) computed from the seeded data |
| `14-admin-users.png` | Admin user management |
| `15-admin-fraud-dashboard.png` | Admin fraud dashboard (empty — the one seeded purchase wasn't flagged, an accurate state, not a broken page) |

`04`/`05` show the dark-mode toggle changing the seller's own session;
the buyer (`08`+) and admin (`13`+) screenshots are light because each
was captured in its own isolated browser context (separate
`localStorage`), not because persistence failed — dark mode surviving a
logout/login *within the same browser* was verified separately during
development (single-context run, documented in `frontend/README.md`'s
"Verified against the real backend" section), just not re-demonstrated
in this particular screenshot set.
