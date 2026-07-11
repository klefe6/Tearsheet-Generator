// Pure derivation of a truthful ExportUiState from the backend's
// POST /api/export/all response. Kept separate from App.tsx so the status
// logic (which drives the truthful Processing/Processed/Partial
// failure/Failed/Dry run/Exported-to-sandbox/Y&Q-skipped requirements) is
// easy to read and test in isolation.

import type { ApiDownstreamProgramResult, ApiExportResult } from '../api/client'
import type { ExportOverallStatus, ExportProgramStatus, ExportUiState } from '../types'

function firstReason(result: ApiDownstreamProgramResult): string | undefined {
  return result.date_results.find((d) => d.reason)?.reason
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

  const hasFailure = relevant.some((s) => s === 'failure' || s === 'partial_failure')
  const hasSuccess = relevant.some((s) => s === 'success')

  if (hasFailure && hasSuccess) return 'partial_failure'
  if (hasFailure) return 'failed'
  if (!hasSuccess) return 'saved' // nothing needed pushing (all no_rows/skipped)
  // Real rows accepted downstream: "pushed" for the live tearsheet ingest
  // target, "sandbox_success" for the local sandbox-file target.
  return targetEnv === 'production' ? 'pushed' : 'sandbox_success'
}

/** Build the next ExportUiState from a successful POST /api/export/all response. */
export function deriveExportState(data: ApiExportResult, exportedAt: Date): ExportUiState {
  if (!data.downstream) {
    // Downstream export isn't enabled on this backend — this is the
    // original uploader-only preview. Always truthfully "saved", never
    // "exported to sandbox" (nothing downstream was attempted).
    return {
      lastExportAt: exportedAt,
      overallStatus: 'saved',
      canUndo: true,
      rowCount: data.total_rows,
      programStatuses: [],
      eligibleCount: data.total_rows,
      dryRun: data.dry_run,
    }
  }

  const { target_env: targetEnv, dry_run: dryRun, results } = data.downstream
  const programStatuses: ExportProgramStatus[] = Object.entries(results).map(([program, r]) => ({
    program,
    status: r.status,
    reason: firstReason(r),
  }))

  const dryRunHadFailure = Object.entries(results).some(
    ([program, r]) =>
      program !== 'YQ' && (r.status === 'failure' || r.status === 'partial_failure'),
  )
  const overallStatus: ExportOverallStatus = dryRun
    ? dryRunHadFailure
      ? 'partial_failure'
      : targetEnv === 'production'
        ? 'downstream_dry_run'
        : 'dry_run'
    : overallDownstreamStatus(targetEnv, results)

  return {
    lastExportAt: exportedAt,
    overallStatus,
    canUndo: true,
    rowCount: data.total_rows,
    programStatuses,
    targetEnv,
    eligibleCount: data.total_rows,
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
  if (!data.downstream) {
    return `${data.message} (${data.total_rows} row${data.total_rows === 1 ? '' : 's'} in this batch, ${appEnv}).`
  }

  const { target_env: targetEnv, dry_run: dryRun, results } = data.downstream
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
