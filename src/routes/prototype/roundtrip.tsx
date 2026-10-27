// PROTOTYPE (throwaway). Builds of your own on Price Paths of your own, priced live, on /prototype/roundtrip.
// The page takes its data from server functions after it mounts (a live Schwab chain and an engine run take a few seconds).

import { createFileRoute } from '@tanstack/react-router'

import { DEBTS, parseHidden } from '#/components/prototype/roundtrip/model.ts'
import { RoundtripPrototype } from '#/components/prototype/roundtrip/roundtrip-prototype.tsx'
import type { PageState, VariantKey, YMode } from '#/components/prototype/roundtrip/types.ts'

const pick = <T extends string>(value: unknown, allowed: readonly T[], fallback: T): T => allowed.find((a) => a === value) ?? fallback

function validateSearch(search: Record<string, unknown>): PageState {
  return {
    variant: pick<VariantKey>(search.variant, ['A', 'B', 'C'], 'A'),
    build: typeof search.build === 'string' ? search.build : '',
    path: typeof search.path === 'string' ? search.path : 'SM',
    debt: pick(typeof search.debt === 'number' ? search.debt.toFixed(2) : search.debt, DEBTS, '0.25'),
    y: pick<YMode>(search.y, ['usd', 'pct'], 'usd'),
    hidden: Array.isArray(search.hidden) ? search.hidden.filter((h): h is string => typeof h === 'string') : parseHidden(search.hidden),
    vs: typeof search.vs === 'string' ? search.vs : '',
  }
}

export const Route = createFileRoute('/prototype/roundtrip')({
  validateSearch,
  component: RoundtripRoute,
})

function RoundtripRoute() {
  const state = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <RoundtripPrototype
      state={state}
      update={(patch) =>
        void navigate({
          search: (prev) => ({ ...prev, ...patch, ...(patch.build !== undefined && patch.build !== prev.build ? { hidden: [] } : {}) }),
          replace: true,
        })
      }
    />
  )
}
