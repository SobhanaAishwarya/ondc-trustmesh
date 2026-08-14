import { Badge } from './ui'
import { titleCase } from '../lib/format'
import type { DisputeStatus, OrderStatus } from '../types'

export function TrustScoreBadge({ score }: { score: number | string }) {
  const value = typeof score === 'string' ? Number(score) : score
  if (value >= 75) return <Badge tone="good">{value.toFixed(0)} — Trusted</Badge>
  if (value >= 50) return <Badge tone="warning">{value.toFixed(0)} — Fair</Badge>
  if (value >= 25) return <Badge tone="serious">{value.toFixed(0)} — Caution</Badge>
  return <Badge tone="critical">{value.toFixed(0)} — High Risk</Badge>
}

export function FraudBadge({ probability, isFlagged }: { probability: number | string | null; isFlagged: boolean }) {
  if (!isFlagged) return <Badge tone="good">Clear</Badge>
  const value = probability === null ? 0 : typeof probability === 'string' ? Number(probability) : probability
  return <Badge tone="critical">Flagged · {(value * 100).toFixed(0)}%</Badge>
}

const ORDER_STATUS_TONE: Record<OrderStatus, 'neutral' | 'good' | 'warning' | 'serious' | 'critical' | 'info'> = {
  created: 'neutral',
  confirmed: 'info',
  shipped: 'warning',
  delivered: 'good',
  disputed: 'serious',
  resolved: 'good',
  cancelled: 'critical',
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return <Badge tone={ORDER_STATUS_TONE[status]}>{titleCase(status)}</Badge>
}

const DISPUTE_STATUS_TONE: Record<DisputeStatus, 'neutral' | 'good' | 'warning' | 'serious' | 'critical' | 'info'> = {
  open: 'serious',
  under_review: 'warning',
  auto_resolved: 'good',
  arbitrated: 'good',
  closed: 'neutral',
}

export function DisputeStatusBadge({ status }: { status: DisputeStatus }) {
  return <Badge tone={DISPUTE_STATUS_TONE[status]}>{titleCase(status)}</Badge>
}
