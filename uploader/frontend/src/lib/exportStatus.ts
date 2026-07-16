// Pure derivation of a truthful ExportUiState from the backend's
// POST /api/export/all response. Kept separate from App.tsx so the status
// logic (which drives the truthful Processing/Processed/Partial
// failure/Failed/Dry run/Exported-to-sandbox/Y&Q-skipped requirements) is
// easy to read and test in isolation.

import type { ApiDownstreamProgramResult, ApiExportResult } from '../api/client'
import type { ExportOverallStatus, ExportProgramStatus, ExportUiState } from '../types'

/** Authoritative dry-run flag — prefers real_writes_enabled over legacy dry_run. */
function resolvesDryRun(data: ApiExportResult): boolean {
  if (typeof data.real_writes_enabled === 'boolean') {
    return !data.real_writes_enabled
  }
  if (data.downstream) {
    return data.downstream.dry_run
  }
  return data.dry_run
}

function firstReason(result: ApiDownstreamProgramResult): string | undefined {
  return result.date_results.find((d) => d.reason)?.reason
}

function programVerification(
  result: ApiDownstreamProgramResult,
): 'verified' | 'pending_refresh' | 'not_confirmed' | undefined {
  const tags = result.date_results
    .map((d) => d.verification)
    .filter((v): v is NonNullable<typeof v> => Boolean(v))
  if (tags.length === 0) return undefined
  if (tags.some((v) => v === 'not_confirmed')) return 'not_confirmed'
  if (tags.some((v) => v === 'pending_refresh')) return 'pending_refresh'
  return 'verified'
}

/** Overall status across TKP/TCP/AGM only — Y&Q is always excluded from this
 *  rollup since it's never a real export target (only ever "skipped"). */
function overallDownstreamStatus(
  targetEnv: string,
  results: Record<string, ApiDownstreamProgramResult>,
): ExportOverallStatus {
  const relevant = Object.entries(results)
    .filter(([program]) => program !== 'YQ')
    .map(([, r]) => r.status)

  const hasPartial = relevant.some((s) => s === 'partial_failure')
  const hasFailure = relevant.some((s) => s === 'failure' || s === 'partial_failure')
  const hasPendingRefresh = relevant.some((s) => s === 'pending_refresh')
  const hasSuccess = relevant.some((s) => s === 'success')
  const onlyIdle = relevant.every((s) => s === 'no_rows' || s === 'skipped')

  // Program-level partial_failure means some dates succeeded — never green.
  if (hasPartial || (hasFailure && hasSuccess)) return 'partial_failure'
  if (hasFailure) return 'failed'
  if (onlyIdle || (!hasSuccess && !hasPendingRefresh)) return 'no_eligible'
  if (hasPendingRefresh && !hasSuccess) return 'pushed_pending_refresh'
  if (hasPendingRefresh && hasSuccess) return 'pushed_pending_refresh'
  // Real rows accepted downstream: "pushed" for the live tearsheet ingest
  // target, "sandbox_success" for the local sandbox-file target.
  return targetEnv === 'production' ? 'pushed' : 'sandbox_success'
}

