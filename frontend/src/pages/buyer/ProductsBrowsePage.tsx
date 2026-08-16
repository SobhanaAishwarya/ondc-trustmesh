import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listProducts } from '../../api/products'
import { Card, EmptyState, ErrorBanner, Input, LoadingBlock, PageHeader, Select } from '../../components/ui'
import { ProductImage } from '../../components/domain'
import { formatCurrency } from '../../lib/format'
import { CATEGORIES } from '../../lib/constants'
import { apiErrorMessage } from '../../api/client'

export function ProductsBrowsePage() {
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['products', { q, category }],
    queryFn: () => listProducts({ q: q || undefined, category: category || undefined, limit: 40 }),
  })

  return (
    <div>
      <PageHeader title="Browse products" description="Search the active catalog across all sellers." />

      <div className="mb-6 flex flex-wrap gap-3">
        <Input
          placeholder="Search products..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-xs"
        />
        <Select value={category} onChange={(e) => setCategory(e.target.value)} className="max-w-xs">
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
      </div>

      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load products')} />}
      {data && data.items.length === 0 && <EmptyState title="No products found" description="Try a different search or category." />}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.items.map((product) => (
          <Link key={product.id} to={`/buyer/products/${product.id}`}>
            <Card className="h-full overflow-hidden p-0 transition hover:shadow-md">
              <ProductImage src={product.image_url} alt={product.name} className="h-48 w-full" />
              <div className="p-4">
                <p className="text-xs font-medium text-brand-blue">{product.category}</p>
                <h3 className="mt-1 font-semibold">{product.name}</h3>
                <p className="mt-1 line-clamp-2 text-sm text-slate-500 dark:text-slate-400">{product.description}</p>
                <div className="mt-3 flex items-center justify-between">
                  <span className="font-semibold">{formatCurrency(product.price)}</span>
                  <span className="text-xs text-slate-400">{product.stock_quantity} in stock</span>
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
