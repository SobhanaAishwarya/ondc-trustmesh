import { api } from './client'
import type { AdminUser, AnalyticsReport, BlockchainHashEntry, Page, UserRole } from '../types'

export interface AdminUserFilters {
  role?: UserRole
  is_active?: boolean
  q?: string
  limit?: number
}

export const listUsers = (filters: AdminUserFilters = {}) =>
  api.get<Page<AdminUser>>('/admin/users', { params: filters }).then((r) => r.data)

export const setUserStatus = (id: string, isActive: boolean) =>
  api.patch<AdminUser>(`/admin/users/${id}/status`, { is_active: isActive }).then((r) => r.data)

export const getAnalytics = () => api.get<AnalyticsReport>('/admin/analytics').then((r) => r.data)

export const listBlockchainHashes = (limit = 30) =>
  api.get<Page<BlockchainHashEntry>>('/admin/blockchain-hashes', { params: { limit } }).then((r) => r.data)
