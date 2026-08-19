import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { FraudBadge, OrderStatusBadge, ProductImage, TrustScoreBadge } from './domain'

describe('TrustScoreBadge', () => {
  it.each([
    [92, 'Trusted'],
    [60, 'Fair'],
    [30, 'Caution'],
    [10, 'High Risk'],
  ])('labels a score of %i as %s', (score, label) => {
    render(<TrustScoreBadge score={score} />)
    expect(screen.getByText(new RegExp(label))).toBeInTheDocument()
  })

  it('accepts a decimal score as a string, as it arrives from the API', () => {
    render(<TrustScoreBadge score="87.50" />)
    expect(screen.getByText(/88 — Trusted/)).toBeInTheDocument()
  })
})

describe('FraudBadge', () => {
  it('shows Clear when not flagged, regardless of the probability value', () => {
    render(<FraudBadge probability={0.9} isFlagged={false} />)
    expect(screen.getByText('Clear')).toBeInTheDocument()
  })

  it('shows the flagged probability as a percentage when flagged', () => {
    render(<FraudBadge probability="0.42" isFlagged={true} />)
    expect(screen.getByText('Flagged · 42%')).toBeInTheDocument()
  })

  it('treats a null probability on a flagged transaction as 0%, not a crash', () => {
    render(<FraudBadge probability={null} isFlagged={true} />)
    expect(screen.getByText('Flagged · 0%')).toBeInTheDocument()
  })
})

describe('OrderStatusBadge', () => {
  it('title-cases a snake_case status', () => {
    render(<OrderStatusBadge status="delivered" />)
    expect(screen.getByText('Delivered')).toBeInTheDocument()
  })
})

describe('ProductImage', () => {
  it('shows the placeholder glyph when no src is given, not a broken-image icon', () => {
    const { container } = render(<ProductImage src={null} alt="Wireless Earbuds Pro" className="h-40" />)
    expect(container.querySelector('img')).not.toBeInTheDocument()
    expect(container.querySelector('svg')).toBeInTheDocument()
  })

  it('renders the image inside a padded frame so object-contain never crops it', () => {
    render(<ProductImage src="https://images.pexels.com/photos/1/pexels-photo-1.jpeg" alt="Denim Jacket" className="h-40" />)
    const img = screen.getByRole('img', { name: 'Denim Jacket' })
    expect(img).toHaveClass('object-contain')
    expect(img.className).not.toContain('object-cover')
  })

  it('falls back to the placeholder if the image URL 404s or otherwise fails to load', () => {
    render(<ProductImage src="https://images.pexels.com/broken.jpg" alt="Broken Product" className="h-40" />)
    const img = screen.getByRole('img', { name: 'Broken Product' })

    fireEvent.error(img)

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(document.querySelector('svg')).toBeInTheDocument()
  })
})
