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

export type OrderStatus = components['schemas']['OrderStatus']
export type PaymentMethod = components['schemas']['PaymentMethod']
export type TransactionStatus = components['schemas']['TransactionStatus']

export type Order = components['schemas']['OrderRead']
export type Transaction = components['schemas']['TransactionRead']
export type OrderWithTransaction = components['schemas']['OrderWithTransaction']

// risk_factors is `dict | None` on the backend (app/schemas/fraud.py) —
// OpenAPI has no way to express its actual per-key shape, so that one
// field is refined here rather than left as the generated `unknown`.
export type FraudLog = Omit<components['schemas']['FraudLogRead'], 'risk_factors'> & {
  risk_factors: Record<string, { value: number | string; contribution_score: number }> | null
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
