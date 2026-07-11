import { describe, expect, it } from 'vitest'
import type { ApiExportResult } from '../api/client'
import { deriveExportState, exportToastMessage } from './exportStatus'

const NOW = new Date('2026-07-10T12:00:00Z')

function result(overrides: Partial<ApiExportResult>): ApiExportResult {
  return {
    dry_run: true,
    app_env: 'sandbox',
    export_enabled: false,
    transport_implemented: false,
    external_calls_made: 0,
    batch_id: 1,
    total_rows: 1,
    programs: {},
    message: 'DRY RUN',
    ...overrides,
  } as ApiExportResult
}

function downstream(targetEnv: string, dryRun: boolean, statuses: Record<string, string>) {
  return {
    target_env: targetEnv,
    dry_run: dryRun,
    results: Object.fromEntries(
      Object.entries(statuses).map(([program, status]) => [
        program,
        { status, date_results: [] },
      ]),
    ),
  } as ApiExportResult['downstream']
}

describe('deriveExportState — downstream push statuses', () => {
  it('backend-only save stays "saved" (downstream disabled)', () => {
    expect(deriveExportState(result({}), NOW).overallStatus).toBe('saved')
  })

  it('production dry-run that validates downstream is "downstream_dry_run"', () => {
    const data = result({
      downstream: downstream('production', true, {
        TKP: 'dry_run', TCP: 'dry_run', AGM: 'dry_run', YQ: 'skipped',
      }),
    })
    expect(deriveExportState(data, NOW).overallStatus).toBe('downstream_dry_run')
  })

  it('sandbox-target dry-run keeps the original "dry_run" badge', () => {
    const data = result({
      downstream: downstream('sandbox', true, { TKP: 'dry_run', YQ: 'skipped' }),
    })
    expect(deriveExportState(data, NOW).overallStatus).toBe('dry_run')
  })

  it('real production push with all success is "pushed"', () => {
    const data = result({
      dry_run: false,
      downstream: downstream('production', false, {
        TKP: 'success', TCP: 'success', AGM: 'success', YQ: 'skipped',
      }),
    })
    expect(deriveExportState(data, NOW).overallStatus).toBe('pushed')
  })

  it('real production push with a failure is failed/partial', () => {
    const failed = result({
      dry_run: false,
      downstream: downstream('production', false, { TKP: 'failure', YQ: 'skipped' }),
    })
    expect(deriveExportState(failed, NOW).overallStatus).toBe('failed')

    const partial = result({
      dry_run: false,
      downstream: downstream('production', false, {
        TKP: 'success', TCP: 'failure', YQ: 'skipped',
      }),
    })
    expect(deriveExportState(partial, NOW).overallStatus).toBe('partial_failure')
  })

  it('dry-run with a config failure surfaces as partial_failure, not a green badge', () => {
    const data = result({
      downstream: downstream('production', true, {
        TKP: 'failure', TCP: 'dry_run', YQ: 'skipped',
      }),
    })
    expect(deriveExportState(data, NOW).overallStatus).toBe('partial_failure')
  })
})

describe('exportToastMessage — downstream push wording', () => {
  it('production dry-run toast says validated with no data changed', () => {
    const data = result({
      downstream: downstream('production', true, { TKP: 'dry_run', YQ: 'skipped' }),
    })
    const msg = exportToastMessage(data, 'sandbox')
    expect(msg).toMatch(/DRY-RUN validated by the tearsheet apps/)
    expect(msg).toMatch(/no data changed/)
  })

  it('real push toast lists per-program outcomes', () => {
    const data = result({
      dry_run: false,
      downstream: downstream('production', false, { TKP: 'success', YQ: 'skipped' }),
    })
    expect(exportToastMessage(data, 'sandbox')).toMatch(
      /Downstream export to production: TKP success, YQ skipped/,
    )
  })
})
