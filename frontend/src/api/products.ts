import { api } from './client'
import type { Page, Product } from '../types'

export interface ProductFilters {
  category?: string
  seller_id?: string
  q?: string
  limit?: number
  offset?: number
}

export const listProducts = (filters: ProductFilters = {}) =>
  api.get<Page<Product>>('/products', { params: filters }).then((r) => r.data)

export const listMyProducts = () => api.get<Product[]>('/products/mine').then((r) => r.data)

export const getProduct = (id: string) => api.get<Product>(`/products/${id}`).then((r) => r.data)

export interface ProductInput {
  name: string
  description?: string
  category: string
  tags?: string[]
  price: string
  stock_quantity: number
  image_url?: string
}

export const createProduct = (input: ProductInput) => api.post<Product>('/products', input).then((r) => r.data)

export const updateProduct = (id: string, input: Partial<ProductInput> & { is_active?: boolean }) =>
  api.patch<Product>(`/products/${id}`, input).then((r) => r.data)

export const deactivateProduct = (id: string) => api.delete(`/products/${id}`)
