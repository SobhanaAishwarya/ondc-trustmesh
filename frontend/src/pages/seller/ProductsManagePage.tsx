import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createProduct, deactivateProduct, listMyProducts, updateProduct } from '../../api/products'
import { Badge, Button, Card, EmptyState, ErrorBanner, Input, Label, LoadingBlock, PageHeader, Select, TextArea } from '../../components/ui'
import { formatCurrency } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'
import { CATEGORIES } from '../../lib/constants'
import type { Product } from '../../types'

function ProductForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState(CATEGORIES[0])
  const [price, setPrice] = useState('')
  const [stock, setStock] = useState(10)

  const mutation = useMutation({
    mutationFn: () => createProduct({ name, description, category, price, stock_quantity: stock }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-products'] })
      onClose()
    },
  })

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    mutation.mutate()
  }

  return (
    <Card className="mb-6 p-6">
      <h2 className="mb-4 font-semibold">Add a product</h2>
      <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
        {mutation.error && (
          <div className="sm:col-span-2">
            <ErrorBanner message={apiErrorMessage(mutation.error, 'Could not create product')} />
          </div>
        )}
        <div>
          <Label>Name</Label>
          <Input required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label>Category</Label>
          <Select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        </div>
        <div className="sm:col-span-2">
          <Label>Description</Label>
          <TextArea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div>
          <Label>Price (₹)</Label>
          <Input required type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />
        </div>
        <div>
          <Label>Stock quantity</Label>
          <Input required type="number" min="0" value={stock} onChange={(e) => setStock(Number(e.target.value))} />
        </div>
        <div className="flex gap-2 sm:col-span-2">
          <Button type="submit" isLoading={mutation.isPending}>
            Create product
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  )
}

function ProductCard({ product }: { product: Product }) {
  const queryClient = useQueryClient()
  const [stock, setStock] = useState(product.stock_quantity)

  const stockMutation = useMutation({
    mutationFn: (value: number) => updateProduct(product.id, { stock_quantity: value }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['my-products'] }),
  })

  const deactivateMutation = useMutation({
    mutationFn: () => deactivateProduct(product.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['my-products'] }),
  })

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-brand-blue">{product.category}</p>
          <h3 className="font-semibold">{product.name}</h3>
        </div>
        {product.is_active ? <Badge tone="good">Active</Badge> : <Badge tone="neutral">Inactive</Badge>}
      </div>
      <p className="mt-2 font-semibold">{formatCurrency(product.price)}</p>
      <div className="mt-3 flex items-center gap-2">
        <Input
          type="number"
          min={0}
          value={stock}
          onChange={(e) => setStock(Number(e.target.value))}
          className="w-24"
        />
        <Button variant="secondary" isLoading={stockMutation.isPending} onClick={() => stockMutation.mutate(stock)}>
          Update stock
        </Button>
      </div>
      {product.is_active && (
        <Button variant="danger" className="mt-2 w-full" isLoading={deactivateMutation.isPending} onClick={() => deactivateMutation.mutate()}>
          Deactivate
        </Button>
      )}
    </Card>
  )
}

export function ProductsManagePage() {
  const [showForm, setShowForm] = useState(false)
  const { data, isLoading, error } = useQuery({ queryKey: ['my-products'], queryFn: listMyProducts })

  return (
    <div>
      <PageHeader
        title="My products"
        description="Manage your catalog and inventory."
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? 'Close' : '+ Add product'}</Button>}
      />
      {showForm && <ProductForm onClose={() => setShowForm(false)} />}
      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load products')} />}
      {data && data.length === 0 && <EmptyState title="No products yet" description="Add your first product to start selling." />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
    </div>
  )
}
