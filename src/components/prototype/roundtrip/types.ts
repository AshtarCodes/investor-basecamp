// PROTOTYPE (throwaway). Shapes of an engine run (scenarios/iren/analysis/roundtrip_run.py) and of the page's state.

export type EngineEvent = {
  date: string
  type: 'action' | 'debt' | 'expiry'
  action?: 'sell_cash' | 'sell_shares'
  pct?: number // the Action's percent, or the debt share
  contracts?: number // how many contracts were sold
  sleeve?: string // the expiry sale's Sleeve key
  amount: number
}

export type Run = {
  total: number // final wealth plus debt paid
  wealth: number
  debt: number
  end: string
  events: EngineEvent[]
  dates: string[] // entry, then every date the run values
  spot: number[]
  legs: Record<string, number[]> // stock, <sleeve keys s0, s1, ...>, cash, debt, total: dollars after each date's trades
  unit: Record<string, (number | null)[]> // return on one share or contract against its entry cost, as if held
  contrib: Record<string, number> // dollars each leg added: proceeds + final holdings - cost
}

export type YMode = 'usd' | 'pct'
export type VariantKey = 'A' | 'B' | 'C'

export type PageState = {
  variant: VariantKey
  build: string
  path: string // a path id, or 'unsaved'
  debt: string
  y: YMode
  hidden: string[] // leg ids hidden on the chart
  vs: string // the build Compare puts beside the focused one
}
