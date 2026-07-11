import { describe, expect, it } from 'vitest'
import { PRODUCTS } from '../config/products'
import { toApiRowPayload } from '../config/products'
import {
  buildRowFromForm,
  classifyPendingForm,
  hasPendingEntry,
  missingRequiredNlvLabels,
} from './pendingRow'

const byId = Object.fromEntries(PRODUCTS.map((p) => [p.id, p]))

describe('pendingRow — typing alone is not saved', () => {
  it('empty form is not pending', () => {
    const form = { date: '2026-07-11', stonexNlv: '', plus500Nlv: '', cash: '' }
    expect(hasPendingEntry(byId.TKP, form)).toBe(false)
    expect(classifyPendingForm(byId.TKP, form).status).toBe('empty')
  })

  it('typed NLV without Save is pending (not silently saved)', () => {
    const form = { date: '2026-07-11', stonexNlv: '100000', plus500Nlv: '50000', cash: '' }
    expect(hasPendingEntry(byId.TKP, form)).toBe(true)
    // classify says ready for Export-to-save-first; nothing has POSTed yet.
    expect(classifyPendingForm(byId.TKP, form).status).toBe('ready')
  })
})

describe('pendingRow — required fields', () => {
  it('TKP requires StoneX + Plus500', () => {
    const form = { date: '2026-07-11', stonexNlv: '100000', plus500Nlv: '', cash: '0' }
    expect(missingRequiredNlvLabels(byId.TKP, form)).toEqual(['Plus500 NLV'])
    const classified = classifyPendingForm(byId.TKP, form)
    expect(classified.status).toBe('incomplete')
    if (classified.status === 'incomplete') {
      expect(classified.missing).toContain('Plus500 NLV')
    }
  })

  it('TCP uses stonex_nlv (not a separate nlv field)', () => {
    const form = { date: '2026-07-11', stonexNlv: '48000', cash: '0' }
    const classified = classifyPendingForm(byId.TCP, form)
    expect(classified.status).toBe('ready')
    if (classified.status === 'ready') {
      const payload = toApiRowPayload(byId.TCP, classified.row)
      expect(payload).toEqual({
        date: '2026-07-11',
        stonex_nlv: 48000,
        cash_transfer: 0,
      })
      expect(payload).not.toHaveProperty('nlv')
      expect(payload).not.toHaveProperty('fee')
      expect(payload).not.toHaveProperty('plus500_nlv')
    }
  })

  it('AGM fee remains AGM-only', () => {
    const form = {
      date: '2026-07-11',
      tradestationNlv: '100000',
      cash: '0',
      fee: '250',
    }
    const classified = classifyPendingForm(byId.AGM, form)
    expect(classified.status).toBe('ready')
    if (classified.status === 'ready') {
      const payload = toApiRowPayload(byId.AGM, classified.row)
      expect(payload.fee).toBe(250)
      expect(payload.tradestation_nlv).toBe(100000)
    }
    const tcp = toApiRowPayload(
      byId.TCP,
      buildRowFromForm(byId.TCP, { date: '2026-07-11', stonexNlv: '1', cash: '0' }),
    )
    expect(tcp).not.toHaveProperty('fee')
  })
})

describe('pendingRow — Y&Q is still a program form but export skips downstream', () => {
  it('Y&Q can be classified as a ready pending manual row', () => {
    const form = { date: '2026-07-11', stonexNlv: '1000', cash: '0' }
    const classified = classifyPendingForm(byId.YQ, form)
    expect(classified.status).toBe('ready')
  })
})
