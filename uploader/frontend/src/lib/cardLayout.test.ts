import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const here = dirname(fileURLToPath(import.meta.url))
const readCss = (rel: string) => readFileSync(join(here, rel), 'utf8')

describe('desktop card layout CSS', () => {
  const appCss = readCss('../App.module.css')
  const cardCss = readCss('../components/ProductCard.module.css')

  it('uses a near-full-width page container with four equal desktop columns', () => {
    expect(appCss).toMatch(/max-width:\s*min\(100%,\s*1880px\)/)
    expect(appCss).toMatch(/grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/)
    expect(appCss).not.toMatch(/max-width:\s*1440px/)
  })

  it('keeps tablet two-column and mobile one-column breakpoints', () => {
    expect(appCss).toMatch(
      /@media \(max-width: 1200px\)[\s\S]*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    )
    expect(appCss).toMatch(/@media \(max-width: 720px\)[\s\S]*minmax\(0,\s*1fr\)/)
  })

  it('avoids horizontal table scroll on desktop while preserving nowrap NLV values', () => {
    expect(cardCss).toMatch(/\.tableWrap\s*\{[\s\S]*overflow-x:\s*visible/)
    expect(cardCss).toMatch(/\.table td\.num\s*\{[\s\S]*white-space:\s*nowrap/)
    expect(cardCss).toMatch(/@media \(max-width: 1200px\)[\s\S]*overflow-x:\s*auto/)
  })

  it('allows source and status badges to wrap inside cells', () => {
    expect(cardCss).toMatch(/\.srcBadge\s*\{[\s\S]*white-space:\s*normal/)
    expect(cardCss).toMatch(/\.historicalBadge\s*\{[\s\S]*white-space:\s*normal/)
    expect(cardCss).toMatch(/\.exportedBadge\s*\{[\s\S]*white-space:\s*normal/)
  })
})
