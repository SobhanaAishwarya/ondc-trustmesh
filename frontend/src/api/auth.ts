import { api } from './client'
import type { Me, TokenResponse, UserRole, WalletNonceResponse } from '../types'

export interface BuyerRegisterInput {
  email: string
  password: string
  full_name: string
  phone?: string
  preferred_categories?: string[]
  city?: string
}

export interface SellerRegisterInput {
  email: string
  password: string
  full_name: string
  phone?: string
  business_name: string
  gstin?: string
  city?: string
  delivery_radius_km?: number
}

export const registerBuyer = (input: BuyerRegisterInput) =>
  api.post<TokenResponse>('/auth/register/buyer', input).then((r) => r.data)

export const registerSeller = (input: SellerRegisterInput) =>
  api.post<TokenResponse>('/auth/register/seller', input).then((r) => r.data)

export const login = (email: string, password: string) =>
  api.post<TokenResponse>('/auth/login', { email, password }).then((r) => r.data)

export const fetchMe = () => api.get<Me>('/auth/me').then((r) => r.data)

export interface ProfileUpdateInput {
  full_name?: string
  phone?: string
  // wallet_address is deliberately absent — PATCH /me rejects it now.
  // Use getWalletNonce + linkWallet (a signed proof of ownership) instead.
  city?: string
  preferred_categories?: string[]
  business_name?: string
  gstin?: string
  delivery_radius_km?: number
}

export const updateMe = (input: ProfileUpdateInput) => api.patch<Me>('/auth/me', input).then((r) => r.data)

// Wallet sign-in — nonce, then a signature over it proves key ownership.
// See src/lib/wallet.ts for the actual browser-wallet calls.
export const getWalletNonce = (address: string) =>
  api.post<WalletNonceResponse>('/auth/wallet/nonce', { address }).then((r) => r.data.message)

export const linkWallet = (address: string, signature: string) =>
  api.post<Me>('/auth/wallet/link', { address, signature }).then((r) => r.data)

export const walletLogin = (address: string, signature: string) =>
  api.post<TokenResponse>('/auth/wallet/login', { address, signature }).then((r) => r.data)

// Revokes the refresh token server-side (app/core/cache.py's blocklist) so
// it can't be used again even if it leaked — best-effort, see AuthContext's
// logout(), which clears local tokens regardless of whether this succeeds.
export const logoutRequest = (refreshToken: string) => api.post('/auth/logout', { refresh_token: refreshToken })

export function roleHomePath(role: UserRole): string {
  if (role === 'seller') return '/seller'
  if (role === 'admin') return '/admin'
  return '/buyer'
}
