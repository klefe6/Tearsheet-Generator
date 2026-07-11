import { describe, expect, it } from 'vitest'
import { PRODUCTS, toApiRowPayload } from '../config/products'
import { buildRowFromForm } from './pendingRow'

/**
 * Contract tests for what Export All is allowed to send.
 * historical_rows / display_rows are never in these payloads — only the
 * manual form/row fields mapped by toApiRowPayload.
 */
describe('manual export payload contract', () => {
  it('TKP payload includes both NLV fields and never fee', () => {
    const row = buildRowFromForm(PRODUCTS[0], {
      date: '2026-07-11',
      stonexNlv: '82838.14',
      plus500Nlv: '85213.12',
      cash: '0',
    })
    const payload = toApiRowPayload(PRODUCTS[0], row)
    expect(payload).toEqual({
      date: '2026-07-11',
      stonex_nlv: 82838.14,
      plus500_nlv: 85213.12,
      cash_transfer: 0,
    })
    expect(Object.keys(payload).sort()).toEqual(
      ['cash_transfer', 'date', 'plus500_nlv', 'stonex_nlv'].sort(),
    )
  })

  it('never includes historical/display provenance fields', () => {
    for (const config of PRODUCTS) {
      const blanks: Record<string, string> = {}
      for (const f of config.fields) {
        blanks[f.key] = f.type === 'date' ? '2026-07-11' : '1'
      }
      const payload = toApiRowPayload(config, buildRowFromForm(config, blanks))
      expect(payload).not.toHaveProperty('source_label')
      expect(payload).not.toHaveProperty('source_detail')
      expect(payload).not.toHaveProperty('historical')
      expect(payload).not.toHaveProperty('display')
    }
  })
})
