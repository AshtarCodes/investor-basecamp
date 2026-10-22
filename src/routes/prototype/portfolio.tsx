// PROTOTYPE (throwaway). Three variants of the Portfolio page, switchable via ?variant=, on /prototype/portfolio.

import { useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'

import { Button } from '#/components/ui/button.tsx'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '#/components/ui/collapsible.tsx'
import { PrototypeSwitcher } from '#/components/prototype/switcher.tsx'
import {
  accountFixture,
  addFromChain,
  addFromOcc,
  simulatedFixture,
  type Kind,
  type LossThreshold,
  type PortfolioActions,
  type PortfolioView,
} from '#/components/prototype/portfolio/fixture.ts'
import {
  VariantA,
  variantAName,
} from '#/components/prototype/portfolio/variant-a-blotter.tsx'
import {
  VariantB,
  variantBName,
} from '#/components/prototype/portfolio/variant-b-cards.tsx'
import {
  VariantC,
  variantCName,
} from '#/components/prototype/portfolio/variant-c-inspector.tsx'

const VARIANTS = [
  { key: 'A', name: variantAName },
  { key: 'B', name: variantBName },
  { key: 'C', name: variantCName },
] as const

type VariantKey = (typeof VARIANTS)[number]['key']

export const Route = createFileRoute('/prototype/portfolio')({
  validateSearch: (search: Record<string, unknown>): { variant: VariantKey } => ({
    variant:
      search.variant === 'B' || search.variant === 'C' ? search.variant : 'A',
  }),
  component: PortfolioPrototypeRoute,
})

function PortfolioPrototypeRoute() {
  const { variant } = Route.useSearch()
  const navigate = Route.useNavigate()
  const [kind, setKind] = useState<Kind>('account')
  const [editing, setEditing] = useState(false)
  const [account, setAccount] = useState<PortfolioView>(accountFixture)
  const [simulated, setSimulated] = useState<PortfolioView>(simulatedFixture)
  const portfolio = kind === 'account' ? account : simulated
  const setPortfolio = kind === 'account' ? setAccount : setSimulated

  const actions: PortfolioActions = {
    kind,
    setKind,
    editing,
    setEditing,
    setCash: (value) =>
      setPortfolio((current) => ({ ...current, cash: value })),
    sync: () =>
      setAccount((current) => ({
        ...current,
        lastSyncedAt: new Date().toISOString(),
        dataAsOf: new Date().toISOString(),
        disconnected: false,
      })),
    reconnect: () =>
      setAccount((current) => ({
        ...current,
        disconnected: false,
        lastSyncedAt: new Date().toISOString(),
        dataAsOf: new Date().toISOString(),
      })),
    expireToken: () =>
      setAccount((current) => ({ ...current, disconnected: true })),
    addFromOcc: (text, quantity) =>
      setPortfolio((current) => addFromOcc(current, text, quantity)),
    addChainPosition: (input) =>
      setPortfolio((current) => addFromChain(current, input)),
    setUnderlyingThreshold: (symbol, threshold: LossThreshold | undefined) =>
      setPortfolio((current) => ({
        ...current,
        groups: current.groups.map((group) =>
          group.symbol === symbol ? { ...group, threshold } : group,
        ),
      })),
  }

  return (
    <div className="flex h-dvh flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b-2 border-zinc-900 bg-yellow-300 px-3 py-2 text-xs text-zinc-900">
        <span className="font-mono font-bold">PROTOTYPE CONTROLS</span>
        <Button
          size="xs"
          variant={kind === 'account' ? 'default' : 'outline'}
          onClick={() => setKind('account')}
        >
          Account
        </Button>
        <Button
          size="xs"
          variant={kind === 'simulated' ? 'default' : 'outline'}
          onClick={() => setKind('simulated')}
        >
          Simulated Portfolio
        </Button>
        <Button size="xs" variant="outline" onClick={actions.expireToken}>
          Expire Schwab token
        </Button>
        <Button
          size="xs"
          variant="outline"
          onClick={() => {
            setAccount(accountFixture())
            setSimulated(simulatedFixture())
            setEditing(false)
          }}
        >
          Reset fixture
        </Button>
        <Collapsible>
          <CollapsibleTrigger className="underline">state</CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="mt-2 max-h-64 overflow-auto bg-zinc-950 p-3 text-[10px] text-zinc-100">
              {JSON.stringify({ variant, kind, editing, portfolio }, null, 2)}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      </div>

      <div className="min-h-0 flex-1">
        {variant === 'A' ? <VariantA portfolio={portfolio} actions={actions} /> : null}
        {variant === 'B' ? <VariantB portfolio={portfolio} actions={actions} /> : null}
        {variant === 'C' ? <VariantC portfolio={portfolio} actions={actions} /> : null}
      </div>

      <PrototypeSwitcher
        variants={VARIANTS}
        current={variant}
        onChange={(key) => {
          if (key === 'A' || key === 'B' || key === 'C') {
            void navigate({ search: { variant: key } })
          }
        }}
      />
    </div>
  )
}
