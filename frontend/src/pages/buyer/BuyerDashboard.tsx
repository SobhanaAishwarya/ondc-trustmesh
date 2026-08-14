import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listOrders } from '../../api/orders'
import { listWishlist } from '../../api/wishlist'
import { getRecommendations } from '../../api/recommendations'
import { useAuth } from '../../context/AuthContext'
import { Card, LoadingBlock, PageHeader, StatTile } from '../../components/ui'
import { OrderStatusBadge } from '../../components/domain'
import { formatCurrency } from '../../lib/format'

export function BuyerDashboard() {
  const { user } = useAuth()
  const ordersQuery = useQuery({ queryKey: ['orders'], queryFn: () => listOrders(5) })
  const wishlistQuery = useQuery({ queryKey: ['wishlist'], queryFn: listWishlist })
  const recsQuery = useQuery({ queryKey: ['recommendations'], queryFn: () => getRecommendations(3) })

  return (
    <div>
      <PageHeader title={`Welcome back, ${user?.full_name}`} description="Here's what's happening with your account." />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatTile label="Total orders" value={ordersQuery.data?.total ?? '—'} />
        <StatTile label="Wishlist items" value={wishlistQuery.data?.length ?? '—'} />
        <StatTile label="Preferred categories" value={user?.buyer?.preferred_categories.length ?? 0} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Recent orders</h2>
            <Link to="/buyer/orders" className="text-sm text-brand-blue">
              View all
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

        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Top picks for you</h2>
            <Link to="/buyer/recommendations" className="text-sm text-brand-blue">
              View all
            </Link>
          </div>
          {recsQuery.isLoading && <LoadingBlock />}
          <ul className="space-y-2">
            {recsQuery.data?.map((item) => (
              <li key={item.id}>
                <Link to={`/buyer/products/${item.product.id}`} className="text-sm hover:underline">
                  {item.product.name} — {formatCurrency(item.product.price)}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}
