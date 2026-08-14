import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { getAnalytics } from '../../api/admin'
import { Card, ErrorBanner, LoadingBlock, PageHeader, StatTile } from '../../components/ui'
import { formatCurrency, formatPercent, titleCase } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'

export function AdminDashboard() {
  const { data, isLoading, error } = useQuery({ queryKey: ['admin-analytics'], queryFn: getAnalytics })

  if (isLoading) return <LoadingBlock />
  if (error || !data) return <ErrorBanner message={apiErrorMessage(error, 'Failed to load analytics')} />

  const orderStatusData = Object.entries(data.orders_by_status).map(([status, count]) => ({
    status: titleCase(status),
    count,
  }))

  return (
    <div>
      <PageHeader title="Analytics" description="Network-wide numbers across users, commerce, fraud, and trust." />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Total users" value={data.total_users} hint={`${data.total_buyers} buyers · ${data.total_sellers} sellers`} />
        <StatTile label="Active products" value={data.active_products} hint={`${data.total_products} total`} />
        <StatTile label="Total orders" value={data.total_orders} />
        <StatTile label="Total revenue" value={formatCurrency(data.total_revenue)} />
        <StatTile label="Fraud flag rate" value={formatPercent(data.fraud_flag_rate)} hint={`${data.fraud_flagged_transactions} flagged`} />
        <StatTile label="Avg. seller trust" value={data.average_seller_trust_score.toFixed(1)} />
        <StatTile label="Open disputes" value={data.open_disputes} hint={`${data.total_disputes} total`} />
        <StatTile label="Transactions" value={data.total_transactions} />
      </div>

      <Card className="p-4">
        <h2 className="mb-4 font-semibold">Orders by status</h2>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={orderStatusData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-slate-800" />
            <XAxis dataKey="status" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="count" fill="#2a78d6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  )
}
