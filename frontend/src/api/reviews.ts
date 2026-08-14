import { api } from './client'
import type { Review } from '../types'

export const createReview = (orderId: string, rating: number, comment?: string) =>
  api.post<Review>('/reviews', { order_id: orderId, rating, comment }).then((r) => r.data)

export const listSellerReviews = (sellerId: string) =>
  api.get<Review[]>(`/reviews/sellers/${sellerId}`).then((r) => r.data)
