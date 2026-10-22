import { Fragment, useState } from 'react'

import { Badge } from '#/components/ui/badge.tsx'
import { Button } from '#/components/ui/button.tsx'
import { Input } from '#/components/ui/input.tsx'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '#/components/ui/table.tsx'

import {
  groupMarketValue,
  groupPnl,
  groupTotalCost,
  isBreach,
  netLiquidationValue,
  pnlClass,
  positionPnl,
  signedUsd,
  thresholdDollars,
  usd,
  usd2,
  type VariantProps,
} from './fixture.ts'

export const variantAName = 'Blotter'

export function VariantA({ portfolio, actions }: VariantProps) {
  const nlv = netLiquidationValue(portfolio)
  const budget = portfolio.portfolioThreshold
    ? thresholdDollars(portfolio.portfolioThreshold, nlv)
    : undefined
  const budgetBreach = isBreach(
    portfolio.worstScenario.pnl,
    portfolio.portfolioThreshold,
    nlv,
  )
  const [occ, setOcc] = useState('IREN 16 Jan 26 45 Call')
  const [qty, setQty] = useState('-1')

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/95 px-4 py-3 font-mono text-xs">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[10px] tracking-[0.2em] text-zinc-500 uppercase">
              {portfolio.kind === 'account' ? 'Account' : 'Simulated Portfolio'}
            </p>
            <h1 className="text-lg text-zinc-50">{portfolio.name}</h1>
          </div>
          <dl className="flex flex-wrap gap-6 tabular-nums">
            <div>
              <dt className="text-zinc-500">NLV</dt>
              <dd className="text-base text-zinc-50">{usd(nlv)}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">Cash</dt>
              <dd>
                {portfolio.kind === 'simulated' && actions.editing ? (
                  <Input
                    className="h-7 w-28 border-zinc-700 bg-zinc-900 text-zinc-50"
                    defaultValue={portfolio.cash}
                    onBlur={(event) =>
                      actions.setCash(Number(event.target.value) || 0)
                    }
                  />
                ) : (
                  usd(portfolio.cash)
                )}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Worst Shock P/L</dt>
              <dd className={pnlClass(portfolio.worstScenario.pnl)}>
                {signedUsd(portfolio.worstScenario.pnl)}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Loss Threshold</dt>
              <dd className={budgetBreach ? 'text-red-400' : 'text-zinc-50'}>
                {budget
                  ? `${usd(budget)}${portfolio.portfolioThreshold?.unit === 'percent' ? ` (${portfolio.portfolioThreshold.value}%)` : ''}`
                  : '—'}
                {budgetBreach ? ' BREACH' : ''}
              </dd>
            </div>
          </dl>
          <div className="flex items-center gap-2">
            {portfolio.kind === 'account' ? (
              <>
                <span className="text-zinc-500">
                  {portfolio.disconnected
                    ? `data as of ${formatStamp(portfolio.dataAsOf)}`
                    : `synced ${formatStamp(portfolio.lastSyncedAt)}`}
                </span>
                {portfolio.disconnected ? (
                  <Button size="xs" variant="secondary" onClick={actions.reconnect}>
                    Reconnect
                  </Button>
                ) : (
                  <Button size="xs" variant="secondary" onClick={actions.sync}>
                    Sync
                  </Button>
                )}
              </>
            ) : (
              <Button
                size="xs"
                variant={actions.editing ? 'default' : 'secondary'}
                onClick={() => actions.setEditing(!actions.editing)}
              >
                {actions.editing ? 'Done' : 'Edit'}
              </Button>
            )}
          </div>
        </div>
        {portfolio.disconnected ? (
          <p className="mt-2 text-amber-400">
            Schwab token expired. Scenarios still run on frozen inputs.
          </p>
        ) : null}
        <p className="mt-2 text-zinc-500">
          {portfolio.worstScenario.name}: {portfolio.worstScenario.shock}
        </p>
      </header>

      <Table className="font-mono text-[11px] text-zinc-200">
        <TableHeader className="bg-zinc-900">
          <TableRow className="border-zinc-800 hover:bg-transparent">
            <TableHead className="text-zinc-400">Instrument</TableHead>
            <TableHead className="text-right text-zinc-400">Qty</TableHead>
            <TableHead className="text-right text-zinc-400">Total Cost</TableHead>
            <TableHead className="text-right text-zinc-400">Mkt</TableHead>
            <TableHead className="text-right text-zinc-400">P/L</TableHead>
            <TableHead className="text-right text-zinc-400">Δ</TableHead>
            <TableHead className="text-right text-zinc-400">Γ</TableHead>
            <TableHead className="text-right text-zinc-400">Θ</TableHead>
            <TableHead className="text-right text-zinc-400">ν</TableHead>
            <TableHead className="text-right text-zinc-400">IV</TableHead>
            <TableHead className="text-right text-zinc-400">HV20</TableHead>
            <TableHead className="text-right text-zinc-400">HV30</TableHead>
            <TableHead className="text-right text-zinc-400">β</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {portfolio.groups.map((group) => {
            const breach = isBreach(group.worstShockPnl, group.threshold, nlv)
            return (
              <Fragment key={group.symbol}>
                <TableRow className="border-zinc-800 bg-zinc-900/80 hover:bg-zinc-900">
                  <TableCell colSpan={4} className="font-sans">
                    <span className="mr-2 font-semibold text-zinc-50">
                      {group.symbol}
                    </span>
                    <span className="text-zinc-500">{group.name}</span>
                    {group.threshold ? (
                      <Badge
                        variant={breach ? 'destructive' : 'outline'}
                        className="ml-2 border-zinc-600 text-[10px]"
                      >
                        threshold {usd(thresholdDollars(group.threshold, nlv))}
                        {breach ? ' · breach' : ''}
                      </Badge>
                    ) : (
                      <button
                        type="button"
                        className="ml-2 text-[10px] text-zinc-500 underline"
                        onClick={() =>
                          actions.setUnderlyingThreshold(group.symbol, {
                            unit: 'dollars',
                            value: 2000,
                          })
                        }
                      >
                        set threshold
                      </button>
                    )}
                  </TableCell>
                  <TableCell className={`text-right ${pnlClass(groupPnl(group))}`}>
                    {signedUsd(groupPnl(group))}
                  </TableCell>
                  <TableCell colSpan={4} className="text-right text-zinc-500">
                    Shock P/L {signedUsd(group.worstShockPnl)}
                  </TableCell>
                  <TableCell className="text-right">{group.hv20}</TableCell>
                  <TableCell className="text-right">{group.hv30}</TableCell>
                  <TableCell className="text-right">{group.beta.toFixed(2)}</TableCell>
                </TableRow>
                {group.positions.map((position) => (
                  <TableRow key={position.id} className="border-zinc-800">
                    <TableCell className="pl-6">
                      {position.instrument}
                      {position.hypothetical ? (
                        <Badge variant="outline" className="ml-2 text-[10px]">
                          Hypothetical Trade
                        </Badge>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-right">{position.quantity}</TableCell>
                    <TableCell className="text-right">
                      {usd2(position.totalCost)}
                    </TableCell>
                    <TableCell className="text-right">
                      {usd2(position.marketValue)}
                    </TableCell>
                    <TableCell className={`text-right ${pnlClass(positionPnl(position))}`}>
                      {signedUsd(positionPnl(position))}
                    </TableCell>
                    <TableCell className="text-right">
                      {position.delta?.toFixed(2) ?? '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      {position.gamma?.toFixed(3) ?? '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      {position.theta?.toFixed(2) ?? '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      {position.vega?.toFixed(2) ?? '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      {position.iv?.toFixed(0) ?? '—'}
                    </TableCell>
                    <TableCell className="text-right text-zinc-600">
                      {group.hv20}
                    </TableCell>
                    <TableCell className="text-right text-zinc-600">
                      {group.hv30}
                    </TableCell>
                    <TableCell className="text-right text-zinc-600">
                      {group.beta.toFixed(2)}
                    </TableCell>
                  </TableRow>
                ))}
                <TableRow className="border-zinc-800 text-zinc-500">
                  <TableCell className="pl-6">subtotal</TableCell>
                  <TableCell />
                  <TableCell className="text-right">
                    {usd2(groupTotalCost(group))}
                  </TableCell>
                  <TableCell className="text-right">
                    {usd2(groupMarketValue(group))}
                  </TableCell>
                  <TableCell className={`text-right ${pnlClass(groupPnl(group))}`}>
                    {signedUsd(groupPnl(group))}
                  </TableCell>
                  <TableCell colSpan={8} />
                </TableRow>
              </Fragment>
            )
          })}
          {portfolio.unpriced.map((position) => (
            <TableRow key={position.id} className="border-zinc-800 text-zinc-500">
              <TableCell>
                {position.instrument}{' '}
                <Badge variant="outline">unpriced in v1</Badge>
              </TableCell>
              <TableCell className="text-right">{position.quantity}</TableCell>
              <TableCell className="text-right">{usd2(position.totalCost)}</TableCell>
              <TableCell className="text-right">{usd2(position.marketValue)}</TableCell>
              <TableCell className={`text-right ${pnlClass(positionPnl(position))}`}>
                {signedUsd(positionPnl(position))}
              </TableCell>
              <TableCell colSpan={8} className="text-zinc-600">
                listed, never dropped
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {portfolio.kind === 'simulated' ? (
        <form
          className="flex flex-wrap items-end gap-2 border-t border-zinc-800 px-4 py-3 font-mono text-xs"
          onSubmit={(event) => {
            event.preventDefault()
            actions.addFromOcc(occ, Number(qty) || 1)
          }}
        >
          <label className="flex flex-col gap-1" htmlFor="occ">
            Type a contract
            <Input
              id="occ"
              className="h-8 w-72 border-zinc-700 bg-zinc-900"
              value={occ}
              onChange={(event) => setOcc(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1" htmlFor="occ-qty">
            Qty
            <Input
              id="occ-qty"
              className="h-8 w-20 border-zinc-700 bg-zinc-900"
              value={qty}
              onChange={(event) => setQty(event.target.value)}
            />
          </label>
          <Button size="sm" type="submit">
            Add Position
          </Button>
        </form>
      ) : (
        <p className="px-4 py-3 font-mono text-xs text-zinc-500">
          Accounts only change through Sync. Add Positions on a Simulated Portfolio.
        </p>
      )}
    </div>
  )
}

function formatStamp(iso?: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    month: 'short',
    day: 'numeric',
  })
}
