// PROTOTYPE (throwaway). Legend with an eye (show or hide) and a solo button per leg.

import { Eye, EyeOff } from 'lucide-react'

import { Button } from '#/components/ui/button.tsx'

export type LegendItem = { id: string; label: string; color: string; detail?: string }

export function LegLegend({
  items,
  hidden,
  onToggle,
  onSolo,
  onAll,
  onNone,
}: {
  items: LegendItem[]
  hidden: string[]
  onToggle: (id: string) => void
  onSolo: (id: string) => void
  onAll: () => void
  onNone: () => void
}) {
  return (
    <div className="flex flex-col gap-1 text-xs">
      <div className="flex items-center gap-1">
        <Button size="xs" variant="outline" onClick={onAll}>
          Show all
        </Button>
        <Button size="xs" variant="outline" onClick={onNone}>
          Hide all
        </Button>
      </div>
      <ul className="flex flex-col gap-1">
        {items.map((item) => {
          const isHidden = hidden.includes(item.id)
          return (
            <li key={item.id} className={`flex items-stretch overflow-hidden rounded border ${isHidden ? 'opacity-55' : ''}`}>
              <button type="button" onClick={() => onToggle(item.id)} className="flex min-w-0 flex-1 items-center gap-2 px-2 py-1 text-left hover:bg-muted/60">
                <span className="inline-block h-2 w-4 shrink-0 rounded" style={{ background: item.color }} />
                <span className="min-w-0 truncate">{item.label}</span>
                {item.detail && <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">{item.detail}</span>}
              </button>
              <button
                type="button"
                aria-label={`Show only ${item.label}`}
                title="Show only this one"
                onClick={() => onSolo(item.id)}
                className="border-l px-1.5 text-[10px] text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              >
                solo
              </button>
              <button
                type="button"
                aria-label={isHidden ? `Show ${item.label}` : `Hide ${item.label}`}
                title={isHidden ? 'Show on chart' : 'Hide on chart'}
                onClick={() => onToggle(item.id)}
                className="border-l px-1.5 text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              >
                {isHidden ? <EyeOff className="size-3.5" aria-hidden /> : <Eye className="size-3.5" aria-hidden />}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
