import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clickRecommendation, getRecommendations } from '../../api/recommendations'
import { Badge, Card, EmptyState, ErrorBanner, LoadingBlock, PageHeader } from '../../components/ui'
import { formatCurrency } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'

const ALGORITHM_LABEL: Record<string, string> = {
  hybrid: 'Personalized',
  popularity_cold_start: 'Popular right now',
}

export function RecommendationsPage() {
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({ queryKey: ['recommendations'], queryFn: () => getRecommendations(12) })

  const clickMutation = useMutation({
    mutationFn: (id: string) => clickRecommendation(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['recommendations'] }),
  })

  return (
    <div>
      <PageHeader
        title="Recommended for you"
        description="A hybrid of your preferences, purchase history, and seller trust — falls back to popular items until you have both."
      />
      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load recommendations')} />}
      {data && data.length === 0 && <EmptyState title="No recommendations yet" description="Browse the catalog to get started." />}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.map((item) => (
          <Link
            key={item.id}
            to={`/buyer/products/${item.product.id}`}
            onClick={() => !item.was_clicked && clickMutation.mutate(item.id)}
          >
            <Card className="h-full p-4 transition hover:shadow-md">
              <div className="flex items-center justify-between">
                <Badge tone="info">{ALGORITHM_LABEL[item.algorithm] ?? item.algorithm}</Badge>
                <span className="text-xs text-slate-400">#{item.rank}</span>
              </div>
              <h3 className="mt-2 font-semibold">{item.product.name}</h3>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.product.category}</p>
              <p className="mt-3 font-semibold">{formatCurrency(item.product.price)}</p>
              {item.estimated_delivery_days != null && (
                <p className="mt-1 text-xs text-slate-400">
                  {item.distance_km != null && item.distance_km > 0 ? `${Math.round(item.distance_km)} km away · ` : ''}
                  Delivery in {item.estimated_delivery_days} day{item.estimated_delivery_days === 1 ? '' : 's'}
                </p>
              )}
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
