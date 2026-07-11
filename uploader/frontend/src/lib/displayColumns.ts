/**
 * Column layout for the bottom display tables (GET /api/display-rows).
 *
 * Derived from each program's field config so it can never drift from the
 * entry form:
 *   - TKP (the only program with BOTH StoneX and Plus500 NLV fields) shows
 *     the two NLV columns separately.
 *   - AGM (the only program with a fee field) shows a Fee column — manual
 *     rows only; historical rows report fee as null and render "—".
 *   - Everything else shows the single graph-equivalent Value.
 * Every table ends with the Source badge column.
 */

import type { ProductConfig } from '../types'

export interface DisplayColumn {
  key: 'date' | 'stonex_nlv' | 'plus500_nlv' | 'value' | 'fee' | 'source'
  label: string
  numeric: boolean
}

const DATE: DisplayColumn = { key: 'date', label: 'Date', numeric: false }
const SOURCE: DisplayColumn = { key: 'source', label: 'Source', numeric: false }

export function displayColumnsFor(config: ProductConfig): DisplayColumn[] {
  const fieldKeys = new Set(config.fields.map((f) => f.key))
  const hasBothNlv = fieldKeys.has('stonexNlv') && fieldKeys.has('plus500Nlv')
  if (hasBothNlv) {
    return [
      DATE,
      { key: 'stonex_nlv', label: 'StoneX NLV', numeric: true },
      { key: 'plus500_nlv', label: 'Plus500 NLV', numeric: true },
      SOURCE,
    ]
  }
  const columns: DisplayColumn[] = [DATE, { key: 'value', label: 'Value', numeric: true }]
  if (fieldKeys.has('fee')) {
    columns.push({ key: 'fee', label: 'Fee', numeric: true })
  }
  columns.push(SOURCE)
  return columns
}
