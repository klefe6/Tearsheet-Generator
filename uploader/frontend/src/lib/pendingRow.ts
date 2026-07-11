// Pure helpers for in-progress card form state. Typing alone never counts as
// saved — these only describe what is currently in the form inputs.

import { makeRowId } from '../data/rows'
import type { ProductConfig, ProductId, ProductRow } from '../types'

export type FormState = Record<string, string>

/** NLV fields that must be filled before a row can be saved/exported. */
export function isRequiredNlvField(field: { type: string; apiName?: string }): boolean {
  return field.type === 'currency' && Boolean(field.apiName?.endsWith('_nlv'))
}

/** True when any currency input has non-empty typed text (pending unsaved work). */
export function hasPendingEntry(config: ProductConfig, form: FormState): boolean {
  return config.fields.some(
    (field) => field.type === 'currency' && String(form[field.key] ?? '').trim() !== '',
  )
}

/** Labels of required NLV fields that are still blank. */
export function missingRequiredNlvLabels(config: ProductConfig, form: FormState): string[] {
  return config.fields
    .filter(isRequiredNlvField)
    .filter((field) => String(form[field.key] ?? '').trim() === '')
    .map((field) => field.label)
}

/**
 * Build a ProductRow from form state. Blank optional currency fields
 * (cash_transfer / fee) become 0; required NLV blanks stay as NaN so callers
 * can reject incomplete pending rows before POST.
 */
export function buildRowFromForm(config: ProductConfig, form: FormState): ProductRow {
  const row: ProductRow = { id: makeRowId(config.id) }
  for (const field of config.fields) {
    if (field.type === 'date') {
      row[field.key] = String(form[field.key] ?? '').trim()
      continue
    }
    const raw = String(form[field.key] ?? '').trim()
    if (raw === '') {
      row[field.key] = isRequiredNlvField(field) ? Number.NaN : 0
    } else {
      const parsed = Number(raw)
      row[field.key] = Number.isFinite(parsed) ? parsed : Number.NaN
    }
  }
  return row
}

export interface PendingRowReady {
  productId: ProductId
  row: ProductRow
}

export type PendingRowResult =
  | { status: 'empty' }
  | { status: 'incomplete'; productId: ProductId; missing: string[] }
  | { status: 'invalid'; productId: ProductId; message: string }
  | { status: 'ready'; productId: ProductId; row: ProductRow }

/** Classify one card's form for save-before-export. */
export function classifyPendingForm(config: ProductConfig, form: FormState): PendingRowResult {
  if (!hasPendingEntry(config, form)) return { status: 'empty' }

  const missing = missingRequiredNlvLabels(config, form)
  if (missing.length > 0) {
    return { status: 'incomplete', productId: config.id, missing }
  }

  const row = buildRowFromForm(config, form)
  for (const field of config.fields) {
    if (field.type !== 'currency') continue
    const value = row[field.key]
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      return {
        status: 'invalid',
        productId: config.id,
        message: `${field.label} must be a valid number`,
      }
    }
  }
  if (!String(row.date ?? '').trim()) {
    return { status: 'invalid', productId: config.id, message: 'Date is required' }
  }
  return { status: 'ready', productId: config.id, row }
}
