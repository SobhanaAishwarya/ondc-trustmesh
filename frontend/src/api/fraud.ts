import { api } from './client'
import type { CTRReport, FraudLog, Page } from '../types'

export const listFraudAlerts = (onlyFlagged = true, limit = 20) =>
  api
    .get<Page<FraudLog>>('/fraud/alerts', { params: { only_flagged: onlyFlagged, limit } })
    .then((r) => r.data)

export const reviewFraudLog = (id: string, decision: 'confirmed_fraud' | 'false_positive') =>
  api.patch<FraudLog>(`/fraud/logs/${id}/review`, { admin_decision: decision }).then((r) => r.data)

export const getRecommendationCtr = (algorithm?: string) =>
  api.get<CTRReport>('/recommendations/ctr', { params: algorithm ? { algorithm } : {} }).then((r) => r.data)
