import { useEffect, useMemo, useState } from 'react'
import { BookOpen, PanelLeft } from 'lucide-react'

import { Badge } from '#/components/ui/badge.tsx'
import { Button } from '#/components/ui/button.tsx'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '#/components/ui/dialog.tsx'
import { Input } from '#/components/ui/input.tsx'
import { Separator } from '#/components/ui/separator.tsx'

import {
  CHAIN,
  groupMarketValue,
  groupPnl,
  groupTotalCost,
  isBreach,
  netLiquidationValue,
  pnlClass,
  signedUsd,
  thresholdDollars,
  usd,
  usd2,
  type UnderlyingGroup,
  type VariantProps,
} from './fixture.ts'

export const variantCName = 'Inspector'

export function VariantC({ portfolio, actions }: VariantProps) {
  const nlv = netLiquidationValue(portfolio)
  const [selected, setSelected] = useState(portfolio.groups[0]?.symbol ?? 'IREN')
  const [palette, setPalette] = useState(false)
  const [showGreeks, setShowGreeks] = useState(false)
  const [showShock, setShowShock] = useState(false)
  const [legendOpen, setLegendOpen] = useState(false)
  const [railOpen, setRailOpen] = useState(false)
  const callLevel =
    portfolio.cash < 0 && portfolio.marginCushion != null
      ? nlv * (1 - portfolio.marginCushion / 100)
      : undefined
  const shockedNlv = nlv + portfolio.worstScenario.pnl
  const shockMarginCall = callLevel != null && shockedNlv <= callLevel
  const group =
    portfolio.groups.find((item) => item.symbol === selected) ??
    portfolio.groups[0]
  const breach = isBreach(
    portfolio.worstScenario.pnl,
    portfolio.portfolioThreshold,
    nlv,
  )

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPalette((open) => !open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="flex h-full min-h-0 overflow-x-auto bg-background">
      <aside className="flex h-full min-h-0 w-14 shrink-0 flex-col items-center gap-1 border-r py-2 lg:hidden">
        <Button
          size="icon-sm"
          variant="outline"
          aria-label="Open holdings"
          onClick={() => setRailOpen(true)}
        >
          <PanelLeft />
        </Button>
        {portfolio.groups.map((item) => {
          const itemBreach = isBreach(item.worstShockPnl, item.threshold, nlv)
          return (
            <button
              key={item.symbol}
              type="button"
              aria-label={item.symbol}
              onClick={() => setSelected(item.symbol)}
              className={`relative w-12 rounded-md px-1 py-2 text-xs font-semibold ${
                item.symbol === selected ? 'bg-muted' : 'hover:bg-muted/50'
              }`}
            >
              {item.symbol}
              <span
                className={`absolute top-1 right-1 size-1.5 rounded-full ${itemBreach ? 'bg-red-500' : 'bg-transparent'}`}
              />
            </button>
          )
        })}
        <LegendButton
          compact
          className="mt-auto w-full px-1"
          open={legendOpen && !railOpen}
          popupClassName="bottom-16 left-full ml-2 max-h-[70vh] w-72 overflow-auto"
          onToggle={() => setLegendOpen((open) => !open)}
        />
      </aside>
      <aside className="hidden h-full min-h-0 w-72 shrink-0 flex-col border-r lg:flex">
        <AccountRail
          portfolio={portfolio}
          actions={actions}
          nlv={nlv}
          callLevel={callLevel}
          selected={selected}
          onSelect={setSelected}
          legendOpen={legendOpen}
          onToggleLegend={() => setLegendOpen((open) => !open)}
        />
      </aside>
      {railOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/40"
            aria-label="Close holdings"
            onClick={() => setRailOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-72 animate-in flex-col bg-background shadow-xl slide-in-from-left">
            <AccountRail
              portfolio={portfolio}
              actions={actions}
              nlv={nlv}
              callLevel={callLevel}
              selected={selected}
              legendOpen={legendOpen}
              onToggleLegend={() => setLegendOpen((open) => !open)}
              onSelect={(symbol) => {
                setSelected(symbol)
                setRailOpen(false)
              }}
            />
          </aside>
        </div>
      ) : null}

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-3">
          <div>
            <p className="text-xs text-muted-foreground">
              Worst Shock · {portfolio.worstScenario.shock}
            </p>
            <p className={`text-xl font-semibold whitespace-nowrap ${pnlClass(portfolio.worstScenario.pnl)}`}>
              {signedUsd(portfolio.worstScenario.pnl)}
              {breach ? (
                <Badge variant="destructive" className="ml-2 align-middle">
                  over Loss Threshold
                </Badge>
              ) : (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  of {portfolio.portfolioThreshold ? usd(thresholdDollars(portfolio.portfolioThreshold, nlv)) : '—'} budget
                </span>
              )}
              {shockMarginCall ? (
                <Badge variant="destructive" className="ml-2 align-middle">
                  margin call · NLV {usd(shockedNlv)}
                </Badge>
              ) : null}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {portfolio.kind === 'account' ? (
              <>
                <span className="text-xs text-muted-foreground">
                  {portfolio.disconnected
                    ? `data as of ${portfolio.dataAsOf}`
                    : `synced ${portfolio.lastSyncedAt}`}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={portfolio.disconnected ? actions.reconnect : actions.sync}
                >
                  {portfolio.disconnected ? 'Reconnect' : 'Sync'}
                </Button>
              </>
            ) : (
              <>
                <Button size="sm" variant="outline" onClick={() => setPalette(true)}>
                  Add Position ⌘K
                </Button>
                <Button
                  size="sm"
                  variant={actions.editing ? 'default' : 'outline'}
                  onClick={() => actions.setEditing(!actions.editing)}
                >
                  {actions.editing ? 'Done' : 'Edit'}
                </Button>
              </>
            )}
          </div>
        </header>

        {group ? (
          <InspectorDetail
            group={group}
            nlv={nlv}
            showGreeks={showGreeks}
            showShock={showShock}
            onToggleGreeks={() => setShowGreeks((open) => !open)}
            onToggleShock={() => setShowShock((open) => !open)}
            onThreshold={(threshold) =>
              actions.setUnderlyingThreshold(group.symbol, threshold)
            }
          />
        ) : null}
      </main>

      {portfolio.kind === 'simulated' ? (
        <CommandPalette
          open={palette}
          onClose={() => setPalette(false)}
          onAdd={(input) => {
            actions.addChainPosition(input)
            setPalette(false)
          }}
        />
      ) : null}
    </div>
  )
}

