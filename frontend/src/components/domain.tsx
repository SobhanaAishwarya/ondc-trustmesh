import { useState } from 'react'
import { Badge } from './ui'
import { titleCase } from '../lib/format'
import type { DisputeStatus, OrderStatus } from '../types'

/** Product photo with a graceful fallback (missing image_url, or a URL
 * that fails to load) instead of a broken-image icon — a plain tinted
 * box with a picture glyph reads as "no photo yet," not "this is broken." */
export function ProductImage({ src, alt, className = '' }: { src: string | null; alt: string; className?: string }) {
  const [failed, setFailed] = useState(false)

  if (!src || failed) {
    return (
      <div className={`flex items-center justify-center bg-slate-100 text-slate-300 dark:bg-slate-800 dark:text-slate-600 ${className}`}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-8 w-8">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <path d="M21 15l-5-5L5 21" />
        </svg>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`object-cover ${className}`}
    />
  )
}

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
