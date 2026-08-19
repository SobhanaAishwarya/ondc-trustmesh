import { describe, expect, it } from 'vitest'
import { formatCurrency, formatPercent, titleCase } from './format'

describe('formatCurrency', () => {
  it('formats a number as INR with the ₹ symbol', () => {
    expect(formatCurrency(2499)).toBe('₹2,499.00')
  })

  it('accepts a numeric string, as prices arrive from the API', () => {
    expect(formatCurrency('149.50')).toBe('₹149.50')
  })

  it('formats zero without erroring', () => {
    expect(formatCurrency(0)).toBe('₹0.00')
  })
})

describe('formatPercent', () => {
  it('converts a 0-1 fraction to a percentage string with one decimal by default', () => {
    expect(formatPercent(0.774)).toBe('77.4%')
  })

  it('respects a custom digit count', () => {
    expect(formatPercent(0.9033, 2)).toBe('90.33%')
  })
})

describe('titleCase', () => {
  it('turns a snake_case enum value into a readable label', () => {
    expect(titleCase('under_review')).toBe('Under Review')
  })

  it('leaves a single already-capitalized word alone', () => {
    expect(titleCase('confirmed')).toBe('Confirmed')
  })
})
