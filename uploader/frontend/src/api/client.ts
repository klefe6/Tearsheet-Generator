// Minimal backend API client.
//
// The ONLY backend call this frontend makes is the optional, read-only
// GET /programs metadata fetch below. Rows, export and undo remain purely
// local mock actions — no other endpoint is called anywhere in the app.
//
// The fetch is best-effort by design: any failure (backend down, CORS,
// timeout, bad shape) resolves to `null` and the app keeps rendering from
// the local mock config in src/config/products.ts, so the UI never needs
// a running backend for local preview.

/** One field's metadata as served by GET /api/programs (backend PR #23). */
export interface ApiProgramField {
  name: string
  label: string
  type: string
  required: boolean
  default: number | null
  copy_to_clipboard: boolean
  account_label?: string
  account_number?: string
}

/** One program's metadata as served by GET /api/programs. */
export interface ApiProgram {
  code: string
  label: string
  fields: ApiProgramField[]
}

const RAW_BASE: string = import.meta.env.VITE_API_BASE_URL || ''

/** Backend base URL (e.g. "https://uploader-sandbox.hcresearch.ltd/api"). */
export const API_BASE_URL = RAW_BASE.replace(/\/+$/, '')

/** Give the metadata fetch a short leash so a dead backend never stalls the UI. */
const METADATA_TIMEOUT_MS = 4000

function isApiProgramField(value: unknown): value is ApiProgramField {
  if (typeof value !== 'object' || value === null) return false
  const field = value as Record<string, unknown>
  return typeof field.name === 'string' && typeof field.copy_to_clipboard === 'boolean'
}

function isApiProgram(value: unknown): value is ApiProgram {
  if (typeof value !== 'object' || value === null) return false
  const program = value as Record<string, unknown>
  return (
    typeof program.code === 'string' &&
    Array.isArray(program.fields) &&
    program.fields.every(isApiProgramField)
  )
}

/**
 * Fetch program/field metadata from the backend.
 *
 * Returns the program list on success, or `null` on ANY failure so callers
 * can silently keep the local mock config.
 */
export async function fetchProgramMetadata(): Promise<ApiProgram[] | null> {
  if (!API_BASE_URL) return null

  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), METADATA_TIMEOUT_MS)
  try {
    const response = await fetch(`${API_BASE_URL}/programs`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
    if (!response.ok) return null
    const body: unknown = await response.json()
    const programs = (body as { programs?: unknown } | null)?.programs
    if (!Array.isArray(programs) || !programs.every(isApiProgram)) return null
    return programs
  } catch {
    return null
  } finally {
    window.clearTimeout(timer)
  }
}
