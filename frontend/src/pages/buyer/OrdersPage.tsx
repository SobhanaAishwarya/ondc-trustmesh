import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listOrders } from '../../api/orders'
import { getProduct } from '../../api/products'
import { Card, EmptyState, ErrorBanner, LoadingBlock, PageHeader } from '../../components/ui'
import { OrderStatusBadge } from '../../components/domain'
import { formatCurrency, formatDate } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'
import type { Order } from '../../types'
import { DisputeForm } from '../shared/DisputeForm'
import { ReturnForm } from './ReturnForm'
import { ReviewForm } from './ReviewForm'

const RETURN_WINDOW_DAYS = 7

function isWithinReturnWindow(order: Order): boolean {
  if (order.status !== 'delivered' || !order.delivered_at) return false
  const daysSinceDelivery = (Date.now() - new Date(order.delivered_at).getTime()) / (1000 * 60 * 60 * 24)
  return daysSinceDelivery <= RETURN_WINDOW_DAYS
}

function OrderProductName({ productId }: { productId: string }) {
  const { data } = useQuery({ queryKey: ['product', productId], queryFn: () => getProduct(productId) })
  return <span>{data?.name ?? '…'}</span>
}

function OrderRow({ order }: { order: Order }) {
  const [openAction, setOpenAction] = useState<'dispute' | 'review' | 'return' | null>(null)
  const canDispute = ['confirmed', 'shipped', 'delivered'].includes(order.status)
  const canReview = order.status === 'delivered'
  const canReturn = isWithinReturnWindow(order)

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium">
            <OrderProductName productId={order.product_id} /> × {order.quantity}
          </p>
          <p className="text-xs text-slate-400">{formatDate(order.created_at)}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-semibold">{formatCurrency(order.amount)}</span>
          <OrderStatusBadge status={order.status} />
        </div>
      </div>
      {(canDispute || canReview || canReturn) && (
        <div className="mt-3 flex gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
          {canReturn && (
            <button
              onClick={() => setOpenAction(openAction === 'return' ? null : 'return')}
              className="text-xs font-medium text-brand-blue hover:underline"
            >
              Request return
            </button>
          )}
          {canDispute && (
            <button
              onClick={() => setOpenAction(openAction === 'dispute' ? null : 'dispute')}
              className="text-xs font-medium text-brand-blue hover:underline"
            >
              Raise dispute
            </button>
          )}
          {canReview && (
            <button
              onClick={() => setOpenAction(openAction === 'review' ? null : 'review')}
              className="text-xs font-medium text-brand-blue hover:underline"
            >
              Leave review
            </button>
          )}
        </div>
      )}
      {openAction === 'return' && <ReturnForm orderId={order.id} onDone={() => setOpenAction(null)} />}
      {openAction === 'dispute' && <DisputeForm orderId={order.id} onDone={() => setOpenAction(null)} />}
      {openAction === 'review' && <ReviewForm orderId={order.id} onDone={() => setOpenAction(null)} />}
    </Card>
  )
}

export function OrdersPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['orders'], queryFn: () => listOrders() })

  return (
    <div>
      <PageHeader title="My orders" description="Track purchases, raise disputes, and leave reviews once delivered." />
      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load orders')} />}
      {data && data.items.length === 0 && <EmptyState title="No orders yet" description="Browse products to make your first purchase." />}
      <div className="space-y-3">
        {data?.items.map((order) => (
          <OrderRow key={order.id} order={order} />
        ))}
      </div>
    </div>
  )
}
