type AssetType = 'equity' | 'option' | 'index-option' | 'unsupported'
export type Kind = 'account' | 'simulated'
type ThresholdUnit = 'dollars' | 'percent'

export type LossThreshold = {
  unit: ThresholdUnit
  value: number
}

export type PositionRow = {
  id: string
  instrument: string
  assetType: AssetType
  quantity: number
  multiplier: number
  totalCost: number
  mark: number
  marketValue: number
  shockPnl: number
  underlying: string
  hypothetical?: boolean
  iv?: number
  delta?: number
  gamma?: number
  theta?: number
  vega?: number
}

export type UnderlyingGroup = {
  symbol: string
  name: string
  beta: number
  hv20: number
  hv30: number
  threshold?: LossThreshold
  worstShockPnl: number
  positions: PositionRow[]
}

export type PortfolioActions = {
  kind: Kind
  setKind: (kind: Kind) => void
  editing: boolean
  setEditing: (value: boolean) => void
  setCash: (value: number) => void
  sync: () => void
  reconnect: () => void
  expireToken: () => void
  addFromOcc: (text: string, quantity: number) => void
  addChainPosition: (input: {
    right: 'C' | 'P'
    strike: number
    expiry: string
    quantity: number
  }) => void
  setUnderlyingThreshold: (
    symbol: string,
    threshold: LossThreshold | undefined,
  ) => void
}

export type VariantProps = {
  portfolio: PortfolioView
  actions: PortfolioActions
}

export type PortfolioView = {
  kind: Kind
  name: string
  cash: number
  marginCushion?: number
  lastSyncedAt?: string
  dataAsOf?: string
  disconnected?: boolean
  portfolioThreshold?: LossThreshold
  worstScenario: {
    name: string
    shock: string
    pnl: number
  }
  groups: UnderlyingGroup[]
  unpriced: PositionRow[]
}

export function usd(n: number) {
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })
}

