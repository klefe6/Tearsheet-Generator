// Shared types for the Glenn Daily Uploader frontend.

export type ProductId = 'TKP' | 'TCP' | 'AGM' | 'YQ'

/** Kind of input rendered in a product's entry form. */
export type FieldType = 'date' | 'currency'

export interface ProductField {
  /** Row key this input writes to. */
  key: string
  /** Visible label in the entry form. */
  label: string
  type: FieldType
  placeholder?: string
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
