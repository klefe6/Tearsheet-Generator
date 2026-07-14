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

/** One data row. `id` is a local, client-only key; field values are string|number. */
export interface ProductRow {
  id: string
  /** Backend daily_rows.id when known. */
  sourceRowId?: number
  exportState?: 'exported' | 'eligible' | 'excluded'
  excludedReason?: string | null
  [key: string]: string | number | undefined | null
}

/**
 * Truthful, distinguishable outcomes for "Export All Changes":
 *  - idle            no export attempted yet
 *  - pending         request in flight
 *  - offline_mock    backend unreachable -> purely local simulation, nothing sent anywhere
 *  - saved           backend reached, saved as an uploader-only preview (downstream export not enabled)
 *  - dry_run         downstream export enabled but EXPORT_DRY_RUN=true -> computed, nothing written
 *  - sandbox_success downstream export ran for real; every non-skipped program succeeded
 *  - partial_failure downstream export ran for real; some programs failed, others succeeded
 *  - failed          downstream export ran for real; every non-skipped program failed
 */
export type ExportOverallStatus =
  | 'idle'
  | 'pending'
  | 'offline_mock'
  | 'saved'
  | 'dry_run'
  | 'downstream_dry_run'
  | 'sandbox_success'
  | 'pushed'
  | 'partial_failure'
  | 'failed'
  | 'no_eligible'

export type ExportProgramOutcome =
  | 'success'
  | 'failure'
  | 'skipped'
  | 'dry_run'
  | 'no_rows'
  | 'partial_failure'

export interface ExportProgramStatus {
  program: string
  status: ExportProgramOutcome
  /** Present for skipped programs, e.g. "destination not configured". */
  reason?: string
}

export interface ExportUiState {
  lastExportAt: Date | null
  overallStatus: ExportOverallStatus
  canUndo: boolean
  /** Rows included in the last export (0 when none). */
  rowCount: number
  /** Per-program downstream results; empty when downstream export wasn't attempted. */
  programStatuses: ExportProgramStatus[]
  /** "sandbox" | "production" when downstream results are present. */
  targetEnv?: string
  /** Manual daily_rows found on the backend immediately before export. */
  manualRowsByProgram?: Partial<Record<ProductId, number>>
  /** Rows eligible for this export batch (unexported + not excluded). */
  eligibleCount?: number
  /** Historical rows excluded from Export All. */
  excludedCount?: number
  /** Already-exported manual rows. */
  exportedCount?: number
  /** Whether the export ran as dry-run (from backend response when present). */
  dryRun?: boolean
  /** Human-readable pre-export note (e.g. pending saves). */
  preflightNote?: string
}
