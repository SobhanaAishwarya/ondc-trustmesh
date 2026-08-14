import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { getCurrentTrustScore, getOnchainTrust, getTrustScoreHistory, recomputeTrustScore } from '../../api/trust'
import { useAuth } from '../../context/AuthContext'
import { Button, Card, ErrorBanner, LoadingBlock, PageHeader, StatTile } from '../../components/ui'
import { TrustScoreBadge } from '../../components/domain'
import { formatPercent } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'

export function TrustDashboardPage() {
  const { user } = useAuth()
  const sellerId = user?.seller?.id ?? ''
  const queryClient = useQueryClient()

  const currentQuery = useQuery({
    queryKey: ['trust-current', sellerId],
    queryFn: () => getCurrentTrustScore(sellerId),
    enabled: !!sellerId,
  })
  const historyQuery = useQuery({
    queryKey: ['trust-history', sellerId],
    queryFn: () => getTrustScoreHistory(sellerId, 30),
    enabled: !!sellerId,
  })
  const onchainQuery = useQuery({
    queryKey: ['trust-onchain', sellerId],
    queryFn: () => getOnchainTrust(sellerId),
    enabled: !!sellerId,
  })

  const recomputeMutation = useMutation({
    mutationFn: () => recomputeTrustScore(sellerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trust-current', sellerId] })
      queryClient.invalidateQueries({ queryKey: ['trust-history', sellerId] })
    },
  })

  if (currentQuery.isLoading) return <LoadingBlock />
  if (currentQuery.error || !currentQuery.data) {
    return <ErrorBanner message={apiErrorMessage(currentQuery.error, 'Failed to load trust score')} />
  }

  const score = currentQuery.data
  const chartData =
    historyQuery.data?.items
      .slice()
      .reverse()
      .map((row, i) => ({ index: i + 1, score: Number(row.score) })) ?? []

  return (
    <div>
      <PageHeader
        title="Trust dashboard"
        description="Your computed trust score, its inputs, and the separate on-chain ledger score."
        action={
          <Button isLoading={recomputeMutation.isPending} onClick={() => recomputeMutation.mutate()}>
            Recompute now
          </Button>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <TrustScoreBadge score={score.score} />
        {onchainQuery.data?.blockchain_enabled ? (
          <span className="text-sm text-slate-500 dark:text-slate-400">
            On-chain score: {onchainQuery.data.onchain_score ?? 'not registered'}
          </span>
        ) : (
          <span className="text-sm text-slate-400">Blockchain bridge is disabled — no on-chain score.</span>
        )}
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Order completion" value={score.order_completion_rate ? formatPercent(Number(score.order_completion_rate)) : '—'} />
        <StatTile label="Transaction success" value={score.transaction_success_rate ? formatPercent(Number(score.transaction_success_rate)) : '—'} />
        <StatTile label="Avg. rating" value={score.avg_customer_rating ? `${score.avg_customer_rating} / 5` : '—'} />
        <StatTile label="Fraud probability" value={score.fraud_probability ? formatPercent(Number(score.fraud_probability)) : '—'} />
        <StatTile label="Complaint ratio" value={score.complaint_ratio ? formatPercent(Number(score.complaint_ratio)) : '—'} />
        <StatTile label="Refund ratio" value={score.refund_ratio ? formatPercent(Number(score.refund_ratio)) : '—'} />
        <StatTile label="Late delivery ratio" value={score.late_delivery_ratio ? formatPercent(Number(score.late_delivery_ratio)) : '—'} />
        <StatTile label="Dispute count" value={score.dispute_count} />
      </div>

      <Card className="p-4">
        <h2 className="mb-4 font-semibold">Score history</h2>
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-slate-800" />
              <XAxis dataKey="index" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#2a78d6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-slate-400">Not enough history yet — recompute after more activity.</p>
        )}
      </Card>
    </div>
  )
}
