import { useState } from 'react'
import { Bookmark, BookmarkCheck, Clock, Flame, Share2, Play, Download, ShoppingBasket, ShieldAlert, Lightbulb, ThumbsUp, ThumbsDown, Leaf, Gauge } from 'lucide-react'
import { api } from '../api'
import { useStore } from '../store'
import type { Recipe, Saved, TierId } from '../types'
import { Chip, cn } from './ui'
import CookMode from './CookMode'

export function recipeText(r: Recipe): string {
  return [r.title.toUpperCase(), `Time: ${r.time_min} minutes`, '', 'You will use: ' + r.ingredients_used.join(', '),
    ...(r.extra_needed.length ? ['You also need: ' + r.extra_needed.join(', ')] : []), '', 'Steps:',
    ...r.steps.map((s, i) => `${i + 1}. ${s}`), ...(r.substitutions.length ? ['', 'Tips:', ...r.substitutions.map(s => '- ' + s)] : []),
    '', 'Safety: ' + r.safety_note, '', 'Made with ForkLens'].join('\n')
}

interface Props { recipe: Recipe; tier: TierId; runId?: string; saved?: Saved | null; onSaved?: (s: Saved | null) => void; readOnly?: boolean }

export default function RecipeView({ recipe, tier, runId, saved, onSaved, readOnly }: Props) {
  const { toast, refreshMe } = useStore()
  const [cooking, setCooking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [rated, setRated] = useState<number | null>(null)
  const meta = recipe.meta

  const run = async (fn: () => Promise<void>) => { setBusy(true); try { await fn() } catch (e) { toast((e as Error).message, 'error') } finally { setBusy(false) } }
  const toggleSave = () => run(async () => {
    if (saved) { await api(`/saved/${saved.id}`, { method: 'DELETE' }); onSaved?.(null); toast('Removed from saved') }
    else { const s = await api<Saved>('/saved', { json: { recipe, tier } }); onSaved?.(s); toast('Saved to your cookbook'); refreshMe() }
  })
  const share = () => run(async () => {
    const s = saved ?? await api<Saved>('/saved', { json: { recipe, tier } })
    onSaved?.(s)
    const withToken = s.share_token ? s : await api<Saved>(`/saved/${s.id}/share`, { json: { enabled: true } })
    onSaved?.(withToken)
    const url = `${location.origin}/r/${withToken.share_token}`
    if (navigator.share) { await navigator.share({ title: recipe.title, url }).catch(() => undefined) }
    else { await navigator.clipboard.writeText(url); toast('Link copied') }
  })
  const addMissing = () => run(async () => { await api('/shopping', { json: { names: recipe.extra_needed, source: recipe.title } }); toast('Added to shopping list') })
  const download = () => {
    const url = URL.createObjectURL(new Blob([recipeText(recipe)], { type: 'text/plain' }))
    Object.assign(document.createElement('a'), { href: url, download: `${recipe.title.replace(/\W+/g, '-').toLowerCase()}.txt` }).click()
    URL.revokeObjectURL(url)
  }
  const rate = (rating: number) => run(async () => { await api('/feedback', { json: { rating, run_id: runId, category: 'recipe' } }); setRated(rating); toast('Thanks for the feedback!') })

  return (
    <article className="card animate-rise !p-0 overflow-hidden">
      <div className="bg-gradient-to-br from-brand-500 to-brand-700 p-6 text-white">
        <h2 className="text-3xl font-bold leading-tight">{recipe.title}</h2>
        <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
          <span className="flex items-center gap-1 rounded-full bg-white/20 px-3 py-1"><Clock size={13} />{recipe.time_min} min</span>
          {meta && <span className="flex items-center gap-1 rounded-full bg-white/20 px-3 py-1"><Flame size={13} />{meta.calories} kcal</span>}
          {meta && <span className="flex items-center gap-1 rounded-full bg-white/20 px-3 py-1"><Gauge size={13} />{meta.difficulty}</span>}
          {meta && <span className="flex items-center gap-1 rounded-full bg-white/20 px-3 py-1"><Leaf size={13} />{meta.diet} - {meta.cuisine}</span>}
        </div>
      </div>
      <div className="space-y-6 p-6">
        {!readOnly && (
          <div className="flex flex-wrap gap-2">
            <button className="btn-primary" onClick={() => setCooking(true)}><Play size={16} />Start cooking</button>
            <button className="btn-ghost" disabled={busy} onClick={toggleSave}>{saved ? <BookmarkCheck size={16} className="text-brand-500" /> : <Bookmark size={16} />}{saved ? 'Saved' : 'Save'}</button>
            <button className="btn-ghost" disabled={busy} onClick={share}><Share2 size={16} />Share</button>
            <button className="btn-ghost" onClick={download}><Download size={16} />.txt</button>
          </div>
        )}
        <section>
          <span className="label">You will use</span>
          <div className="flex flex-wrap gap-2">{recipe.ingredients_used.map(i => <Chip key={i} tone="leaf">{i}</Chip>)}</div>
          {recipe.extra_needed.length > 0 && (
            <div className="mt-4 rounded-2xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-900/20 dark:text-amber-100">
              <b>You will also need:</b> {recipe.extra_needed.join(', ')}
              {!readOnly && <button className="ml-3 inline-flex items-center gap-1 font-bold underline" onClick={addMissing}><ShoppingBasket size={14} />Add to list</button>}
            </div>
          )}
        </section>
        <section>
          <span className="label">Steps</span>
          <ol className="space-y-3">
            {recipe.steps.map((step, i) => (
              <li key={i} className="flex gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-500 text-xs font-bold text-white">{i + 1}</span>
                <p className="pt-0.5 leading-relaxed">{step}</p>
              </li>
            ))}
          </ol>
        </section>
        {recipe.substitutions.length > 0 && (
          <section className="rounded-2xl bg-brand-50 p-4 dark:bg-brand-900/20">
            <span className="label flex items-center gap-1.5"><Lightbulb size={13} />Tips and swaps</span>
            <ul className="list-disc space-y-1 pl-5 text-sm">{recipe.substitutions.map(s => <li key={s}>{s}</li>)}</ul>
          </section>
        )}
        <section className="flex gap-3 rounded-2xl border border-line p-4 text-sm"><ShieldAlert className="mt-0.5 shrink-0 text-red-500" size={18} /><p><b>Safety:</b> {recipe.safety_note}</p></section>
        {!readOnly && runId && (
          <div className="flex items-center justify-between border-t border-line pt-4 text-sm">
            <span className="text-muted">Was this recipe helpful?</span>
            <div className="flex gap-2">
              {[{ v: 5, i: ThumbsUp }, { v: 1, i: ThumbsDown }].map(({ v, i: Icon }) => (
                <button key={v} disabled={rated !== null || busy} onClick={() => rate(v)} aria-label={v === 5 ? 'Helpful' : 'Not helpful'}
                  className={cn('rounded-full border border-line p-2.5 hover:bg-brand-50', rated === v && 'bg-brand-500 text-white')}><Icon size={16} /></button>
              ))}
            </div>
          </div>
        )}
      </div>
      {cooking && <CookMode recipe={recipe} tier={tier} saved={saved ?? null} onSaved={s => onSaved?.(s)} onClose={() => setCooking(false)} />}
    </article>
  )
}
