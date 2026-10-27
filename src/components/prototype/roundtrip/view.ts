// PROTOTYPE (throwaway). What the shell hands each of the three views.

import type { ReactNode } from 'react'

import type { PathLike } from './model.ts'
import type { BuildView } from './quotes.ts'
import type { PageState, Run } from './types.ts'

export type ViewProps = {
  state: PageState
  update: (patch: Partial<PageState>) => void
  build: BuildView // the focused Build
  builds: BuildView[] // every Build that priced, sorted by Expected
  paths: PathLike[] // the unsaved copy first, if any, then the saved paths
  path: PathLike // the loaded path
  run: (buildId: string, pathId?: string) => Run | undefined // at the page's debt share
  baseline: (budget: number, pathId?: string) => Run | undefined // all shares at that budget
  expectedOf: (buildId: string) => number | null // over the saved paths with weight, at the page's debt share
  side: ReactNode // the selection area (Price Paths), under the legend
  below: ReactNode // the edit area (the loaded path's points), under the chart
}
