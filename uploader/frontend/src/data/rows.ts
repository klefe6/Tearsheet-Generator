import type { ProductId, ProductRow } from '../types'

// Mock seed rows for each product, oldest → newest. Business days ending
// 2026-07-08. Eight rows apiece so the "last 7 rows" table demonstrates its
// rolling window out of the box (the oldest row sits just off-screen until a
// delete rolls it in). Values are illustrative only.
export const INITIAL_ROWS: Record<ProductId, ProductRow[]> = {
  TKP: [
    { id: 'tkp-1', date: '2026-06-29', stonexNlv: 248120, plus500Nlv: 58430, cash: 0 },
    { id: 'tkp-2', date: '2026-06-30', stonexNlv: 249540, plus500Nlv: 58910, cash: 0 },
    { id: 'tkp-3', date: '2026-07-01', stonexNlv: 250830, plus500Nlv: 59220, cash: 25000 },
    { id: 'tkp-4', date: '2026-07-02', stonexNlv: 252110, plus500Nlv: 59680, cash: 0 },
    { id: 'tkp-5', date: '2026-07-03', stonexNlv: 251470, plus500Nlv: 60110, cash: 0 },
    { id: 'tkp-6', date: '2026-07-06', stonexNlv: 253960, plus500Nlv: 60540, cash: 0 },
    { id: 'tkp-7', date: '2026-07-07', stonexNlv: 255380, plus500Nlv: 61020, cash: 0 },
    { id: 'tkp-8', date: '2026-07-08', stonexNlv: 256240, plus500Nlv: 61390, cash: 0 },
  ],
  TCP: [
    { id: 'tcp-1', date: '2026-06-29', stonexNlv: 496320, cash: 0 },
    { id: 'tcp-2', date: '2026-06-30', stonexNlv: 498780, cash: 0 },
    { id: 'tcp-3', date: '2026-07-01', stonexNlv: 501240, cash: 0 },
    { id: 'tcp-4', date: '2026-07-02', stonexNlv: 503910, cash: 50000 },
    { id: 'tcp-5', date: '2026-07-03', stonexNlv: 505470, cash: 0 },
    { id: 'tcp-6', date: '2026-07-06', stonexNlv: 508020, cash: 0 },
    { id: 'tcp-7', date: '2026-07-07', stonexNlv: 510640, cash: 0 },
    { id: 'tcp-8', date: '2026-07-08', stonexNlv: 512180, cash: 0 },
  ],
  AGM: [
    { id: 'agm-1', date: '2026-06-29', tradestationNlv: 31240, cash: 0, fee: 0 },
    { id: 'agm-2', date: '2026-06-30', tradestationNlv: 31480, cash: 0, fee: 0 },
    { id: 'agm-3', date: '2026-07-01', tradestationNlv: 31710, cash: 0, fee: 0 },
    { id: 'agm-4', date: '2026-07-02', tradestationNlv: 31950, cash: 0, fee: 320 },
    { id: 'agm-5', date: '2026-07-03', tradestationNlv: 32090, cash: 0, fee: 0 },
    { id: 'agm-6', date: '2026-07-06', tradestationNlv: 32360, cash: 0, fee: 0 },
    { id: 'agm-7', date: '2026-07-07', tradestationNlv: 32580, cash: 0, fee: 0 },
    { id: 'agm-8', date: '2026-07-08', tradestationNlv: 32740, cash: 0, fee: 0 },
  ],
  YQ: [
    { id: 'yq-1', date: '2026-06-29', stonexNlv: 176420, cash: 0 },
    { id: 'yq-2', date: '2026-06-30', stonexNlv: 177310, cash: 0 },
    { id: 'yq-3', date: '2026-07-01', stonexNlv: 178050, cash: 0 },
    { id: 'yq-4', date: '2026-07-02', stonexNlv: 179240, cash: 10000 },
    { id: 'yq-5', date: '2026-07-03', stonexNlv: 178890, cash: 0 },
    { id: 'yq-6', date: '2026-07-06', stonexNlv: 180470, cash: 0 },
    { id: 'yq-7', date: '2026-07-07', stonexNlv: 181630, cash: 0 },
    { id: 'yq-8', date: '2026-07-08', stonexNlv: 182410, cash: 0 },
  ],
}

let rowCounter = 0
/** Client-only unique id for a newly entered row. */
export function makeRowId(productId: ProductId): string {
  rowCounter += 1
  return `${productId.toLowerCase()}-new-${rowCounter}`
}
