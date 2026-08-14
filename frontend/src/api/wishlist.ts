import { api } from './client'
import type { WishlistItem } from '../types'

export const listWishlist = () => api.get<WishlistItem[]>('/wishlist').then((r) => r.data)

export const addToWishlist = (productId: string) =>
  api.post<WishlistItem>('/wishlist', { product_id: productId }).then((r) => r.data)

export const removeFromWishlist = (productId: string) => api.delete(`/wishlist/${productId}`)
