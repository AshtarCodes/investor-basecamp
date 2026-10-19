import { expect, test } from 'vitest'

import { cn } from './utils.ts'

test('a later Tailwind class wins over a conflicting earlier one', () => {
  expect(cn('px-2 text-sm', 'px-4')).toBe('text-sm px-4')
})
