import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listMyProducts } from '../../api/products'
import { listOrders } from '../../api/orders'
import { getCurrentTrustScore } from '../../api/trust'
import { useAuth } from '../../context/AuthContext'
import { Card, LoadingBlock, PageHeader, StatTile } from '../../components/ui'
import { TrustScoreBadge, OrderStatusBadge } from '../../components/domain'
import { formatCurrency } from '../../lib/format'

export function SellerDashboard() {
  const { user } = useAuth()
  const sellerId = user?.seller?.id ?? ''

  const productsQuery = useQuery({ queryKey: ['my-products'], queryFn: listMyProducts })
  const ordersQuery = useQuery({ queryKey: ['orders'], queryFn: () => listOrders(5) })
  const trustQuery = useQuery({
    queryKey: ['trust-current', sellerId],
    queryFn: () => getCurrentTrustScore(sellerId),
    enabled: !!sellerId,
  })

  const revenue =
    ordersQuery.data?.items
      .filter((o) => ['delivered', 'resolved'].includes(o.status))
      .reduce((sum, o) => sum + Number(o.amount), 0) ?? 0

  return (
    <div>
      <PageHeader title={`Welcome back, ${user?.full_name}`} description={user?.seller?.business_name} />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Products" value={productsQuery.data?.length ?? '—'} />
        <StatTile label="Recent orders" value={ordersQuery.data?.total ?? '—'} />
        <StatTile label="Revenue (recent)" value={formatCurrency(revenue)} />
        <Card className="p-4">
          <p className="text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">Trust score</p>
          <div className="mt-2">{trustQuery.data ? <TrustScoreBadge score={trustQuery.data.score} /> : <LoadingBlock />}</div>
        </Card>
      </div>

      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Recent orders</h2>
          <Link to="/seller/orders" className="text-sm text-brand-blue">
            Manage orders
          </Link>
        </div>
        {ordersQuery.isLoading && <LoadingBlock />}
        <ul className="space-y-2">
          {ordersQuery.data?.items.map((order) => (
            <li key={order.id} className="flex items-center justify-between text-sm">
              <span>{formatCurrency(order.amount)}</span>
              <OrderStatusBadge status={order.status} />
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
