import { useEffect, useState } from 'react'
import { Check, Copy, ShoppingBasket, Trash2 } from 'lucide-react'
import { api } from '../api'
import { useStore } from '../store'
import type { ShoppingItem } from '../types'
import { Empty, IngredientInput, Skeleton, cn } from '../components/ui'

export default function Shopping() {
  const { config, toast } = useStore()
  const [items, setItems] = useState<ShoppingItem[] | null>(null)
  useEffect(() => { api<ShoppingItem[]>('/shopping').then(setItems).catch(e => toast(e.message, 'error')) }, [toast])

  const add = async (name: string) => { try { setItems(await api<ShoppingItem[]>('/shopping', { json: { names: [name] } })) } catch (e) { toast((e as Error).message, 'error') } }
  const tick = async (item: ShoppingItem) => {
    setItems(prev => prev?.map(i => (i.id === item.id ? { ...i, checked: !i.checked } : i)) ?? prev)
    try { await api(`/shopping/${item.id}`, { method: 'PATCH', json: { checked: !item.checked } }) } catch (e) { toast((e as Error).message, 'error') }
  }
  const clear = async () => { await api('/shopping', { method: 'DELETE' }); setItems(prev => prev?.filter(i => !i.checked) ?? prev); toast('Cleared ticked items') }
  const copy = async () => { await navigator.clipboard.writeText((items ?? []).filter(i => !i.checked).map(i => `- ${i.name}`).join('\n')); toast('List copied') }
  const open = (items ?? []).filter(i => !i.checked).length

  return (
    <div className="space-y-5">
      <div><h1 className="text-3xl font-bold">Shopping list</h1><p className="text-muted">Missing ingredients from your recipes land here. {open > 0 && <b>{open} to buy.</b>}</p></div>
      <div className="card"><IngredientInput vocabulary={config?.vocabulary ?? []} onAdd={add} placeholder="Add an item to buy" /></div>
      {items === null && <Skeleton className="h-32" />}
      {items?.length === 0 && <Empty icon={<ShoppingBasket />} title="Nothing to buy" hint="When a recipe needs something you don't have, tap 'Add to list'." />}
      {!!items?.length && (
        <div className="card !p-2">
          {items.map(i => (
            <button key={i.id} onClick={() => tick(i)} className="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left hover:bg-brand-50/60 dark:hover:bg-white/5">
              <span className={cn('grid h-6 w-6 place-items-center rounded-full border-2', i.checked ? 'border-leaf-600 bg-leaf-600 text-white' : 'border-line')}>{i.checked && <Check size={14} />}</span>
              <span className={cn('font-semibold', i.checked && 'text-muted line-through')}>{i.name}</span>
              {i.source && <span className="ml-auto truncate text-xs text-muted">for {i.source}</span>}
            </button>
          ))}
        </div>
      )}
      {!!items?.length && <div className="flex flex-wrap gap-2"><button className="btn-ghost" onClick={copy}><Copy size={16} />Copy list</button><button className="btn-danger" onClick={clear}><Trash2 size={16} />Remove ticked</button></div>}
    </div>
  )
}
