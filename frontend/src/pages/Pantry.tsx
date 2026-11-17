import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CalendarClock, Refrigerator, Sparkles } from 'lucide-react'
import { api } from '../api'
import { useStore } from '../store'
import type { PantryItem } from '../types'
import { Chip, Empty, IngredientInput, Skeleton, cn } from '../components/ui'

const daysLeft = (iso: string | null) => (iso ? Math.ceil((new Date(iso + 'T23:59:59').getTime() - Date.now()) / 86_400_000) : null)

export default function Pantry() {
  const { config, toast } = useStore()
  const navigate = useNavigate()
  const [items, setItems] = useState<PantryItem[] | null>(null)

  useEffect(() => { api<PantryItem[]>('/pantry').then(setItems).catch(e => toast(e.message, 'error')) }, [toast])
  const save = async (next: PantryItem[]) => {
    setItems(next)
    try { setItems(await api<PantryItem[]>('/pantry', { method: 'PUT', json: { items: next } })) } catch (e) { toast((e as Error).message, 'error') }
  }
  const add = (name: string) => items && !items.some(i => i.name === name) && save([...items, { name, use_by: null }])
  const setDate = (name: string, use_by: string) => items && save(items.map(i => (i.name === name ? { ...i, use_by: use_by || null } : i)))
  const expiring = (items ?? []).filter(i => { const d = daysLeft(i.use_by); return d !== null && d <= 3 })

  return (
    <div className="space-y-5">
      <div><h1 className="text-3xl font-bold">My pantry</h1><p className="text-muted">Keep what you own here. Add use-by dates and we'll nudge you to cook with the ones about to expire.</p></div>
      <div className="card space-y-4"><IngredientInput vocabulary={config?.vocabulary ?? []} onAdd={add} placeholder="Add something you have at home" /></div>
      {items === null && <Skeleton className="h-32" />}
      {items?.length === 0 && <Empty icon={<Refrigerator />} title="Your pantry is empty" hint="Add the staples you keep around. You can pull them into any recipe search with one tap." />}
      {expiring.length > 0 && (
        <div className="card flex flex-wrap items-center justify-between gap-3 !border-amber-300 bg-amber-50 dark:bg-amber-900/20">
          <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">Use soon: {expiring.map(e => e.name).join(', ')}</p>
          <button className="btn-primary" onClick={() => navigate('/', { state: { ingredients: expiring.map(e => e.name) } })}><Sparkles size={16} />Cook with these</button>
        </div>
      )}
      {!!items?.length && (
        <div className="card space-y-2">
          {items.map(i => {
            const d = daysLeft(i.use_by)
            return (
              <div key={i.name} className="flex flex-wrap items-center gap-3 border-b border-line py-2 last:border-0">
                <Chip tone="plain" onRemove={() => save(items.filter(x => x.name !== i.name))}>{i.name}</Chip>
                <label className="ml-auto flex items-center gap-2 text-xs text-muted"><CalendarClock size={14} />Use by
                  <input type="date" value={i.use_by ?? ''} onChange={e => setDate(i.name, e.target.value)} className="rounded-xl border border-line bg-card px-2 py-1 text-xs" /></label>
                {d !== null && <span className={cn('pill', d <= 0 && '!bg-red-100 !text-red-700')}>{d < 0 ? 'Expired' : d === 0 ? 'Today' : `${d}d left`}</span>}
              </div>
            )
          })}
        </div>
      )}
      {!!items?.length && <button className="btn-primary" onClick={() => navigate('/', { state: { ingredients: items.map(i => i.name) } })}><Sparkles size={16} />Cook with my pantry</button>}
    </div>
  )
}
