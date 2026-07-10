// Shared types for the Glenn Daily Uploader frontend.

export type ProductId = 'TKP' | 'TCP' | 'AGM' | 'YQ'

/** Kind of input rendered in a product's entry form. */
export type FieldType = 'date' | 'currency'

/**
 * Background tint for currency inputs (date inputs always stay white):
 * 'yellow' = pale, ~80% transparent yellow wash (NLV fields on TKP/TCP/AGM),
 * 'pink'   = light translucent red/pink (all other non-date fields, incl. Y&Q).
 */
export type CurrencyInputTint = 'yellow' | 'pink'

export interface ProductField {
  /** Row key this input writes to. */
  key: string
  /**
   * Backend field name for this input (snake_case, e.g. "stonex_nlv") —
   * matches `fields[].name` in GET /api/programs so backend metadata can be
   * merged onto this field. Omit for purely local fields.
   */
  apiName?: string
  /** Visible label in the entry form. */
  label: string
  type: FieldType
  placeholder?: string
  /** Background tint for currency inputs. Omit for date fields (white). */
  tint?: CurrencyInputTint
  /** Broker account number shown as a copy-to-clipboard chip next to the label. */
  accountNumber?: string
  /** Broker name for the account chip (tooltip/aria only, e.g. "StoneX"). */
  accountLabel?: string
}

/** How a table cell is rendered. */
export type ColumnFormat = 'date' | 'currency'

export interface ProductColumn {
  /** Row key this column reads from. */
  key: string
  /** Visible header in the table. */
  label: string
  format: ColumnFormat
}

export interface ProductConfig {
  id: ProductId
  /** Short display code shown in the card header, e.g. "TKP". */
  code: string
  /** Accounts feeding this product, shown as the header subtitle. */
  account: string
  /** Brand color (hex). Also used as the card header background. */
  color: string
  /** Soft tint of the brand color, for table header / accent backgrounds. */
  colorSoft: string
  /** Entry-form fields, in order. */
  fields: ProductField[]
  /** Table columns, in order. */
  columns: ProductColumn[]
}

/** One data row. `id` is a local, client-only key; the rest are field values. */
export interface ProductRow {
  id: string
  [key: string]: string | number
}

/** Mock export / undo UI state (frontend-only until backend wiring). */
export type ExportProcessStatus = 'idle' | 'pending' | 'processed'

export interface ExportUiState {
  lastExportAt: Date | null
  status: ExportProcessStatus
  canUndo: boolean
  /** Rows included in the last mock export (0 when none). */
  rowCount: number
}
