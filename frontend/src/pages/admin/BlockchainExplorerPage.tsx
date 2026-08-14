import { useQuery } from '@tanstack/react-query'
import { listBlockchainHashes } from '../../api/admin'
import { Badge, Card, EmptyState, ErrorBanner, LoadingBlock, PageHeader } from '../../components/ui'
import { formatDate, titleCase } from '../../lib/format'
import { apiErrorMessage } from '../../api/client'

export function BlockchainExplorerPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['blockchain-hashes'], queryFn: () => listBlockchainHashes(50) })

  return (
    <div>
      <PageHeader
        title="Blockchain explorer"
        description="Every on-chain write the backend has made — trust registrations and TrustScore.sol events."
      />
      {isLoading && <LoadingBlock />}
      {error && <ErrorBanner message={apiErrorMessage(error, 'Failed to load on-chain records')} />}
      {data && data.items.length === 0 && (
        <EmptyState
          title="No on-chain activity yet"
          description="Enable the blockchain bridge (BLOCKCHAIN_ENABLED=true in the backend) and have a seller set a wallet address to see entries here."
        />
      )}

      <div className="space-y-3">
        {data?.items.map((entry) => (
          <Card key={entry.id} className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Badge tone="info">{titleCase(entry.event_type)}</Badge>
              <span className="text-xs text-slate-400">{formatDate(entry.created_at)}</span>
            </div>
            <p className="mt-2 font-mono text-xs break-all text-slate-500 dark:text-slate-400">{entry.tx_hash}</p>
            <p className="mt-1 text-xs text-slate-400">
              {entry.entity_type} · block #{entry.block_number ?? '—'} · {entry.network}
            </p>
          </Card>
        ))}
      </div>
    </div>
  )
}
