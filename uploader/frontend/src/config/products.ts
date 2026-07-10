import type { ProductConfig } from '../types'

/** Max entry fields across products — used to align action buttons across cards. */
export const MAX_PRODUCT_FIELD_COUNT = 4

// The four products, each config-driven so one <ProductCard> renders all of them.
// Field rules are the source of truth for the entry forms AND the tables:
//   TKP  — the only product with BOTH StoneX NLV and Plus500 NLV.
//   AGM  — the only product with a Fee.
//   TCP, Y&Q — StoneX NLV + Cash Transfer only.
// Input tints: NLV fields on TKP/TCP/AGM = translucent purple; every other
// non-date field (cash transfers, AGM fee, all Y&Q currency fields) = light
// translucent pink. Date inputs stay white. `accountNumber` renders a
// copy-to-clipboard chip beside the label (only the four broker NLV accounts).
export const PRODUCTS: ProductConfig[] = [
  {
    id: 'TKP',
    code: 'TKP',
    account: 'StoneX · Plus500',
    color: '#2a78d6', // blue
    colorSoft: '#eaf1fb',
    fields: [
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'stonexNlv', label: 'StoneX NLV', type: 'currency', placeholder: '0.00', tint: 'purple', accountNumber: '69060709' },
      { key: 'plus500Nlv', label: 'Plus500 NLV', type: 'currency', placeholder: '0.00', tint: 'purple', accountNumber: '50110102' },
      { key: 'cash', label: 'Cash Transfer', type: 'currency', placeholder: '0.00', tint: 'pink' },
    ],
    columns: [
      { key: 'date', label: 'Date', format: 'date' },
      { key: 'stonexNlv', label: 'StoneX NLV', format: 'currency' },
      { key: 'plus500Nlv', label: 'Plus500 NLV', format: 'currency' },
      { key: 'cash', label: 'Cash', format: 'currency' },
    ],
  },
  {
    id: 'TCP',
    code: 'TCP',
    account: 'StoneX',
    color: '#12a150', // green
    colorSoft: '#e7f6ee',
    fields: [
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'stonexNlv', label: 'StoneX NLV', type: 'currency', placeholder: '0.00', tint: 'purple', accountNumber: '69060795' },
      { key: 'cash', label: 'Cash Transfer', type: 'currency', placeholder: '0.00', tint: 'pink' },
    ],
    columns: [
      { key: 'date', label: 'Date', format: 'date' },
      { key: 'stonexNlv', label: 'StoneX NLV', format: 'currency' },
      { key: 'cash', label: 'Cash', format: 'currency' },
    ],
  },
  {
    id: 'AGM',
    code: 'AGM',
    account: 'TradeStation',
    color: '#7c3aed', // purple
    colorSoft: '#f1ecfd',
    fields: [
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'tradestationNlv', label: 'TradeStation NLV', type: 'currency', placeholder: '0.00', tint: 'purple', accountNumber: '210TGG51' },
      { key: 'cash', label: 'Cash Transfer', type: 'currency', placeholder: '0.00', tint: 'pink' },
      { key: 'fee', label: 'Fee', type: 'currency', placeholder: '0.00', tint: 'pink' },
    ],
    columns: [
      { key: 'date', label: 'Date', format: 'date' },
      { key: 'tradestationNlv', label: 'TradeStation NLV', format: 'currency' },
      { key: 'cash', label: 'Cash', format: 'currency' },
      { key: 'fee', label: 'Fee', format: 'currency' },
    ],
  },
  {
    id: 'YQ',
    code: 'Y&Q',
    account: 'StoneX',
    color: '#e0a000', // orange / gold
    colorSoft: '#fbf1d9',
    fields: [
      { key: 'date', label: 'Date', type: 'date' },
      { key: 'stonexNlv', label: 'StoneX NLV', type: 'currency', placeholder: '0.00', tint: 'pink' },
      { key: 'cash', label: 'Cash Transfer', type: 'currency', placeholder: '0.00', tint: 'pink' },
    ],
    columns: [
      { key: 'date', label: 'Date', format: 'date' },
      { key: 'stonexNlv', label: 'StoneX NLV', format: 'currency' },
      { key: 'cash', label: 'Cash', format: 'currency' },
    ],
  },
]
