import { describe, expect, it } from 'vitest'
import {
  formatCurrency,
  formatCurrencyInput,
  formatTooltipCurrency,
} from './format'

/** Regression value: must never display as whole-dollar $192,876. */
const SAMPLE_NLV = 192875.99
const SAMPLE_FORMATTED = '$192,875.99'
const WHOLE_DOLLAR_ROUNDED = '$192,876'

describe('formatCurrency — table and card display', () => {
  it('renders thousands separators with exactly two decimal places', () => {
    expect(formatCurrency(SAMPLE_NLV)).toBe(SAMPLE_FORMATTED)
  })

  it('never rounds to the nearest whole dollar', () => {
    expect(formatCurrency(SAMPLE_NLV)).not.toBe(WHOLE_DOLLAR_ROUNDED)
    expect(formatCurrency(SAMPLE_NLV)).not.toContain('192,876')
  })

  it('preserves cents for string inputs from the API', () => {
    expect(formatCurrency('192875.99')).toBe(SAMPLE_FORMATTED)
  })

  it('formats other representative NLV amounts', () => {
    expect(formatCurrency(82838.14)).toBe('$82,838.14')
    expect(formatCurrency(125.5)).toBe('$125.50')
    expect(formatCurrency(-50.01)).toBe('-$50.01')
  })

  it('shows em dash for zero and invalid values', () => {
    expect(formatCurrency(0)).toBe('—')
    expect(formatCurrency('')).toBe('—')
    expect(formatCurrency('abc')).toBe('—')
  })
})

describe('formatTooltipCurrency — chart tooltips', () => {
  it('preserves cents (no whole-dollar rounding)', () => {
    expect(formatTooltipCurrency(SAMPLE_NLV)).toBe(SAMPLE_FORMATTED)
    expect(formatTooltipCurrency(SAMPLE_NLV)).not.toBe(WHOLE_DOLLAR_ROUNDED)
  })

  it('shows zero as $0.00', () => {
    expect(formatTooltipCurrency(0)).toBe('$0.00')
  })
})

describe('formatCurrencyInput — blur/paste normalization', () => {
  it('keeps two decimal places without rounding cents away', () => {
    expect(formatCurrencyInput('192875.99')).toBe('192875.99')
    expect(formatCurrencyInput('192875.99')).not.toBe('192876')
    expect(formatCurrencyInput('192875.99')).not.toBe('192876.00')
  })

  it('pads single-digit fractional inputs', () => {
    expect(formatCurrencyInput('192875.9')).toBe('192875.90')
  })

  it('does not add thousands separators (number inputs require plain decimals)', () => {
    expect(formatCurrencyInput('192875.99')).not.toContain(',')
  })
})
