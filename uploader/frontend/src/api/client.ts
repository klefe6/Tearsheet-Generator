// Backend API client for the uploader backend ONLY (PR #23's FastAPI service).
//
// Two call styles:
//  - Read-only GETs (fetchProgramMetadata, fetchPerformance, fetchProgramRows)
//    are best-effort: ANY failure (backend down, CORS, timeout, bad shape)
//    resolves to `null` so callers keep rendering local mock data — local
//    preview never requires a running backend.
//  - Mutations (postRow, deleteLastRow, postExportAll) return a discriminated
//    MutationOutcome so callers can tell "backend unreachable" (fall back to
//    local-only mock behavior, same as before this wiring existed) apart from
//    "backend reachable but rejected the request" (a real error to surface,
//    never silently swallowed as success).
//
// This build never calls anything other than this backend. In particular
// `postExportAll` only ever hits the backend's own dry-run-safe
// `POST /api/export/all` — that endpoint's own code guarantees it never calls
// the four downstream TKP/TCP/AGM/Y&Q websites; nothing here adds, enables,
// or bypasses that.

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

/** One stored row as served by GET /api/rows/{program} (snake_case field names). */
export interface ApiRow {
  program: string
  date: string
  exported: boolean
  created_at: string | null
  updated_at: string | null
  [fieldName: string]: string | number | boolean | null
}

/** One display row as served by GET /api/display-rows/{program} — the bottom
 *  tables' data source. Unlike /api/rows (manual daily_rows only, export
 *  semantics), display rows merge in backfilled history, labeled per row.
 *  `value` is the same program value the performance graph uses. */
export interface ApiDisplayRow {
  date: string
  value: number | null
  row_source: string
  source_label: 'Manual' | 'Backfilled'
  source_detail?: string
  fee?: number | null
  [fieldName: string]: string | number | boolean | null | undefined
}

export interface ApiDisplayRowsResponse {
  program: string
  label: string
  count: number
  rows: ApiDisplayRow[]
  display_note: string
  export_note: string
  /** Only for Y&Q with no rows: "No daily Y&Q source available." */
  empty_reason?: string
}

/** One {x,y} point in a GET /api/performance series. */
export interface ApiPerformancePoint {
  x: number | string
  y: number
}

export interface ApiPerformanceSeriesMeta {
  key: string
  label: string
  kind: 'program' | 'benchmark'
  point_count: number
}

export interface ApiPerformanceResponse {
  mode: 'combined' | 'program'
  x_axis: 'trading_day' | 'date'
  base_value: number
  program: string | null
  benchmarks: string[]
  series: ApiPerformanceSeriesMeta[]
  points: Record<string, ApiPerformancePoint[]>
  last_updated_at: string
  warnings: string[]
  /** Always `uploader_daily_rows` when served by the backend. */
  program_data_source?: string
  /** `deterministic_fixture` | `market_cache_live_fetch` | `market_cache_cached` | `unavailable` */
  benchmark_data_source?: string | null
  /** e.g. `prior_close_within_5_calendar_days` when benchmarks are aligned. */
  benchmark_align_policy?: string | null
}

/** One program's downstream export outcome (present only when the backend's
 *  EXPORT_DOWNSTREAM_ENABLED flag is on). See docs/downstream_export_contract.md. */
export interface ApiDownstreamProgramResult {
  status: 'success' | 'failure' | 'skipped' | 'dry_run' | 'no_rows' | 'partial_failure'
  date_results: Array<{
    date: string
    status: 'success' | 'failure' | 'skipped' | 'dry_run'
    reason?: string
    payload_hash?: string
    downstream_response?: unknown
  }>
}

export interface ApiDownstreamResult {
  target_env: string
  dry_run: boolean
  results: Record<string, ApiDownstreamProgramResult>
}

export interface ApiExportResult {
  dry_run: boolean
  app_env: string
  export_enabled: boolean
  transport_implemented: boolean
  external_calls_made: number
  batch_id: number
  total_rows: number
  programs: Record<string, { target_url: string | null; row_count: number; rows: ApiRow[] }>
  message: string
  /** Present only when the backend attempted downstream TKP/TCP/AGM export. */
  downstream?: ApiDownstreamResult
}

const RAW_BASE: string = import.meta.env.VITE_API_BASE_URL || ''

/** Backend base URL (e.g. "https://uploader-sandbox.hcresearch.ltd/api"). */
export const API_BASE_URL = RAW_BASE.replace(/\/+$/, '')

/** Give read-only fetches a short leash so a dead backend never stalls the UI. */
const READ_TIMEOUT_MS = 4000
/** Mutations get a little more room (server does real validation/DB work). */
const MUTATION_TIMEOUT_MS = 6000

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
  const timer = window.setTimeout(() => controller.abort(), READ_TIMEOUT_MS)
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

/**
 * Fetch chart data for the performance card.
 *
 * `mode: 'combined'` ignores `program`/`benchmarks`. `mode: 'program'`
 * requires `program`; `benchmarks` (all three requested regardless of which
 * are currently toggled on — the frontend hides/shows lines client-side so
 * toggling doesn't need a round trip) are rebased server-side to that
 * program's own start date. Returns `null` on ANY failure so callers fall
 * back to local mock chart data.
 */
