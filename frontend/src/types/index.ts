// Type aliases over ./schema.ts, which is generated from the backend's
// OpenAPI spec (`npm run types:generate` — see frontend/README.md) rather
// than hand-written. That's what keeps these honest about the backend's
// actual request/response shapes: a renamed/removed backend field shows
// up here as a type error the next time types are regenerated, instead of
// silently drifting the way a hand-duplicated interface would.
//
// Every name below is chosen to match what call sites already import —
// regenerating schema.ts never requires touching any other frontend file.
import type { components } from './schema'

export type UserRole = components['schemas']['UserRole']

export type Me = components['schemas']['MeResponse']
export type User = Omit<Me, 'buyer' | 'seller'>
export type BuyerProfile = components['schemas']['BuyerProfileRead']
export type SellerProfile = components['schemas']['SellerProfileRead']

export type TokenResponse = components['schemas']['TokenResponse']
export type WalletNonceResponse = components['schemas']['WalletNonceResponse']

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export type Product = components['schemas']['ProductRead']
export type VendorMatch = components['schemas']['VendorMatchRead']

export type OrderStatus = components['schemas']['OrderStatus']
export type PaymentMethod = components['schemas']['PaymentMethod']
export type TransactionStatus = components['schemas']['TransactionStatus']

export type Order = components['schemas']['OrderRead']
export type Transaction = components['schemas']['TransactionRead']
export type OrderWithTransaction = components['schemas']['OrderWithTransaction']

// risk_factors and rule_signals are `dict | None` on the backend
// (app/schemas/fraud.py) — OpenAPI has no way to express their actual
// per-key shape, so both are refined here rather than left as the
// generated `unknown`. rule_signals mirrors app.ml.fraud_rules'
// evaluate_rule_based_signals output exactly (duplicate_account_suspected,
// high_velocity_bot_suspected).
export type FraudLog = Omit<components['schemas']['FraudLogRead'], 'risk_factors' | 'rule_signals'> & {
  risk_factors: Record<string, { value: number | string; contribution_score: number }> | null
  rule_signals: {
    duplicate_account_suspected: { triggered: boolean; phone_shared_by_accounts: number }
    high_velocity_bot_suspected: { triggered: boolean; orders_last_hour: number }
  } | null
}

export type TrustScore = components['schemas']['TrustScoreRead']
export type OnchainTrust = components['schemas']['OnchainTrustRead']

export type Review = components['schemas']['ReviewRead']

export type RecommendationItem = components['schemas']['RecommendationItemRead']
export type CTRReport = components['schemas']['CTRReport']

export type DisputeStatus = components['schemas']['DisputeStatus']
export type DisputeReason = components['schemas']['DisputeReason']
export type Dispute = components['schemas']['DisputeRead']

export type WishlistItem = components['schemas']['WishlistItemRead']

export type AdminUser = components['schemas']['AdminUserRead']
export type AnalyticsReport = components['schemas']['AnalyticsReport']
export type BlockchainHashEntry = components['schemas']['BlockchainHashRead']

// The global validation/error envelope (app/main.py's exception handlers)
// isn't a response_model on any route, so it has no OpenAPI schema to
// generate from — this one stays hand-written.
export interface ApiError {
  detail: string
}
