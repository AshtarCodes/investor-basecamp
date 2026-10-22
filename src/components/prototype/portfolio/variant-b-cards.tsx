import { Fragment, useState } from 'react'

import { Badge } from '#/components/ui/badge.tsx'
import { Button } from '#/components/ui/button.tsx'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '#/components/ui/card.tsx'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '#/components/ui/dialog.tsx'
import { Input } from '#/components/ui/input.tsx'
import { Progress } from '#/components/ui/progress.tsx'

import {
  CHAIN,
  groupPnl,
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

export const variantBName = 'Risk cards'

export function VariantB({ portfolio, actions }: VariantProps) {
  const nlv = netLiquidationValue(portfolio)
  const budget = portfolio.portfolioThreshold
    ? thresholdDollars(portfolio.portfolioThreshold, nlv)
    : 0
  const used = budget ? Math.min(100, (Math.abs(Math.min(portfolio.worstScenario.pnl, 0)) / budget) * 100) : 0
  const breach = isBreach(
    portfolio.worstScenario.pnl,
    portfolio.portfolioThreshold,
    nlv,
  )

  return (
    <div className="min-h-screen bg-[var(--foam)] px-4 py-6 pb-24 text-[var(--sea-ink)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-widest text-[var(--kicker)] uppercase">
              {portfolio.kind === 'account' ? 'Account' : 'Simulated Portfolio'}
            </p>
            <h1 className="font-[Fraunces] text-4xl">{portfolio.name}</h1>
            <p className="mt-1 text-sm text-[var(--sea-ink-soft)]">
              NLV {usd(nlv)} · cash{' '}
              {portfolio.kind === 'simulated' && actions.editing ? (
                <Input
                  className="inline-flex h-7 w-28 bg-white"
                  defaultValue={portfolio.cash}
                  onBlur={(event) =>
                    actions.setCash(Number(event.target.value) || 0)
                  }
                />
              ) : (
                usd(portfolio.cash)
              )}
            </p>
          </div>
          <div className="flex gap-2">
            {portfolio.kind === 'account' ? (
              portfolio.disconnected ? (
                <Button onClick={actions.reconnect}>Reconnect Schwab</Button>
              ) : (
                <Button variant="outline" onClick={actions.sync}>
                  Sync now
                </Button>
              )
            ) : (
              <>
                <AddFromChain onAdd={actions.addChainPosition} />
                <Button
                  variant={actions.editing ? 'default' : 'outline'}
                  onClick={() => actions.setEditing(!actions.editing)}
                >
                  {actions.editing ? 'Done editing' : 'Edit'}
                </Button>
              </>
            )}
          </div>
        </div>

        {portfolio.disconnected ? (
          <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm">
            Data as of {portfolio.dataAsOf}. Reconnect to refresh. Scenarios still
            run on these frozen inputs.
          </div>
        ) : portfolio.kind === 'account' ? (
          <p className="text-sm text-[var(--sea-ink-soft)]">
            Last synced {portfolio.lastSyncedAt ?? '—'}. Auto-syncs when older
            than 15 minutes.
          </p>
        ) : null}

        <Card className={breach ? 'border-red-300 bg-red-50' : 'bg-white/80'}>
          <CardHeader>
            <CardDescription>Worst Shock against the Loss Threshold</CardDescription>
            <CardTitle className="flex flex-wrap items-baseline justify-between gap-2">
              <span className={pnlClass(portfolio.worstScenario.pnl)}>
                {signedUsd(portfolio.worstScenario.pnl)}
              </span>
              <span className="text-base font-normal text-muted-foreground">
                budget {usd(budget)}
                {portfolio.portfolioThreshold?.unit === 'percent'
                  ? ` (${portfolio.portfolioThreshold.value}% of NLV)`
                  : ''}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Progress value={used} className={breach ? 'bg-red-200' : ''} />
            <p className="text-sm text-muted-foreground">
              {portfolio.worstScenario.name} · {portfolio.worstScenario.shock}
              {breach ? ' · this Shock breaches the Portfolio budget' : ''}
            </p>
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-2">
          {portfolio.groups.map((group) => {
            const groupBreach = isBreach(group.worstShockPnl, group.threshold, nlv)
            return (
              <Card key={group.symbol} className="bg-white/90">
                <CardHeader className="border-b pb-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <CardTitle>
                        {group.symbol}{' '}
                        <span className="text-sm font-normal text-muted-foreground">
                          {group.name}
                        </span>
                      </CardTitle>
                      <CardDescription>
                        β {group.beta.toFixed(2)} · HV20 {group.hv20} · HV30{' '}
                        {group.hv30}
                      </CardDescription>
                    </div>
                    <div className="text-right">
                      <p className={`text-lg font-semibold ${pnlClass(groupPnl(group))}`}>
                        {signedUsd(groupPnl(group))}
                      </p>
                      <p className="text-xs text-muted-foreground">total P/L</p>
                    </div>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-sm">
                    <span className={groupBreach ? 'text-red-700' : 'text-muted-foreground'}>
                      Shock P/L {signedUsd(group.worstShockPnl)}
                    </span>
                    {group.threshold ? (
                      <Badge variant={groupBreach ? 'destructive' : 'secondary'}>
                        threshold {usd(thresholdDollars(group.threshold, nlv))}
                      </Badge>
                    ) : (
                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() =>
                          actions.setUnderlyingThreshold(group.symbol, {
                            unit: 'dollars',
                            value: 2000,
                          })
                        }
                      >
                        Set Loss Threshold
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="px-0">
                  <ul>
                    {group.positions.map((position) => (
                      <li
                        key={position.id}
                        className="flex items-baseline justify-between gap-3 border-b px-6 py-3 last:border-0"
                      >
                        <div>
                          <p className="text-sm font-medium">
                            {position.instrument}
                            {position.hypothetical ? (
                              <Badge className="ml-2" variant="outline">
                                Hypothetical Trade
                              </Badge>
                            ) : null}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            qty {position.quantity}
                            {position.iv != null ? ` · IV ${position.iv}` : ''}
                            {position.delta != null
                              ? ` · Δ ${position.delta.toFixed(2)}`
                              : ''}
                          </p>
                        </div>
                        <div className="text-right tabular-nums">
                          <p>{usd2(position.marketValue)}</p>
                          <p className={`text-xs ${pnlClass(positionPnl(position))}`}>
                            {signedUsd(positionPnl(position))}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {portfolio.unpriced.length > 0 ? (
          <Card className="border-dashed bg-white/60">
            <CardHeader>
              <CardTitle className="text-base">Unpriced in v1</CardTitle>
              <CardDescription>
                Listed so nothing is silently dropped.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {portfolio.unpriced.map((position) => (
                <p key={position.id} className="text-sm">
                  {position.instrument} · {position.quantity} ·{' '}
                  {usd2(position.marketValue)}
                </p>
              ))}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  )
}

function AddFromChain({
  onAdd,
}: {
  onAdd: VariantProps['actions']['addChainPosition']
}) {
  const [open, setOpen] = useState(false)
  const [expiry, setExpiry] = useState(CHAIN.expiries[0])
  const [qty, setQty] = useState(1)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Add Hypothetical Trade</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>IREN chain</DialogTitle>
          <DialogDescription>
            Search is stubbed to IREN so you can judge the picker, not the quote
            feed.
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-2">
          {CHAIN.expiries.map((value) => (
            <Button
              key={value}
              size="sm"
              variant={expiry === value ? 'default' : 'outline'}
              onClick={() => setExpiry(value)}
            >
              {value}
            </Button>
          ))}
          <Input
            className="ml-auto w-20"
            type="number"
            value={qty}
            onChange={(event) => setQty(Number(event.target.value) || 1)}
          />
        </div>
        <div className="grid grid-cols-[auto_1fr_1fr] gap-1 text-center text-sm">
          <div />
          <div className="text-xs text-muted-foreground">Calls</div>
          <div className="text-xs text-muted-foreground">Puts</div>
          {CHAIN.strikes.map((strike) => (
            <Fragment key={strike}>
              <div className="flex items-center justify-end pr-2 font-medium">
                {strike}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  onAdd({ right: 'C', strike, expiry: expiry ?? '', quantity: qty })
                  setOpen(false)
                }}
              >
                {usd2(CHAIN.marks.C[strike] ?? 0)}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  onAdd({ right: 'P', strike, expiry: expiry ?? '', quantity: qty })
                  setOpen(false)
                }}
              >
                {usd2(CHAIN.marks.P[strike] ?? 0)}
              </Button>
            </Fragment>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