function AccountRail({
  portfolio,
  actions,
  nlv,
  callLevel,
  selected,
  onSelect,
  legendOpen,
  onToggleLegend,
}: VariantProps & {
  nlv: number
  callLevel: number | undefined
  selected: string
  onSelect: (symbol: string) => void
  legendOpen: boolean
  onToggleLegend: () => void
}) {
  return (
    <>
      <div className="p-4">
        <p className="text-xs text-muted-foreground">
          {portfolio.kind === 'account' ? 'Account' : 'Simulated Portfolio'}
        </p>
        <h1 className="text-lg font-semibold">{portfolio.name}</h1>
        <dl className="mt-3 space-y-3">
          <div>
            <dd className="text-2xl tabular-nums">{usd(nlv)}</dd>
            <dt className="text-xs text-muted-foreground">Net Liquidation Value</dt>
          </div>
          <div>
            {portfolio.kind === 'simulated' && actions.editing ? (
              <Input
                className="h-8"
                defaultValue={portfolio.cash}
                aria-label="Cash"
                onBlur={(event) => actions.setCash(Number(event.target.value) || 0)}
              />
            ) : (
              <dd
                className={`text-lg tabular-nums ${portfolio.cash < 0 ? 'text-red-700' : ''}`}
              >
                {signedWhole(portfolio.cash)}
              </dd>
            )}
            <dt className="text-xs text-muted-foreground">
              Cash{portfolio.cash < 0 ? ' · margin owed' : ''}
            </dt>
          </div>
          <div>
            <dd className="text-lg tabular-nums">
              {portfolio.marginCushion != null && callLevel != null
                ? `${portfolio.marginCushion}%`
                : '—'}
            </dd>
            <dt className="text-xs text-muted-foreground">
              {callLevel != null
                ? `Margin Cushion · call at ${usd(callLevel)}`
                : 'Margin Cushion · not borrowing'}
            </dt>
          </div>
        </dl>
      </div>
      <Separator />
      <nav className="min-h-0 flex-1 overflow-auto p-2">
        {portfolio.groups.map((item) => {
          const itemBreach = isBreach(item.worstShockPnl, item.threshold, nlv)
          return (
            <button
              key={item.symbol}
              type="button"
              aria-label={`${item.symbol}, P/L ${signedUsd(groupPnl(item))}`}
              onClick={() => onSelect(item.symbol)}
              className={`mb-1 w-full rounded-md px-3 py-2 text-left text-sm ${
                item.symbol === selected ? 'bg-muted' : 'hover:bg-muted/50'
              }`}
            >
              <span className="flex items-center justify-between">
                <span className="font-medium">{item.symbol}</span>
                <span className={`whitespace-nowrap ${pnlClass(groupPnl(item))}`}>
                  {signedUsd(groupPnl(item))}
                </span>
              </span>
              <span className="mt-0.5 flex items-center justify-between text-xs text-muted-foreground">
                <span>Shock {signedUsd(item.worstShockPnl)}</span>
                <span
                  className={`size-2 rounded-full ${itemBreach ? 'bg-red-500' : item.threshold ? 'bg-emerald-500' : 'bg-zinc-300'}`}
                />
              </span>
            </button>
          )
        })}
        {portfolio.unpriced.map((position) => (
          <div key={position.id} className="px-3 py-2 text-xs text-muted-foreground">
            {position.instrument} · unpriced
          </div>
        ))}
      </nav>
      <div className="border-t p-3">
        <LegendButton
          className="w-full"
          open={legendOpen}
          popupClassName="bottom-full left-0 mb-2 w-full"
          onToggle={onToggleLegend}
        />
      </div>
    </>
  )
}

