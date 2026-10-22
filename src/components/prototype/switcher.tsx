import { useEffect } from 'react'

import { Button } from '#/components/ui/button.tsx'

type PrototypeVariant = { key: string; name: string }

interface PrototypeSwitcherProps {
  variants: readonly PrototypeVariant[]
  current: string
  onChange: (key: string) => void
}

export function PrototypeSwitcher({
  variants,
  current,
  onChange,
}: PrototypeSwitcherProps) {
  const index = Math.max(
    0,
    variants.findIndex((variant) => variant.key === current),
  )
  const label = variants[index] ?? variants[0]

  function cycle(delta: number) {
    const next = variants[(index + delta + variants.length) % variants.length]
    if (next) onChange(next.key)
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target
      if (
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return
      }
      if (event.key === 'ArrowLeft') cycle(-1)
      if (event.key === 'ArrowRight') cycle(1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (process.env.NODE_ENV === 'production' || !label) return null

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center">
      <div className="pointer-events-auto flex items-center gap-1 rounded-full border-2 border-zinc-900 bg-zinc-950 px-2 py-1 text-zinc-50 shadow-lg">
        <Button
          type="button"
          size="icon-xs"
          variant="ghost"
          className="text-zinc-50 hover:bg-zinc-800 hover:text-zinc-50"
          aria-label="Previous variant"
          onClick={() => cycle(-1)}
        >
          ←
        </Button>
        <span className="min-w-40 px-2 text-center font-mono text-xs tracking-wide">
          {label.key} ({label.name})
        </span>
        <Button
          type="button"
          size="icon-xs"
          variant="ghost"
          className="text-zinc-50 hover:bg-zinc-800 hover:text-zinc-50"
          aria-label="Next variant"
          onClick={() => cycle(1)}
        >
          →
        </Button>
      </div>
    </div>
  )
}