/** Build the next ExportUiState from a successful POST /api/export/all response. */
export function deriveExportState(data: ApiExportResult, exportedAt: Date): ExportUiState {
  const eligibleCount =
    typeof data.eligible_count === 'number' ? data.eligible_count : data.total_rows
  const excludedCount = data.excluded_count
  const exportedCount = data.exported_count

  if (!data.downstream) {
    // Downstream export isn't enabled on this backend — this is the
    // original uploader-only preview. Always truthfully "saved", never
    // "exported to sandbox" (nothing downstream was attempted).
    return {
      lastExportAt: exportedAt,
      overallStatus: eligibleCount === 0 ? 'no_eligible' : 'saved',
      canUndo: true,
      rowCount: data.total_rows,
      programStatuses: [],
      eligibleCount,
      excludedCount,
      exportedCount,
      dryRun: resolvesDryRun(data),
    }
  }

  const { target_env: targetEnv, results } = data.downstream
  const dryRun = resolvesDryRun(data)
  const programStatuses: ExportProgramStatus[] = Object.entries(results).map(([program, r]) => ({
    program,
    status: r.status,
    reason: firstReason(r),
    verification: programVerification(r),
  }))

  const dryRunHadFailure = Object.entries(results).some(
    ([program, r]) =>
      program !== 'YQ' && (r.status === 'failure' || r.status === 'partial_failure'),
  )
  let overallStatus: ExportOverallStatus = dryRun
    ? dryRunHadFailure
      ? 'partial_failure'
      : targetEnv === 'production'
        ? 'downstream_dry_run'
        : 'dry_run'
    : overallDownstreamStatus(targetEnv, results)

  // Zero eligible rows with no failures → neutral, never a green success check.
  if (
    eligibleCount === 0 &&
    (overallStatus === 'saved' || overallStatus === 'no_eligible' || overallStatus === 'pushed')
  ) {
    overallStatus = 'no_eligible'
  }

  return {
    lastExportAt: exportedAt,
    overallStatus,
    canUndo: true,
    rowCount: data.total_rows,
    programStatuses,
    targetEnv,
    eligibleCount,
    excludedCount,
    exportedCount,
    dryRun,
  }
}

/**
 * Toast text for a successful POST /api/export/all. The backend's own
 * `message` field describes ONLY the original uploader-only preview layer —
 * when downstream export also ran, that message alone would contradict the
 * badge (e.g. it always says "DRY RUN" whenever the uploader-only
 * EXPORT_ENABLED flag is off, even if downstream export just ran for real).
 * Build a toast that's consistent with whatever badge is about to show.
 */
export function exportToastMessage(data: ApiExportResult, appEnv: string): string {
  if (data.message && data.export_mode === 'live') {
    return data.message
  }

  if (!data.downstream) {
    return `${data.message} (${data.total_rows} row${data.total_rows === 1 ? '' : 's'} in this batch, ${appEnv}).`
  }

  const { target_env: targetEnv, results } = data.downstream
  const dryRun = resolvesDryRun(data)
  if (dryRun && targetEnv === 'production') {
    const summary = Object.entries(results)
      .map(([program, r]) => `${program} ${r.status}`)
      .join(', ')
    return (
      `Downstream DRY-RUN validated by the tearsheet apps (no data changed): ${summary}. ` +
      `${data.total_rows} row${data.total_rows === 1 ? '' : 's'} in this batch, ${appEnv}.`
    )
  }
  if (dryRun) {
    return (
      `Downstream export computed but not written (EXPORT_DRY_RUN) — target: ${targetEnv}. ` +
      `${data.total_rows} row${data.total_rows === 1 ? '' : 's'} in this batch, ${appEnv}.`
    )
  }

  const summary = Object.entries(results)
    .map(([program, r]) => `${program} ${r.status}`)
    .join(', ')
  return `Downstream export to ${targetEnv}: ${summary}.`
}

/** Icon kind for an overall export badge. Partial/total failure never use check. */
export function exportStatusIcon(
  status: ExportOverallStatus,
): 'check' | 'warn' | 'fail' | null {
  switch (status) {
    case 'partial_failure':
      return 'warn'
    case 'failed':
      return 'fail'
    case 'saved':
    case 'sandbox_success':
    case 'pushed':
    case 'downstream_dry_run':
      return 'check'
    case 'pushed_pending_refresh':
      return 'warn'
    default:
      return null
  }
}

/** State for the purely-local fallback (backend unreachable) — unchanged
 *  behavior from before downstream export existed, just relabeled truthfully. */
export function offlineMockExportState(rowCount: number, exportedAt: Date): ExportUiState {
  return {
    lastExportAt: exportedAt,
    overallStatus: 'offline_mock',
    canUndo: true,
    rowCount,
    programStatuses: [],
  }
}
