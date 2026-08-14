import { useQuery } from '@tanstack/react-query'
import { listUsers } from '../../api/admin'
import { getCurrentTrustScore } from '../../api/trust'
import { Card, ErrorBanner, LoadingBlock, PageHeader } from '../../components/ui'
import { TrustScoreBadge } from '../../components/domain'
import { apiErrorMessage } from '../../api/client'
import type { AdminUser } from '../../types'

function SellerTrustRow({ seller }: { seller: AdminUser }) {
  const { data, isLoading } = useQuery({
    queryKey: ['trust-current', seller.seller_id],
    queryFn: () => getCurrentTrustScore(seller.seller_id!),
    enabled: !!seller.seller_id,
  })

  return (
    <tr>
      <td className="px-4 py-3">{seller.full_name}</td>
      <td className="px-4 py-3 text-slate-500 dark:text-slate-400">{seller.email}</td>
      <td className="px-4 py-3">{isLoading ? '…' : data ? <TrustScoreBadge score={data.score} /> : '—'}</td>
      <td className="px-4 py-3 text-slate-400">{data?.dispute_count ?? '—'}</td>
    </tr>
  )
}

export function TrustMonitoringPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-sellers'],
    queryFn: () => listUsers({ role: 'seller', limit: 50 }),
  })

  return (
    <div>
      <PageHeader title="Trust monitoring" description="Every seller's current computed trust score." />
      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load sellers')} />}
      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs tracking-wide text-slate-500 uppercase dark:border-slate-800 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3">Seller</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Trust score</th>
              <th className="px-4 py-3">Disputes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {data?.items.map((seller) => (
              <SellerTrustRow key={seller.id} seller={seller} />
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
