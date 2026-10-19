import { QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderOptions } from '@testing-library/react'
import type { ReactElement } from 'react'

import { getContext } from '#/integrations/tanstack-query/root-provider.tsx'

export function renderWithQuery(ui: ReactElement, options?: RenderOptions) {
  const { queryClient } = getContext()
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
      options,
    ),
  }
}
