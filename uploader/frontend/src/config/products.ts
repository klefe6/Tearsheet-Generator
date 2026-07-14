import type { ApiProgram, ApiRow } from '../api/client'
import type { ProductConfig, ProductRow } from '../types'

/** Max entry fields across products — used to align action buttons across cards. */
export const MAX_PRODUCT_FIELD_COUNT = 4

// The four products, each config-driven so one <ProductCard> renders all of them.
// Field rules are the source of truth for the entry forms AND the tables:
//   TKP  — the only product with BOTH StoneX NLV and Plus500 NLV.
//   AGM  — the only product with a Fee.
//   TCP, Y&Q — StoneX NLV + Cash Transfer only.
// Input tints: NLV fields on TKP/TCP/AGM = pale, ~80% transparent yellow;
// every other non-date field (cash transfers, AGM fee, all Y&Q currency
// fields) = light translucent pink. Date inputs stay white. `accountNumber` renders a
// copy-to-clipboard chip beside the label (only the four broker NLV accounts).
//
// Account chip data below is the LOCAL MOCK FALLBACK. When the backend is
// reachable, applyProgramMetadata() overlays account_label / account_number /
// copy_to_clipboard from GET /api/programs (matched via each field's
// `apiName`) and the backend becomes authoritative for chips.
export const PRODUCTS: ProductConfig[] = [
  {
    id: 'TKP',
    code: 'TKP',
    account: 'StoneX · Plus500',
    color: '#2a78d6', // blue
    colorSoft: '#eaf1fb',
    fields: [
      { key: 'date', apiName: 'date', label: 'Date', type: 'date' },
      { key: 'stonexNlv', apiName: 'stonex_nlv', label: 'StoneX NLV', type: 'currency', placeholder: '0.00', tint: 'yellow', accountNumber: '69060709', accountLabel: 'StoneX' },
      { key: 'plus500Nlv', apiName: 'plus500_nlv', label: 'Plus500 NLV', type: 'currency', placeholder: '0.00', tint: 'yellow', accountNumber: '50110102', accountLabel: 'Plus500' },
      { key: 'cash', apiName: 'cash_transfer', label: 'Cash Transfer', type: 'currency', placeholder: '0.00', tint: 'pink' },
    ],
    columns: [
      { key: 'date', label: 'Date', format: 'date' },
      { key: 'stonexNlv', label: 'StoneX NLV', format: 'currency' },
      { key: 'plus500Nlv', label: 'Plus500 NLV', format: 'currency' },
      { key: 'cash', label: 'Cash', format: 'currency' },
    ],
  },
  {
    id: 'TCP',
    code: 'TCP',
    account: 'StoneX',
    color: '#12a150', // green
    colorSoft: '#e7f6ee',
    fields: [
      { key: 'date', apiName: 'date', label: 'Date', type: 'date' },
      { key: 'stonexNlv', apiName: 'stonex_nlv', label: 'StoneX NLV', type: 'currency', placeholder: '0.00', tint: 'yellow', accountNumber: '69060795', accountLabel: 'StoneX' },
      { key: 'cash', apiName: 'cash_transfer', label: 'Cash Transfer', type: 'currency', placeholder: '0.00', tint: 'pink' },
    ],
    columns: [
      { key: 'date', label: 'Date', format: 'date' },
      { key: 'stonexNlv', label: 'StoneX NLV', format: 'currency' },
      { key: 'cash', label: 'Cash', format: 'currency' },
    ],
  },
  {
    id: 'AGM',
    code: 'AGM',
    account: 'TradeStation',
    color: '#7c3aed', // purple
    colorSoft: '#f1ecfd',
    fields: [
      { key: 'date', apiName: 'date', label: 'Date', type: 'date' },
      { key: 'tradestationNlv', apiName: 'tradestation_nlv', label: 'TradeStation NLV', type: 'currency', placeholder: '0.00', tint: 'yellow', accountNumber: '210TGG51', accountLabel: 'TradeStation' },
      { key: 'cash', apiName: 'cash_transfer', label: 'Cash Transfer', type: 'currency', placeholder: '0.00', tint: 'pink' },
      { key: 'fee', apiName: 'fee', label: 'Fee', type: 'currency', placeholder: '0.00', tint: 'pink' },
    ],
    columns: [
      { key: 'date', label: 'Date', format: 'date' },
      { key: 'tradestationNlv', label: 'TradeStation NLV', format: 'currency' },
      { key: 'cash', label: 'Cash', format: 'currency' },
      { key: 'fee', label: 'Fee', format: 'currency' },
    ],
  },
  {
    id: 'YQ',
    code: 'Y&Q',
    account: 'StoneX',
    color: '#e0a000', // orange / gold
    colorSoft: '#fbf1d9',
    fields: [
      { key: 'date', apiName: 'date', label: 'Date', type: 'date' },
      // No account chip: Y&Q's StoneX account number is not published yet
      // (backend serves copy_to_clipboard=false, no account_number).
      { key: 'stonexNlv', apiName: 'stonex_nlv', label: 'StoneX NLV', type: 'currency', placeholder: '0.00', tint: 'pink' },
      { key: 'cash', apiName: 'cash_transfer', label: 'Cash Transfer', type: 'currency', placeholder: '0.00', tint: 'pink' },
    ],
    columns: [
      { key: 'date', label: 'Date', format: 'date' },
      { key: 'stonexNlv', label: 'StoneX NLV', format: 'currency' },
      { key: 'cash', label: 'Cash', format: 'currency' },
    ],
  },
]

