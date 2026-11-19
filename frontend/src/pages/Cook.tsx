import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Camera, ImagePlus, Refrigerator, Sparkles, X, ChefHat, Info } from 'lucide-react'
import { ApiError, api, compressImage } from '../api'
import { useStore } from '../store'
import type { Detected, GenerateResponse, PantryItem, Recipe, Saved, ScanResponse } from '../types'
import KitchenSettings from '../components/KitchenSettings'
import RecipeView from '../components/RecipeView'
import DetectedIngredients from '../components/DetectedIngredients'
import { IngredientInput, Skeleton, Spinner, cn } from '../components/ui'

const COOKING_LINES = ['Checking your kitchen rules...', 'Searching the recipe library...', 'Picking the easiest option...', 'Writing the steps...']

export default function Cook() {
  const { prefs, config, toast, refreshMe } = useStore()
  const location = useLocation()
  const [previews, setPreviews] = useState<string[]>([])
  const [items, setItems] = useState<Detected[]>([])
  const [scanning, setScanning] = useState(false)
  const [cooking, setCooking] = useState(false)
  const [line, setLine] = useState(0)
  const [result, setResult] = useState<GenerateResponse | null>(null)
  const [shown, setShown] = useState(0)
  const [saved, setSaved] = useState<Saved | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const camRef = useRef<HTMLInputElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)
  const maxPhotos = config?.max_photos ?? 3

  useEffect(() => {
    const incoming = (location.state as { ingredients?: string[] } | null)?.ingredients
    if (incoming?.length) setItems(prev => merge(prev, incoming.map(name => ({ name, confidence: 1 }))))
  }, [location.state])
  useEffect(() => {
    if (!cooking) return
    const t = setInterval(() => setLine(l => (l + 1) % COOKING_LINES.length), 1800)
    return () => clearInterval(t)
  }, [cooking])

  const merge = (a: Detected[], b: Detected[]) => {
    const map = new Map(a.map(i => [i.name, i]))
    b.forEach(i => { if (!map.has(i.name)) map.set(i.name, i) })
    return [...map.values()]
  }
  const fail = (e: unknown) => { const msg = e instanceof ApiError ? e.message : 'Something went wrong. Please try again.'; setError(msg); toast(msg, 'error') }

  async function onFiles(list: FileList | null) {
    if (!list?.length) return
    const files = [...list].slice(0, maxPhotos)
    if (list.length > maxPhotos) toast(`Only the first ${maxPhotos} photos are used`)
    setError(null); setScanning(true)
    setPreviews(files.map(f => URL.createObjectURL(f)))
    try {
      const form = new FormData()
      for (const f of files) form.append('files', await compressImage(f), 'photo.jpg')
      const res = await api<ScanResponse>('/scan', { form })
      setItems(prev => merge(prev, res.ingredients))
      toast(`Found ${res.ingredients.length} ingredient${res.ingredients.length === 1 ? '' : 's'}`)
      if (res.empty_photos) toast(`${res.empty_photos} photo(s) had no recognisable food`)
    } catch (e) { fail(e) } finally { setScanning(false); if (fileRef.current) fileRef.current.value = ''; if (camRef.current) camRef.current.value = '' }
  }

  async function addPantry() {
    try {
      const pantry = await api<PantryItem[]>('/pantry')
      if (!pantry.length) { toast('Your pantry is empty. Add items on the Pantry tab.'); return }
      setItems(prev => merge(prev, pantry.map(p => ({ name: p.name, confidence: 1 }))))
    } catch (e) { fail(e) }
  }

  async function generate(extra?: string) {
    const list = extra ? merge(items, [{ name: extra, confidence: 1 }]) : items
    if (extra) setItems(list)
    setError(null); setCooking(true); setResult(null); setSaved(null); setShown(0)
    try {
      const res = await api<GenerateResponse>('/recipes/generate', {
        json: { ingredients: list.map(i => i.name), tier: prefs.tier, equipment: prefs.equipment, extras: prefs.tier === 'home' ? prefs.extras : [], diet: prefs.diet, max_time: prefs.maxTime },
      })
      setResult(res); refreshMe()
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
    } catch (e) { fail(e) } finally { setCooking(false) }
  }

  const options: Recipe[] = result?.recipe ? [result.recipe, ...result.alternatives] : []
  const current = options[shown]

  return (
    <div className="space-y-6">
      <section className="py-2 text-center md:py-6">
        <h1 className="text-4xl font-bold leading-tight md:text-5xl">What's in your <span className="text-brand-500">kitchen</span> today?</h1>
        <p className="mx-auto mt-3 max-w-xl text-muted">Snap a photo of what you have. We'll turn it into a recipe you can actually make, with the equipment you actually own.</p>
      </section>

      <KitchenSettings />

      <section className="card space-y-4" aria-labelledby="ing-h">
        <div><h2 id="ing-h" className="text-xl font-bold">2. Show us your ingredients</h2>
          <p className="text-sm text-muted">Up to {maxPhotos} photos. One item per photo works best. You can always edit the list.</p></div>
        <input ref={camRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={e => onFiles(e.target.files)} />
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" onChange={e => onFiles(e.target.files)} />
        <div className="grid grid-cols-2 gap-3">
          <button className="btn-primary !py-4" disabled={scanning} onClick={() => camRef.current?.click()}><Camera size={18} />Take photo</button>
          <button className="btn-soft !py-4" disabled={scanning} onClick={() => fileRef.current?.click()}><ImagePlus size={18} />Upload photos</button>
        </div>
        {previews.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {previews.map((p, i) => <img key={p + i} src={p} alt={`Photo ${i + 1}`} className="h-14 w-14 shrink-0 rounded-xl object-cover" />)}
            <button className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl border border-dashed border-line text-muted" onClick={() => setPreviews([])} aria-label="Clear photos"><X size={18} /></button>
          </div>
        )}
        {scanning && <div className="space-y-2" aria-live="polite"><p className="flex items-center gap-2 text-sm font-semibold text-brand-600"><Spinner />Looking at your food...</p><Skeleton className="h-10" /></div>}
        <DetectedIngredients items={items} onChange={setItems} />
        {items.length === 0 && !scanning && <p className="text-sm text-muted">No ingredients yet. Take a photo or type them in.</p>}
        <IngredientInput vocabulary={config?.vocabulary ?? []} onAdd={name => setItems(prev => merge(prev, [{ name, confidence: 1 }]))} />
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={addPantry}><Refrigerator size={16} />Add my pantry</button>
          {items.length > 0 && <button className="btn-ghost" onClick={() => { setItems([]); setPreviews([]); setResult(null) }}>Clear all</button>}
        </div>
      </section>

      <div className="sticky bottom-20 z-20 md:static">
        <button className="btn-primary w-full !py-4 text-base" disabled={!items.length || cooking || scanning} onClick={() => generate()}>
          {cooking ? <><Spinner />{COOKING_LINES[line]}</> : <><Sparkles size={18} />Get my recipe</>}
        </button>
      </div>
      {error && <div role="alert" className="card flex items-start gap-3 !border-red-300 bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-100"><Info className="mt-0.5 shrink-0" size={18} />{error}</div>}
      {cooking && <div className="space-y-3"><Skeleton className="h-28" /><Skeleton className="h-6 w-2/3" /><Skeleton className="h-6" /><Skeleton className="h-6 w-5/6" /></div>}

      <div ref={resultRef} className="scroll-mt-24 space-y-4">
        {result && !current && (
          <div className="card space-y-3 text-center animate-rise">
            <ChefHat className="mx-auto text-brand-500" size={36} />
            <h3 className="text-xl font-bold">Not quite enough for a proper dish yet</h3>
            <p className="text-sm text-muted">With this kitchen and these ingredients we can't make something good. Add one of these and we'll try again:</p>
            <div className="flex flex-wrap justify-center gap-2">
              {result.suggestions.map(s => <button key={s} onClick={() => generate(s)} className="btn-soft">+ {s}</button>)}
            </div>
          </div>
        )}
        {current && result && (
          <>
            {options.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Recipe options">
                {options.map((r, i) => (
                  <button key={r.title} role="tab" aria-selected={i === shown} onClick={() => { setShown(i); setSaved(null) }}
                    className={cn('shrink-0 rounded-2xl border px-4 py-2 text-left text-sm font-semibold', i === shown ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-line bg-card')}>
                    <span className="block text-[10px] uppercase tracking-wider text-muted">{i === 0 ? 'Best match' : 'Other idea'}</span>{r.title}
                  </button>
                ))}
              </div>
            )}
            <RecipeView key={current.title} recipe={current} tier={prefs.tier} runId={result.run_id} saved={saved} onSaved={setSaved} />
          </>
        )}
      </div>
    </div>
  )
}
