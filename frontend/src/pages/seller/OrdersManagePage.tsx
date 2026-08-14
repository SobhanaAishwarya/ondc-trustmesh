import { useQuery } from '@tanstack/react-query'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { listOrders, updateOrderStatus } from '../../api/orders'
import { getProduct } from '../../api/products'
import { Button, Card, EmptyState, ErrorBanner, LoadingBlock, PageHeader } from '../../components/ui'
import { OrderStatusBadge } from '../../components/domain'
import { formatCurrency, formatDate } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'
import type { Order, OrderStatus } from '../../types'

const NEXT_STATUS: Partial<Record<OrderStatus, OrderStatus[]>> = {
  created: ['confirmed', 'cancelled'],
  confirmed: ['shipped', 'cancelled'],
  shipped: ['delivered'],
}

function OrderProductName({ productId }: { productId: string }) {
  const { data } = useQuery({ queryKey: ['product', productId], queryFn: () => getProduct(productId) })
  return <span>{data?.name ?? '…'}</span>
}

function OrderRow({ order }: { order: Order }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (status: OrderStatus) => updateOrderStatus(order.id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orders'] }),
  })
  const nextOptions = NEXT_STATUS[order.status] ?? []

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
      {mutation.error && (
        <div className="mt-2">
          <ErrorBanner message={apiErrorMessage(mutation.error, 'Could not update order')} />
        </div>
      )}
      {nextOptions.length > 0 && (
        <div className="mt-3 flex gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
          {nextOptions.map((status) => (
            <Button
              key={status}
              variant={status === 'cancelled' ? 'danger' : 'primary'}
              isLoading={mutation.isPending}
              onClick={() => mutation.mutate(status)}
            >
              Mark {status}
            </Button>
          ))}
        </div>
      )}
    </Card>
  )
}

export function OrdersManagePage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['orders'], queryFn: () => listOrders(50) })

  return (
    <div>
      <PageHeader title="Orders" description="Accept, ship, and deliver orders on your products." />
      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load orders')} />}
      {data && data.items.length === 0 && <EmptyState title="No orders yet" description="Orders on your products will show up here." />}
      <div className="space-y-3">
        {data?.items.map((order) => (
          <OrderRow key={order.id} order={order} />
        ))}
      </div>
    </div>
  )
}
