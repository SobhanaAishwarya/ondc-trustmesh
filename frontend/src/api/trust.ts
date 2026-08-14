import { api } from './client'
import type { OnchainTrust, Page, TrustScore } from '../types'

export const getCurrentTrustScore = (sellerId: string) =>
  api.get<TrustScore>(`/trust/sellers/${sellerId}`).then((r) => r.data)

export const getTrustScoreHistory = (sellerId: string, limit = 20) =>
  api.get<Page<TrustScore>>(`/trust/sellers/${sellerId}/history`, { params: { limit } }).then((r) => r.data)

export const recomputeTrustScore = (sellerId: string) =>
  api.post<TrustScore>(`/trust/sellers/${sellerId}/recompute`).then((r) => r.data)

export const getOnchainTrust = (sellerId: string) =>
  api.get<OnchainTrust>(`/trust/sellers/${sellerId}/onchain`).then((r) => r.data)