export function usd2(n: number) {
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function signedUsd(n: number) {
  const abs = usd2(Math.abs(n))
  if (n > 0) return `+${abs}`
  if (n < 0) return `−${abs}`
  return abs
}

export function pnlClass(n: number) {
  if (n > 0) return 'text-emerald-700'
  if (n < 0) return 'text-red-700'
  return 'text-muted-foreground'
}

export function positionPnl(position: PositionRow) {
  return position.marketValue - position.totalCost
}

export function groupMarketValue(group: UnderlyingGroup) {
  return group.positions.reduce((sum, position) => sum + position.marketValue, 0)
}

export function groupTotalCost(group: UnderlyingGroup) {
  return group.positions.reduce((sum, position) => sum + position.totalCost, 0)
}

export function groupPnl(group: UnderlyingGroup) {
  return groupMarketValue(group) - groupTotalCost(group)
}

export function netLiquidationValue(portfolio: PortfolioView) {
  const positions = [
    ...portfolio.groups.flatMap((group) => group.positions),
    ...portfolio.unpriced,
  ]
  return (
    portfolio.cash +
    positions.reduce((sum, position) => sum + position.marketValue, 0)
  )
}

export function thresholdDollars(threshold: LossThreshold, nlv: number) {
  return threshold.unit === 'percent' ? (nlv * threshold.value) / 100 : threshold.value
}

export function isBreach(pnl: number, threshold: LossThreshold | undefined, nlv: number) {
  if (!threshold || pnl >= 0) return false
  return -pnl > thresholdDollars(threshold, nlv)
}

function pos(
  row: Omit<PositionRow, 'marketValue' | 'shockPnl'> & {
    marketValue?: number
    shockPnl: number
  },
): PositionRow {
  return {
    ...row,
    marketValue: row.marketValue ?? row.mark * row.quantity * row.multiplier,
  }
}

export const CHAIN = {
  symbol: 'IREN',
  expiries: ['2026-01-16', '2026-02-20'],
  strikes: [30, 35, 40, 45, 50],
  marks: {
    C: { 30: 12.4, 35: 8.1, 40: 4.6, 45: 2.2, 50: 0.95 },
    P: { 30: 0.7, 35: 1.9, 40: 4.15, 45: 7.6, 50: 11.4 },
  } as Record<'C' | 'P', Record<number, number>>,
}

export function accountFixture(): PortfolioView {
  return {
    kind: 'account',
    name: 'Schwab IRA',
    cash: -6200,
    marginCushion: 36,
    lastSyncedAt: '2026-10-19T16:42:00.000Z',
    dataAsOf: '2026-10-19T16:42:00.000Z',
    disconnected: false,
    portfolioThreshold: { unit: 'percent', value: 12 },
    worstScenario: {
      name: 'Market shock',
      shock: 'SPY −15% · IV +20 pts · 0d',
      pnl: -9420,
    },
    groups: [
      {
        symbol: 'IREN',
        name: 'Iris Energy',
        beta: 3.42,
        hv20: 118,
        hv30: 96,
        threshold: { unit: 'dollars', value: 3000 },
        worstShockPnl: -4180,
        positions: [
          pos({
            id: 'iren-shares',
            instrument: 'IREN',
            assetType: 'equity',
            quantity: 200,
            multiplier: 1,
            totalCost: 6200,
            mark: 41.2,
            shockPnl: -5600,
            underlying: 'IREN',
          }),
          pos({
            id: 'iren-short-call',
            instrument: 'IREN 16 Jan 26 40 Call',
            assetType: 'option',
            quantity: -2,
            multiplier: 100,
            totalCost: -710,
            mark: 4.6,
            shockPnl: 620,
            underlying: 'IREN',
            iv: 102,
            delta: -0.54,
            gamma: 0.031,
            theta: -0.08,
            vega: 0.041,
          }),
          pos({
            id: 'iren-long-put',
            instrument: 'IREN 16 Jan 26 35 Put',
            assetType: 'option',
            quantity: 2,
            multiplier: 100,
            totalCost: 840,
            mark: 1.9,
            shockPnl: 800,
            underlying: 'IREN',
            iv: 98,
            delta: -0.22,
            gamma: 0.024,
            theta: -0.05,
            vega: 0.036,
          }),
        ],
      },
      {
        symbol: 'CIFR',
        name: 'Cipher Mining',
        beta: 2.88,
        hv20: 104,
        hv30: 91,
        worstShockPnl: -2610,
        positions: [
          pos({
            id: 'cifr-shares',
            instrument: 'CIFR',
            assetType: 'equity',
            quantity: 500,
            multiplier: 1,
            totalCost: 3100,
            mark: 8.14,
            shockPnl: -2610,
            underlying: 'CIFR',
          }),
        ],
      },
      {
        symbol: 'ASST',
        name: 'Asset Entities',
        beta: 1.95,
        hv20: 142,
        hv30: 121,
        worstShockPnl: -890,
        positions: [
          pos({
            id: 'asst-shares',
            instrument: 'ASST',
            assetType: 'equity',
            quantity: 1000,
            multiplier: 1,
            totalCost: 980,
            mark: 1.18,
            shockPnl: -890,
            underlying: 'ASST',
          }),
        ],
      },
      {
        symbol: 'SPY',
        name: 'SPDR S&P 500',
        beta: 1,
        hv20: 14,
        hv30: 16,
        worstShockPnl: -480,
        positions: [
          pos({
            id: 'spy-shares',
            instrument: 'SPY',
            assetType: 'equity',
            quantity: 5,
            multiplier: 1,
            totalCost: 2680,
            mark: 582.4,
            shockPnl: -480,
            underlying: 'SPY',
          }),
        ],
      },
      {
        symbol: 'SPX',
        name: 'S&P 500 Index',
        beta: 1,
        hv20: 15,
        hv30: 16,
        worstShockPnl: -1260,
        positions: [
          pos({
            id: 'spx-put',
            instrument: 'SPX 16 Jan 26 5600 Put',
            assetType: 'index-option',
            quantity: 1,
            multiplier: 100,
            totalCost: 2140,
            mark: 18.2,
            shockPnl: -1260,
            underlying: 'SPX',
            iv: 16.4,
            delta: -0.18,
            gamma: 0.001,
            theta: -0.42,
            vega: 0.62,
          }),
        ],
      },
    ],
    unpriced: [
      pos({
        id: 'swppx',
        instrument: 'SWPPX',
        assetType: 'unsupported',
        quantity: 42,
        multiplier: 1,
        totalCost: 3100,
        mark: 98.4,
        marketValue: 4132.8,
        shockPnl: 0,
        underlying: 'SWPPX',
      }),
    ],
  }
}

export function simulatedFixture(): PortfolioView {
  const copy = accountFixture()
  copy.kind = 'simulated'
  copy.name = 'IRA + IREN hedge'
  copy.lastSyncedAt = undefined
  copy.disconnected = false
  copy.groups[0]?.positions.push(
    pos({
      id: 'iren-hedge',
      instrument: 'IREN 20 Feb 26 30 Put',
      assetType: 'option',
      quantity: 5,
      multiplier: 100,
      totalCost: 1750,
      mark: 3.5,
      shockPnl: 1500,
      underlying: 'IREN',
      hypothetical: true,
      iv: 110,
      delta: -0.16,
      gamma: 0.018,
      theta: -0.04,
      vega: 0.044,
    }),
  )
  if (copy.groups[0]) copy.groups[0].worstShockPnl = -2680
  copy.worstScenario = {
    name: 'Market shock',
    shock: 'SPY −15% · IV +20 pts · 0d',
    pnl: -7920,
  }
  return copy
}

export function addFromOcc(
  portfolio: PortfolioView,
  instrument: string,
  quantity: number,
): PortfolioView {
  const next = structuredClone(portfolio)
  const group =
    next.groups.find((item) => instrument.toUpperCase().includes(item.symbol)) ??
    next.groups[0]
  if (!group) return next
  const mark = 2.2
  const marketValue = mark * quantity * 100
  const shockPnl = Math.round(marketValue * -0.35)
  group.worstShockPnl += shockPnl
  group.positions.push({
    id: `occ-${Date.now()}`,
    instrument,
    assetType: 'option',
    quantity,
    multiplier: 100,
    totalCost: marketValue,
    mark,
    marketValue,
    shockPnl,
    underlying: group.symbol,
    hypothetical: next.kind === 'simulated',
    iv: 100,
    delta: quantity < 0 ? -0.4 : 0.4,
    gamma: 0.03,
    theta: -0.06,
    vega: 0.04,
  })
  return next
}

export function addFromChain(
  portfolio: PortfolioView,
  input: { right: 'C' | 'P'; strike: number; expiry: string; quantity: number },
): PortfolioView {
  const mark = CHAIN.marks[input.right][input.strike] ?? 1
  const marketValue = mark * input.quantity * 100
  const shockPnl = Math.round(marketValue * -0.35)
  const expiry = new Date(`${input.expiry}T00:00:00`)
  const expiryLabel = expiry.toLocaleDateString('en-US', {
    day: 'numeric',
    month: 'short',
    year: '2-digit',
  })
  const right = input.right === 'C' ? 'Call' : 'Put'
  const next = structuredClone(portfolio)
  const group = next.groups.find((item) => item.symbol === 'IREN')
  if (!group) return next
  group.worstShockPnl += shockPnl
  group.positions.push(
    pos({
      id: `new-${Date.now()}`,
      instrument: `IREN ${expiryLabel} ${input.strike} ${right}`,
      assetType: 'option',
      quantity: input.quantity,
      multiplier: 100,
      totalCost: marketValue,
      mark,
      shockPnl,
      underlying: 'IREN',
      hypothetical: next.kind === 'simulated',
      iv: 100,
      delta: input.right === 'C' ? 0.5 : -0.5,
      gamma: 0.03,
      theta: -0.06,
      vega: 0.04,
    }),
  )
  return next
}
