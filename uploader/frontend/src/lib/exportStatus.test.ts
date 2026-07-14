import { describe, expect, it } from 'vitest'
import type { ApiExportResult } from '../api/client'
import { deriveExportState } from './exportStatus'

const exportedAt = new Date('2026-07-11T20:00:00Z')

function downstreamResult(
  overrides: Partial<ApiExportResult> & { downstream: NonNullable<ApiExportResult['downstream']> },
): ApiExportResult {
  return {
    dry_run: true,
    app_env: 'sandbox',
    export_enabled: false,
    transport_implemented: true,
    external_calls_made: 0,
    batch_id: 1,
    total_rows: 0,
    programs: {},
    message: 'test',
    ...overrides,
  }
}

describe('deriveExportState', () => {
  it('reports saved when downstream is not enabled', () => {
    const state = deriveExportState(
      {
        dry_run: true,
        app_env: 'sandbox',
        export_enabled: false,
        transport_implemented: false,
        external_calls_made: 0,
        batch_id: 1,
        total_rows: 2,
        programs: {},
        message: 'preview',
      },
      exportedAt,
    )
    expect(state.overallStatus).toBe('saved')
  })

  it('reports dry_run when downstream dry_run is true', () => {
    const state = deriveExportState(
      downstreamResult({
        total_rows: 3,
        downstream: {
          target_env: 'production',
          dry_run: true,
          results: {
            TKP: { status: 'dry_run', date_results: [] },
            TCP: { status: 'dry_run', date_results: [] },
            AGM: { status: 'dry_run', date_results: [] },
            YQ: { status: 'skipped', date_results: [{ date: '', status: 'skipped', reason: 'destination not configured' }] },
          },
        },
      }),
      exportedAt,
    )
    expect(state.overallStatus).toBe('dry_run')
  })

  it('reports live_success for production push with successes', () => {
    const state = deriveExportState(
      downstreamResult({
        total_rows: 3,
        external_calls_made: 3,
        downstream: {
          target_env: 'production',
          dry_run: false,
          results: {
            TKP: { status: 'success', date_results: [{ date: '2026-07-11', status: 'success' }] },
            TCP: { status: 'success', date_results: [{ date: '2026-07-11', status: 'success' }] },
            AGM: { status: 'success', date_results: [{ date: '2026-07-11', status: 'success' }] },
            YQ: { status: 'skipped', date_results: [{ date: '', status: 'skipped', reason: 'destination not configured' }] },
          },
        },
      }),
      exportedAt,
    )
    expect(state.overallStatus).toBe('live_success')
  })

  it('reports sandbox_success for sandbox push with successes', () => {
    const state = deriveExportState(
      downstreamResult({
        total_rows: 1,
        downstream: {
          target_env: 'sandbox',
          dry_run: false,
          results: {
            TKP: { status: 'success', date_results: [{ date: '2026-07-11', status: 'success' }] },
            TCP: { status: 'no_rows', date_results: [] },
            AGM: { status: 'no_rows', date_results: [] },
            YQ: { status: 'skipped', date_results: [] },
          },
        },
      }),
      exportedAt,
    )
    expect(state.overallStatus).toBe('sandbox_success')
  })

  it('reports no_rows when everything is already exported', () => {
    const state = deriveExportState(
      downstreamResult({
        total_rows: 0,
        downstream: {
          target_env: 'production',
          dry_run: false,
          results: {
            TKP: { status: 'no_rows', date_results: [] },
            TCP: { status: 'no_rows', date_results: [] },
            AGM: { status: 'no_rows', date_results: [] },
            YQ: { status: 'skipped', date_results: [] },
          },
        },
      }),
      exportedAt,
    )
    expect(state.overallStatus).toBe('no_rows')
  })

  it('reports partial_failure when some programs fail', () => {
    const state = deriveExportState(
      downstreamResult({
        total_rows: 2,
        downstream: {
          target_env: 'production',
          dry_run: false,
          results: {
            TKP: { status: 'success', date_results: [{ date: '2026-07-11', status: 'success' }] },
            TCP: { status: 'failure', date_results: [{ date: '2026-07-11', status: 'failure', reason: 'timeout' }] },
            AGM: { status: 'no_rows', date_results: [] },
            YQ: { status: 'skipped', date_results: [] },
          },
        },
      }),
      exportedAt,
    )
    expect(state.overallStatus).toBe('partial_failure')
  })

  it('reports failed when every non-skipped program fails', () => {
    const state = deriveExportState(
      downstreamResult({
        total_rows: 2,
        downstream: {
          target_env: 'production',
          dry_run: false,
          results: {
            TKP: { status: 'failure', date_results: [] },
            TCP: { status: 'failure', date_results: [] },
            AGM: { status: 'failure', date_results: [] },
            YQ: { status: 'skipped', date_results: [] },
          },
        },
      }),
      exportedAt,
    )
    expect(state.overallStatus).toBe('failed')
  })
})
