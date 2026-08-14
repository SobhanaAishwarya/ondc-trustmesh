import { api } from './client'
import type { Dispute, DisputeReason, Order, OrderStatus, OrderWithTransaction, Page, PaymentMethod, Transaction } from '../types'

export interface PlaceOrderInput {
  product_id: string
  quantity: number
  payment_method: PaymentMethod
}

export const placeOrder = (input: PlaceOrderInput) =>
  api.post<OrderWithTransaction>('/orders', input).then((r) => r.data)

export const listOrders = (limit = 50, offset = 0) =>
  api.get<Page<Order>>('/orders', { params: { limit, offset } }).then((r) => r.data)

export const getOrder = (id: string) => api.get<Order>(`/orders/${id}`).then((r) => r.data)

export const getOrderTransactions = (id: string) =>
  api.get<Transaction[]>(`/orders/${id}/transactions`).then((r) => r.data)

export const updateOrderStatus = (id: string, status: OrderStatus) =>
  api.patch<Order>(`/orders/${id}/status`, { status }).then((r) => r.data)

export interface RequestReturnInput {
  reason: DisputeReason
  description?: string
  item_condition?: 'good' | 'damaged' | 'missing_parts'
}

export const requestReturn = (id: string, input: RequestReturnInput) =>
  api.post<Dispute>(`/orders/${id}/return`, input).then((r) => r.data)
