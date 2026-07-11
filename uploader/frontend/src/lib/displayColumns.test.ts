import { describe, expect, it } from 'vitest'
import { PRODUCTS } from '../config/products'
import { displayColumnsFor } from './displayColumns'

const byId = new Map(PRODUCTS.map((p) => [p.id, p]))
const labels = (id: string) => displayColumnsFor(byId.get(id as never)!).map((c) => c.label)

describe('displayColumnsFor', () => {
  it('TKP is the only program with both StoneX and Plus500 NLV columns', () => {
    expect(labels('TKP')).toEqual(['Date', 'StoneX NLV', 'Plus500 NLV', 'Source'])
    for (const id of ['TCP', 'AGM', 'YQ']) {
      expect(labels(id)).not.toContain('Plus500 NLV')
      expect(labels(id)).not.toContain('StoneX NLV')
    }
  })

  it('AGM is the only program with a Fee column', () => {
    expect(labels('AGM')).toEqual(['Date', 'Value', 'Fee', 'Source'])
    for (const id of ['TKP', 'TCP', 'YQ']) {
      expect(labels(id)).not.toContain('Fee')
    }
  })

  it('TCP and YQ show the single graph-equivalent value', () => {
    expect(labels('TCP')).toEqual(['Date', 'Value', 'Source'])
    expect(labels('YQ')).toEqual(['Date', 'Value', 'Source'])
  })

  it('every table ends with the Source badge column', () => {
    for (const p of PRODUCTS) {
      const cols = displayColumnsFor(p)
      expect(cols[cols.length - 1].key).toBe('source')
    }
  })
})
