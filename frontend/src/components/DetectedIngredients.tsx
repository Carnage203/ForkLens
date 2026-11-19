import { useState } from 'react'
import { Check, Pencil, X } from 'lucide-react'
import type { Detected } from '../types'
import { cn } from './ui'

const SURE = 0.8
const UNSURE = 0.6

function tone(c: number) {
  if (c >= SURE) return { bar: 'bg-leaf-500', text: 'text-leaf-700 dark:text-leaf-100', border: 'border-line' }
  if (c >= UNSURE) return { bar: 'bg-amber-400', text: 'text-amber-700 dark:text-amber-300', border: 'border-line' }
  return { bar: 'bg-red-500', text: 'text-red-600 dark:text-red-300', border: 'border-amber-400' }
}

interface Props { items: Detected[]; onChange: (items: Detected[]) => void }

/** Confidence plot of the detected ingredients: one compact tile per item, tap the name to fix it, tick to confirm, x to drop. */
export default function DetectedIngredients({ items, onChange }: Props) {
  const [editing, setEditing] = useState<string | null>(null)
  const sorted = [...items].sort((a, b) => b.confidence - a.confidence)
  const unsure = items.filter(i => i.confidence < UNSURE).length

  const remove = (name: string) => onChange(items.filter(i => i.name !== name))
  const confirm = (name: string) => onChange(items.map(i => (i.name === name ? { ...i, confidence: 1 } : i)))
  function rename(oldName: string, raw: string) {
    setEditing(null)
    const name = raw.trim().toLowerCase()
    if (!name || name === oldName) return
    const rest = items.filter(i => i.name !== oldName)
    onChange(rest.some(i => i.name === name) ? rest : items.map(i => (i.name === oldName ? { name, confidence: 1 } : i)))
  }

  if (!items.length) return null
  return (
    <div className="space-y-2" aria-label="Detected ingredients">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-bold">Found {items.length} ingredient{items.length === 1 ? '' : 's'}</h3>
        <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-bold', unsure ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200' : 'bg-leaf-50 text-leaf-700 dark:bg-leaf-700/20 dark:text-leaf-100')}>
          {unsure ? `${unsure} to check` : 'All look right'}
        </span>
      </div>
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {sorted.map(i => {
          const t = tone(i.confidence)
          const pct = Math.round(i.confidence * 100)
          return (
            <li key={i.name} className={cn('animate-rise rounded-2xl border bg-card p-2.5 shadow-soft', t.border)}>
              <div className="flex items-center gap-1">
                {editing === i.name ? (
                  <input autoFocus defaultValue={i.name} maxLength={40} aria-label={`Rename ${i.name}`}
                    className="min-w-0 flex-1 rounded-lg border border-brand-300 bg-surface px-2 py-1 text-sm font-semibold outline-none"
                    onBlur={e => rename(i.name, e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); if (e.key === 'Escape') setEditing(null) }} />
                ) : (
                  <button onClick={() => setEditing(i.name)} aria-label={`Edit ${i.name}`} className="flex min-w-0 flex-1 items-center gap-1 text-left text-sm font-semibold capitalize">
                    <span className="truncate">{i.name}</span><Pencil size={11} className="shrink-0 text-muted" />
                  </button>
                )}
                {i.confidence < UNSURE && editing !== i.name && (
                  <button onClick={() => confirm(i.name)} aria-label={`Confirm ${i.name}`} className="rounded-full p-1 text-leaf-700 hover:bg-leaf-50 dark:text-leaf-100"><Check size={14} /></button>
                )}
                <button onClick={() => remove(i.name)} aria-label={`Remove ${i.name}`} className="rounded-full p-1 text-muted hover:bg-line/60"><X size={14} /></button>
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line/70" role="img" aria-label={`${pct}% sure`}>
                  <div className={cn('h-full rounded-full transition-all duration-500', t.bar)} style={{ width: `${pct}%` }} />
                </div>
                <span className={cn('w-9 text-right text-xs font-bold tabular-nums', t.text)}>{pct}%</span>
              </div>
            </li>
          )
        })}
      </ul>
      <p className="text-xs text-muted">Bars show how sure the scan is. Tap a name to fix it, tick to confirm, x to remove.</p>
    </div>
  )
}
