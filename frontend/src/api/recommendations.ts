import { api } from './client'
import type { RecommendationItem } from '../types'

export const getRecommendations = (topK = 10) =>
  api.get<RecommendationItem[]>('/recommendations', { params: { top_k: topK } }).then((r) => r.data)

export const clickRecommendation = (id: string) => api.post(`/recommendations/${id}/click`)
