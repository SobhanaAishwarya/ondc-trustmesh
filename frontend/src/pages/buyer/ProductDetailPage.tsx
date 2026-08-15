import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getProduct } from '../../api/products'
import { getCurrentTrustScore } from '../../api/trust'
import { placeOrder } from '../../api/orders'
import { addToWishlist } from '../../api/wishlist'
import { apiErrorMessage } from '../../api/client'
import { Button, Card, ErrorBanner, LoadingBlock, Select } from '../../components/ui'
import { ProductImage, TrustScoreBadge } from '../../components/domain'
import { formatCurrency } from '../../lib/format'
import { PAYMENT_METHODS } from '../../lib/constants'
import type { PaymentMethod } from '../../types'

export function ProductDetailPage() {
  const { productId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [quantity, setQuantity] = useState(1)
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('upi')
  const [feedback, setFeedback] = useState<string | null>(null)

  const productQuery = useQuery({ queryKey: ['product', productId], queryFn: () => getProduct(productId) })
  const trustQuery = useQuery({
    queryKey: ['trust', productQuery.data?.seller_id],
    queryFn: () => getCurrentTrustScore(productQuery.data!.seller_id),
    enabled: !!productQuery.data,
  })

  const purchaseMutation = useMutation({
    mutationFn: () => placeOrder({ product_id: productId, quantity, payment_method: paymentMethod }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['product', productId] })
      navigate(`/buyer/orders?highlight=${result.order.id}`)
    },
  })

  const wishlistMutation = useMutation({
    mutationFn: () => addToWishlist(productId),
    onSuccess: () => setFeedback('Added to wishlist.'),
    onError: (err) => setFeedback(apiErrorMessage(err, 'Could not add to wishlist')),
  })

  if (productQuery.isLoading) return <LoadingBlock />
  if (productQuery.error || !productQuery.data) {
    return <ErrorBanner message={apiErrorMessage(productQuery.error, 'Product not found')} />
  }

  const product = productQuery.data
  const outOfStock = product.stock_quantity < quantity

  return (
    <div className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
      <Card className="overflow-hidden p-0">
        <ProductImage src={product.image_url} alt={product.name} className="h-64 w-full" />
        <div className="p-6">
        <p className="text-xs font-medium text-brand-blue">{product.category}</p>
        <h1 className="mt-1 text-2xl font-semibold">{product.name}</h1>
        <p className="mt-2 text-slate-600 dark:text-slate-300">{product.description}</p>
        <div className="mt-3 flex flex-wrap gap-1">
          {product.tags.map((tag) => (
            <span key={tag} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {tag}
            </span>
          ))}
        </div>
        <p className="mt-4 text-3xl font-bold">{formatCurrency(product.price)}</p>
        <p className="mt-1 text-sm text-slate-400">{product.stock_quantity} in stock</p>
        {trustQuery.data && (
          <div className="mt-4 flex items-center gap-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">Seller trust score:</span>
            <TrustScoreBadge score={trustQuery.data.score} />
          </div>
        )}
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="font-semibold">Purchase</h2>
        {feedback && <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{feedback}</p>}
        {purchaseMutation.error && (
          <div className="mt-3">
            <ErrorBanner message={apiErrorMessage(purchaseMutation.error, 'Could not place order')} />
          </div>
        )}
        <div className="mt-4 space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Quantity</label>
            <input
              type="number"
              min={1}
              max={product.stock_quantity}
              value={quantity}
              onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Payment method</label>
            <Select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}>
              {PAYMENT_METHODS.map((method) => (
                <option key={method} value={method}>
                  {method.toUpperCase()}
                </option>
              ))}
            </Select>
          </div>
          <p className="text-lg font-semibold">Total: {formatCurrency(Number(product.price) * quantity)}</p>
          <div className="flex gap-2">
            <Button
              className="flex-1"
              disabled={outOfStock}
              isLoading={purchaseMutation.isPending}
              onClick={() => purchaseMutation.mutate()}
            >
              {outOfStock ? 'Out of stock' : 'Buy now'}
            </Button>
            <Button variant="secondary" isLoading={wishlistMutation.isPending} onClick={() => wishlistMutation.mutate()}>
              ♡ Wishlist
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
