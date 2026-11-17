import { useCallback, useEffect, useState } from 'react'
import { Bookmark, Clock, History as HistoryIcon, Trash2, ChefHat } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useStore } from '../store'
import type { HistoryItem, Recipe, Saved, TierId } from '../types'
import RecipeView from '../components/RecipeView'
import { tierLabel } from '../components/KitchenSettings'
import { Empty, Modal, Segmented, Skeleton } from '../components/ui'

interface Open { recipe: Recipe; tier: TierId; saved: Saved | null }

export default function Library() {
  const { toast } = useStore()
  const [tab, setTab] = useState<'saved' | 'history'>('saved')
  const [saved, setSaved] = useState<Saved[] | null>(null)
  const [history, setHistory] = useState<HistoryItem[] | null>(null)
  const [open, setOpen] = useState<Open | null>(null)

  const load = useCallback(() => {
    api<Saved[]>('/saved').then(setSaved).catch(e => toast(e.message, 'error'))
    api<HistoryItem[]>('/history').then(setHistory).catch(e => toast(e.message, 'error'))
  }, [toast])
  useEffect(load, [load])

  const clearHistory = async () => { await api('/history', { method: 'DELETE' }); setHistory([]); toast('History cleared') }
  const list = tab === 'saved' ? saved : history
  const bySaved = (title: string) => saved?.find(s => s.title === title) ?? null

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-bold">Your cookbook</h1>
        <Segmented value={tab} onChange={setTab} label="Library tab" options={[{ value: 'saved', label: `Saved${saved ? ` (${saved.length})` : ''}` }, { value: 'history', label: 'History' }]} />
      </div>
      {list === null && <div className="grid gap-3 sm:grid-cols-2"><Skeleton className="h-28" /><Skeleton className="h-28" /></div>}
      {tab === 'saved' && saved?.length === 0 && <Empty icon={<Bookmark />} title="Nothing saved yet" hint="Tap Save on any recipe to keep it here, even across devices once you sign in." action={<Link to="/" className="btn-primary">Find a recipe</Link>} />}
      {tab === 'history' && history?.length === 0 && <Empty icon={<HistoryIcon />} title="No history yet" hint="Every recipe we make for you shows up here." action={<Link to="/" className="btn-primary">Cook something</Link>} />}
      <div className="grid gap-3 sm:grid-cols-2">
        {tab === 'saved' && saved?.map(s => (
          <button key={s.id} onClick={() => setOpen({ recipe: s.recipe, tier: s.tier, saved: s })} className="card text-left transition hover:-translate-y-0.5 hover:shadow-soft">
            <h3 className="text-lg font-bold">{s.title}</h3>
            <p className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted"><span className="flex items-center gap-1"><Clock size={12} />{s.recipe.time_min} min</span><span>{tierLabel(s.tier)}</span>
              {s.cooked_count > 0 && <span className="flex items-center gap-1 text-leaf-600"><ChefHat size={12} />Cooked {s.cooked_count}x</span>}</p>
          </button>
        ))}
        {tab === 'history' && history?.map(h => (
          <button key={h.id} onClick={() => setOpen({ recipe: h.recipe, tier: h.tier, saved: bySaved(h.recipe.title) })} className="card text-left transition hover:-translate-y-0.5 hover:shadow-soft">
            <h3 className="text-lg font-bold">{h.recipe.title}</h3>
            <p className="mt-1 text-xs text-muted">{new Date(h.ts + 'Z').toLocaleString()} - {tierLabel(h.tier)}</p>
            <p className="mt-2 line-clamp-1 text-xs text-muted">From: {h.ingredients.join(', ')}</p>
          </button>
        ))}
      </div>
      {tab === 'history' && !!history?.length && <button className="btn-danger" onClick={clearHistory}><Trash2 size={16} />Clear history</button>}
      <Modal open={!!open} onClose={() => { setOpen(null); load() }} wide>
        {open && <RecipeView recipe={open.recipe} tier={open.tier} saved={open.saved} onSaved={s => setOpen(o => (o ? { ...o, saved: s } : o))} />}
      </Modal>
    </div>
  )
}
