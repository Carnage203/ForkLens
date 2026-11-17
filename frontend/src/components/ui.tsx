import { useEffect, useState, type ReactNode } from 'react'
import { X, Search, Plus } from 'lucide-react'

export const cn = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(' ')

export function Spinner({ className }: { className?: string }) {
  return <span className={cn('inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent', className)} role="status" aria-label="Loading" />
}

export function Skeleton({ className }: { className?: string }) { return <div className={cn('skeleton h-6', className)} /> }

export function Empty({ icon, title, hint, action }: { icon: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-2 py-10 text-center">
      <div className="mb-1 grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-900/30">{icon}</div>
      <h3 className="text-lg font-bold">{title}</h3>
      {hint && <p className="max-w-sm text-sm text-muted">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function Chip({ children, onRemove, tone = 'brand' }: { children: ReactNode; onRemove?: () => void; tone?: 'brand' | 'leaf' | 'plain' }) {
  const tones = { brand: 'bg-brand-50 text-brand-800 dark:bg-brand-900/30 dark:text-brand-100', leaf: 'bg-leaf-50 text-leaf-700 dark:bg-leaf-700/20 dark:text-leaf-100', plain: 'bg-line/60 text-ink' }
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-semibold animate-rise', tones[tone])}>
      {children}
      {onRemove && <button onClick={onRemove} aria-label="Remove" className="rounded-full p-0.5 hover:bg-black/10"><X size={14} /></button>}
    </span>
  )
}

export function Segmented<T extends string | number | null>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label?: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
      {options.map(o => (
        <button key={String(o.value)} role="radio" aria-checked={o.value === value} onClick={() => onChange(o.value)}
          className={cn('rounded-full border px-3.5 py-1.5 text-sm font-semibold transition',
            o.value === value ? 'border-brand-500 bg-brand-500 text-white shadow-soft' : 'border-line bg-card hover:border-brand-300')}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title?: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 backdrop-blur-sm sm:items-center sm:p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} onClick={e => e.stopPropagation()}
        className={cn('max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-surface p-5 shadow-2xl animate-rise sm:rounded-3xl', wide ? 'max-w-3xl' : 'max-w-lg')}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-bold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-full p-2 hover:bg-line/60"><X size={20} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

/** Free-text input with autocomplete from a vocabulary; Enter or the + button adds the value. */
export function IngredientInput({ onAdd, vocabulary, placeholder = 'Type an ingredient, e.g. egg' }: { onAdd: (name: string) => void; vocabulary: string[]; placeholder?: string }) {
  const [text, setText] = useState('')
  const q = text.trim().toLowerCase()
  const suggestions = q.length < 1 ? [] : vocabulary.filter(v => v.includes(q)).slice(0, 6)
  const add = (value: string) => { const v = value.trim().toLowerCase(); if (v) { onAdd(v); setText('') } }
  return (
    <div className="relative">
      <Search size={16} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
      <input className="input pl-10 pr-12" value={text} placeholder={placeholder} maxLength={40} aria-label="Add ingredient"
        onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && add(text)} />
      <button onClick={() => add(text)} aria-label="Add" className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-xl bg-brand-500 p-2 text-white"><Plus size={16} /></button>
      {suggestions.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-2xl border border-line bg-card shadow-soft">
          {suggestions.map(s => <li key={s}><button className="w-full px-4 py-2 text-left text-sm hover:bg-brand-50 dark:hover:bg-white/5" onClick={() => add(s)}>{s}</button></li>)}
        </ul>
      )}
    </div>
  )
}

export function Stat({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode }) {
  return (
    <div className="card !p-4">
      <div className="flex items-center justify-between text-muted"><span className="text-xs font-bold uppercase tracking-wider">{label}</span>{icon}</div>
      <div className="mt-1 font-display text-3xl font-bold">{value}</div>
      {hint && <div className="text-xs text-muted">{hint}</div>}
    </div>
  )
}