/**
 * Overlay backend program metadata (GET /api/programs) onto the local product
 * config. Backend is authoritative for account chips wherever it knows the
 * program AND the field:
 *
 *   - chip rendered only when copy_to_clipboard=true AND account_number set;
 *   - otherwise the chip is removed, even if the mock had one;
 *   - programs/fields the backend doesn't mention keep their mock values.
 *
 * Pure function — never mutates the input configs. Everything else about the
 * cards (labels, tints, columns, colors) stays from the local config so the
 * UI renders identically with or without a backend.
 */
/**
 * Build the POST /api/rows/{program} payload (snake_case, per-program fields
 * only) from a locally-keyed row. Only fields with an `apiName` are sent —
 * exactly the program's own fields, matching what the backend validates.
 */
export function toApiRowPayload(
  config: ProductConfig,
  row: ProductRow,
): Record<string, string | number> {
  const payload: Record<string, string | number> = {}
  for (const field of config.fields) {
    if (!field.apiName) continue
    const value = row[field.key]
    if (typeof value === 'string' || typeof value === 'number') {
      payload[field.apiName] = value
    }
  }
  return payload
}

/**
 * Map one GET/POST /api/rows/{program} row (snake_case) into the local
 * `ProductRow` shape the table/form already render. `id` is derived from
 * `(program, date)` — the same key the backend upserts on — so re-fetching
 * the same row never produces a duplicate React key.
 */
export function fromApiRow(config: ProductConfig, apiRow: ApiRow): ProductRow {
  const row: ProductRow = { id: `${config.id}-${apiRow.date}` }
  for (const field of config.fields) {
    if (!field.apiName) continue
    const value = apiRow[field.apiName]
    row[field.key] =
      field.type === 'date' ? String(value ?? '') : Number(value ?? 0)
  }
  if (typeof apiRow.id === 'number') row.sourceRowId = apiRow.id
  if (apiRow.export_state) row.exportState = apiRow.export_state
  else if (apiRow.exported) row.exportState = 'exported'
  else if (apiRow.excluded) row.exportState = 'excluded'
  else row.exportState = 'eligible'
  row.excludedReason = apiRow.excluded_reason ?? null
  return row
}

export function applyProgramMetadata(
  base: ProductConfig[],
  programs: ApiProgram[],
): ProductConfig[] {
  const programsByCode = new Map(programs.map((p) => [p.code, p]))
  return base.map((product) => {
    const remote = programsByCode.get(product.id)
    if (!remote) return product
    const remoteFields = new Map(remote.fields.map((f) => [f.name, f]))
    return {
      ...product,
      fields: product.fields.map((field) => {
        if (!field.apiName) return field
        const meta = remoteFields.get(field.apiName)
        if (!meta) return field
        const hasChip =
          meta.copy_to_clipboard === true &&
          typeof meta.account_number === 'string' &&
          meta.account_number.length > 0
        return {
          ...field,
          accountNumber: hasChip ? meta.account_number : undefined,
          accountLabel: hasChip ? meta.account_label : undefined,
        }
      }),
    }
  })
}