function InspectorDetail({
  group,
  nlv,
  showGreeks,
  showShock,
  onToggleGreeks,
  onToggleShock,
  onThreshold,
}: {
  group: UnderlyingGroup
  nlv: number
  showGreeks: boolean
  showShock: boolean
  onToggleGreeks: () => void
  onToggleShock: () => void
  onThreshold: (threshold: { unit: 'dollars'; value: number } | undefined) => void
}) {
  return (
    <div className="flex flex-1">
      <section className="@container min-w-[26rem] flex-1 overflow-auto px-6 py-5">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-2xl font-semibold">
            {group.symbol}{' '}
            <span className="text-base font-normal text-muted-foreground">
              {group.name}
            </span>
          </h2>
          <p className="text-sm text-muted-foreground">
            β {group.beta.toFixed(2)} · HV20 {group.hv20} · HV30 {group.hv30}
          </p>
        </div>
        <dl className="mb-6 grid grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="text-muted-foreground">Market value</dt>
            <dd className="text-lg whitespace-nowrap tabular-nums">{usd(groupMarketValue(group))}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Total P/L</dt>
            <dd className={`text-lg whitespace-nowrap tabular-nums ${pnlClass(groupPnl(group))}`}>
              {signedUsd(groupPnl(group))}
              <span className="ml-2 text-sm">
                {signedPercent(pnlPercent(groupPnl(group), groupTotalCost(group)))}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Shock P/L</dt>
            <dd className={`text-lg whitespace-nowrap tabular-nums ${pnlClass(group.worstShockPnl)}`}>
              {signedUsd(group.worstShockPnl)}
              <span className="ml-2 text-sm">
                {signedPercent(pnlPercent(group.worstShockPnl, groupMarketValue(group)))}
              </span>
            </dd>
          </div>
        </dl>
        <div className="mb-4 flex justify-end gap-2">
          <Button
            size="sm"
            variant={showShock ? 'default' : 'outline'}
            aria-pressed={showShock}
            onClick={onToggleShock}
          >
            Shock
          </Button>
          {group.positions.some((position) => position.iv != null) ? (
            <Button
              size="sm"
              variant={showGreeks ? 'default' : 'outline'}
              aria-expanded={showGreeks}
              onClick={onToggleGreeks}
            >
              Greeks
            </Button>
          ) : null}
        </div>
        <ul className="space-y-3">
          {group.positions.map((position) => (
            <li key={position.id} className="rounded-lg border p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium whitespace-nowrap">
                    {position.instrument}
                    {position.hypothetical ? (
                      <Badge className="ml-2" variant="outline">
                        Hypothetical Trade
                      </Badge>
                    ) : null}
                  </p>
                  <p className="mt-1 flex flex-wrap gap-x-3 text-xs">
                    <Field label="Qty" value={String(position.quantity)} negative={position.quantity < 0} />
                    <Field label="Mark" value={usd2(position.mark)} />
                    <Field
                      label="Total Cost"
                      value={usd2(position.totalCost)}
                      negative={position.totalCost < 0}
                    />
                  </p>
                </div>
                <div className={`shrink-0 text-right ${pnlClass(shownPnl(position, showShock))}`}>
                  <p className="whitespace-nowrap tabular-nums">
                    {signedUsd(shownPnl(position, showShock))}
                  </p>
                  <p className="whitespace-nowrap text-xs tabular-nums">
                    {signedPercent(
                      pnlPercent(
                        shownPnl(position, showShock),
                        showShock ? position.marketValue : position.totalCost,
                      ),
                    )}
                  </p>
                </div>
              </div>
              {showGreeks && position.iv != null ? (
                <p className="mt-2 flex flex-wrap gap-x-3 font-mono text-xs">
                  <Field label="IV" value={String(position.iv)} />
                  <Field label="Δ" value={position.delta?.toFixed(2) ?? '—'} />
                  <Field label="Γ" value={position.gamma?.toFixed(3) ?? '—'} />
                  <Field label="Θ" value={position.theta?.toFixed(2) ?? '—'} />
                  <Field label="ν" value={position.vega?.toFixed(2) ?? '—'} />
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
      <aside className="w-72 shrink-0 overflow-auto border-l p-5 text-sm">
        <h3 className="font-semibold">Loss Threshold</h3>
        <p className="mt-1 text-muted-foreground">
          A risk budget for this Underlying, not an exit rule.
        </p>
        {group.threshold ? (
          <p className="mt-3 text-lg">
            {usd(thresholdDollars(group.threshold, nlv))}
            <Button
              className="ml-2"
              size="xs"
              variant="ghost"
              onClick={() => onThreshold(undefined)}
            >
              Clear
            </Button>
          </p>
        ) : (
          <Button
            className="mt-3"
            size="sm"
            variant="outline"
            onClick={() => onThreshold({ unit: 'dollars', value: 2000 })}
          >
            Set $2,000
          </Button>
        )}
      </aside>
    </div>
  )
}

function CommandPalette({
  open,
  onClose,
  onAdd,
}: {
  open: boolean
  onClose: () => void
  onAdd: VariantProps['actions']['addChainPosition']
}) {
  const [query, setQuery] = useState('')
  const hits = useMemo(
    () =>
      CHAIN.strikes.flatMap((strike) =>
        (['C', 'P'] as const).map((right) => ({
          strike,
          right,
          label: `IREN ${strike} ${right === 'C' ? 'Call' : 'Put'}`,
        })),
      ).filter((item) => item.label.toLowerCase().includes(query.toLowerCase())),
    [query],
  )

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="p-0 sm:max-w-lg">
        <DialogHeader className="px-4 pt-4">
          <DialogTitle>Add Position</DialogTitle>
          <DialogDescription>Type a contract on IREN.</DialogDescription>
        </DialogHeader>
        <Input
          placeholder="IREN 40 Call"
          className="border-0 shadow-none focus-visible:ring-0"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Separator />
        <ul className="max-h-80 overflow-auto p-2">
          {hits.map((item) => (
            <li key={item.label}>
              <button
                type="button"
                className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm hover:bg-muted"
                onClick={() =>
                  onAdd({
                    right: item.right,
                    strike: item.strike,
                    expiry: CHAIN.expiries[0] ?? '2026-01-16',
                    quantity: 1,
                  })
                }
              >
                <span>{item.label}</span>
                <span className="tabular-nums text-muted-foreground">
                  {usd2(CHAIN.marks[item.right][item.strike] ?? 0)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  )
}

function Field({
  label,
  value,
  negative = false,
}: {
  label: string
  value: string
  negative?: boolean
}) {
  return (
    <span>
      <span className="text-muted-foreground">{label} </span>
      <span className={`font-medium ${negative ? 'text-red-700' : 'text-foreground'}`}>
        {value}
      </span>
    </span>
  )
}

function shownPnl(
  position: { marketValue: number; totalCost: number; shockPnl: number },
  showShock: boolean,
) {
  if (showShock) return position.shockPnl
  return position.marketValue - position.totalCost
}

function pnlPercent(pnl: number, cost: number) {
  if (cost === 0) return null
  return (pnl / Math.abs(cost)) * 100
}

function signedPercent(value: number | null) {
  if (value == null) return '—'
  const body = `${Math.abs(value).toFixed(1)}%`
  if (value > 0) return `+${body}`
  if (value < 0) return `−${body}`
  return body
}

function signedWhole(n: number) {
  const body = usd(Math.abs(n))
  if (n < 0) return `−${body}`
  return body
}

const LEGEND = [
  ['Δ Delta', 'How much the Position changes when the Underlying moves $1.'],
  ['Γ Gamma', 'How fast delta itself changes as the Underlying moves.'],
  ['Θ Theta', 'How much value a day takes off, with price and IV unchanged.'],
  ['ν Vega', 'How much the Position changes when IV moves 1 point.'],
  ['IV', "The volatility implied by the contract's current mark."],
  ['β Beta', 'How many percent this Underlying moves when SPY moves 1%.'],
  ['HV20 / HV30', 'How much the Underlying actually moved over 20 and 30 days.'],
  [
    'Margin Cushion',
    'The percent Net Liquidation Value can fall before a margin call. The call level under it is that value.',
  ],
] as const

function LegendButton({
  open,
  onToggle,
  popupClassName,
  className,
  compact = false,
}: {
  open: boolean
  onToggle: () => void
  popupClassName: string
  className?: string
  compact?: boolean
}) {
  return (
    <div className={`relative ${className ?? ''}`}>
      {open ? (
        <div
          className={`absolute z-30 rounded-xl border bg-background p-4 shadow-lg ${popupClassName}`}
        >
          <p className="mb-2 text-sm font-semibold">Legend</p>
          <dl className="space-y-2">
            {LEGEND.map(([term, meaning]) => (
              <div key={term}>
                <dt className="text-sm font-medium">{term}</dt>
                <dd className="text-xs text-muted-foreground">{meaning}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
      <Button
        aria-label="Legend"
        className={compact ? undefined : 'w-full'}
        size={compact ? 'icon-sm' : 'sm'}
        variant="default"
        onClick={onToggle}
        aria-expanded={open}
      >
        {compact ? <BookOpen /> : 'Legend'}
      </Button>
    </div>
  )
}