export async function fetchPerformance(
  mode: 'combined' | 'program',
  program?: string,
  benchmarks?: string[],
): Promise<ApiPerformanceResponse | null> {
  if (!API_BASE_URL) return null

  const params = new URLSearchParams({ mode })
  if (program) params.set('program', program)
  if (benchmarks && benchmarks.length > 0) params.set('benchmarks', benchmarks.join(','))

  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), READ_TIMEOUT_MS)
  try {
    const response = await fetch(`${API_BASE_URL}/performance?${params.toString()}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
    if (!response.ok) return null
    const body = (await response.json()) as unknown as Record<string, unknown>
    if (
      typeof body !== 'object' ||
      body === null ||
      (body.mode !== 'combined' && body.mode !== 'program') ||
      typeof body.points !== 'object' ||
      body.points === null
    ) {
      return null
    }
    return body as unknown as ApiPerformanceResponse
  } catch {
    return null
  } finally {
    window.clearTimeout(timer)
  }
}

/**
 * Fetch a program's most recent rows (best-effort, same graceful-fallback
 * pattern as fetchProgramMetadata — `null` on any failure).
 */
export async function fetchProgramRows(
  program: string,
  limit = 7,
): Promise<{ rows: ApiRow[] } | null> {
  if (!API_BASE_URL) return null

  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), READ_TIMEOUT_MS)
  try {
    const response = await fetch(
      `${API_BASE_URL}/rows/${encodeURIComponent(program)}?limit=${limit}`,
      { method: 'GET', headers: { Accept: 'application/json' }, signal: controller.signal },
    )
    if (!response.ok) return null
    const body = (await response.json()) as { rows?: unknown }
    if (!Array.isArray(body.rows)) return null
    return { rows: body.rows as ApiRow[] }
  } catch {
    return null
  } finally {
    window.clearTimeout(timer)
  }
}

/**
 * Fetch a program's latest merged display rows for the bottom tables
 * (manual + labeled backfilled history; best-effort, `null` on any failure
 * so callers fall back to local manual rows).
 */
export async function fetchDisplayRows(
  program: string,
  limit = 7,
): Promise<ApiDisplayRowsResponse | null> {
  if (!API_BASE_URL) return null

  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), READ_TIMEOUT_MS)
  try {
    const response = await fetch(
      `${API_BASE_URL}/display-rows/${encodeURIComponent(program)}?limit=${limit}`,
      { method: 'GET', headers: { Accept: 'application/json' }, signal: controller.signal },
    )
    if (!response.ok) return null
    const body = (await response.json()) as { rows?: unknown }
    if (!Array.isArray(body.rows)) return null
    return body as unknown as ApiDisplayRowsResponse
  } catch {
    return null
  } finally {
    window.clearTimeout(timer)
  }
}

/**
 * Outcome of a mutation call:
 *  - `ok: true`               — backend accepted it; `data` is the response body.
 *  - `ok: false, reason: 'network'`  — backend unreachable (down/CORS/timeout) —
 *    callers should fall back to the previous local-mock-only behavior.
 *  - `ok: false, reason: 'rejected'` — backend WAS reached but rejected the
 *    request (validation error, 404, auth) — callers should surface this,
 *    never silently treat it as success.
 */
export type MutationOutcome<T> =
  | { ok: true; data: T }
  | { ok: false; reason: 'network' }
  | { ok: false; reason: 'rejected'; status: number; detail: unknown }

async function callMutation<T>(
  path: string,
  method: 'POST' | 'DELETE',
  body?: unknown,
): Promise<MutationOutcome<T>> {
  if (!API_BASE_URL) return { ok: false, reason: 'network' }

  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), MUTATION_TIMEOUT_MS)
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers:
        body !== undefined
          ? { 'Content-Type': 'application/json', Accept: 'application/json' }
          : { Accept: 'application/json' },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
    if (response.ok) {
      const data = (await response.json()) as T
      return { ok: true, data }
    }
    let detail: unknown = null
    try {
      detail = await response.json()
    } catch {
      // no JSON body — leave detail null
    }
    return { ok: false, reason: 'rejected', status: response.status, detail }
  } catch {
    return { ok: false, reason: 'network' }
  } finally {
    window.clearTimeout(timer)
  }
}

/** POST /api/rows/{program} — create or update (upsert by date). No auth
 *  header is sent; the backend's sandbox mode allows unauthenticated
 *  mutations by design (see app/security.py). Production would need a token
 *  flow, which this build doesn't add. */
export function postRow(
  program: string,
  payload: Record<string, string | number>,
): Promise<MutationOutcome<{ program: string; created: boolean; action: string; row: ApiRow }>> {
  return callMutation(`/rows/${encodeURIComponent(program)}`, 'POST', payload)
}

/** DELETE /api/rows/{program}/last — delete the most recent row. */
export function deleteLastRow(
  program: string,
): Promise<MutationOutcome<{ program: string; deleted: ApiRow }>> {
  return callMutation(`/rows/${encodeURIComponent(program)}/last`, 'DELETE')
}

/** POST /api/export/all — the backend's own dry-run-safe export preview.
 *  This never calls the four TKP/TCP/AGM/Y&Q websites (guaranteed by the
 *  backend itself: `transport_implemented` is always false in this build). */
export function postExportAll(): Promise<MutationOutcome<ApiExportResult>> {
  return callMutation('/export/all', 'POST')
}
