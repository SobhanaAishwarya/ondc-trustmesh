import { api } from './client'
import type { Dispute, DisputeReason, Page } from '../types'

export interface RaiseDisputeInput {
  order_id: string
  reason: DisputeReason
  description?: string
  evidence_score?: string
}

export const raiseDispute = (input: RaiseDisputeInput) => api.post<Dispute>('/disputes', input).then((r) => r.data)

export const submitEvidence = (id: string, evidenceScore: string) =>
  api.post<Dispute>(`/disputes/${id}/evidence`, { evidence_score: evidenceScore }).then((r) => r.data)

export const arbitrateDispute = (id: string, sellerShareBps: number) =>
  api.patch<Dispute>(`/disputes/${id}/arbitrate`, { seller_share_bps: sellerShareBps }).then((r) => r.data)

export const listDisputes = (limit = 20) =>
  api.get<Page<Dispute>>('/disputes', { params: { limit } }).then((r) => r.data)
