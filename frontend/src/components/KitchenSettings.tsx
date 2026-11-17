import { Coffee, Flame, Home } from 'lucide-react'
import { useStore } from '../store'
import type { Diet, TierId } from '../types'
import { Chip, Segmented, cn } from './ui'

export const TIERS: { id: TierId; name: string; blurb: string; icon: typeof Home; equipment: string[] }[] = [
  { id: 'hostel', name: 'Hostel', blurb: 'Kettle only', icon: Coffee, equipment: [] },
  { id: 'pg', name: 'PG room', blurb: 'One burner or oven', icon: Flame, equipment: ['gas_stove'] },
  { id: 'home', name: 'Home', blurb: 'Full kitchen', icon: Home, equipment: ['gas_stove'] },
]
const EQUIP_LABEL: Record<string, string> = { gas_stove: 'Gas stove', oven: 'Oven', microwave: 'Microwave' }
const DIET_LABEL: Record<Diet, string> = { any: 'Anything', veg: 'Veg', vegan: 'Vegan', egg: 'Egg', 'non-veg': 'Non-veg' }

export function tierLabel(id: TierId) { return TIERS.find(t => t.id === id)?.name ?? id }

export default function KitchenSettings() {
  const { prefs, setPrefs, config } = useStore()
  const times = [{ value: null as number | null, label: 'Any time' }, ...(config?.time_options ?? [15, 30, 45]).map(t => ({ value: t as number | null, label: `${t} min` }))]
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter(x => x !== v) : [...list, v])
  return (
    <section className="card space-y-5" aria-labelledby="kitchen-h">
      <div>
        <h2 id="kitchen-h" className="text-xl font-bold">1. What is your kitchen like?</h2>
        <p className="text-sm text-muted">We only suggest recipes you can really make with what you have.</p>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:gap-3">
        {TIERS.map(t => (
          <button key={t.id} onClick={() => setPrefs({ tier: t.id, equipment: t.equipment, extras: t.id === 'home' ? prefs.extras : [] })} aria-pressed={prefs.tier === t.id}
            className={cn('flex flex-col items-center gap-1 rounded-2xl border-2 p-3 text-center transition sm:p-4',
              prefs.tier === t.id ? 'border-brand-500 bg-brand-50 shadow-soft dark:bg-brand-900/20' : 'border-line bg-card hover:border-brand-300')}>
            <t.icon className={prefs.tier === t.id ? 'text-brand-500' : 'text-muted'} />
            <span className="text-sm font-bold">{t.name}</span>
            <span className="text-[11px] leading-tight text-muted">{t.blurb}</span>
          </button>
        ))}
      </div>
      {prefs.tier === 'pg' && (
        <div><span className="label">Which one do you have?</span>
          <Segmented label="Appliance" value={prefs.equipment[0] ?? 'gas_stove'} onChange={v => setPrefs({ equipment: [v] })}
            options={['gas_stove', 'oven'].map(v => ({ value: v, label: EQUIP_LABEL[v] }))} /></div>
      )}
      {prefs.tier === 'home' && (
        <>
          <div><span className="label">Equipment</span>
            <div className="flex flex-wrap gap-2">
              {['gas_stove', 'microwave'].map(v => (
                <button key={v} aria-pressed={prefs.equipment.includes(v)} onClick={() => setPrefs({ equipment: toggle(prefs.equipment, v) })}
                  className={cn('rounded-full border px-3.5 py-1.5 text-sm font-semibold', prefs.equipment.includes(v) ? 'border-brand-500 bg-brand-500 text-white' : 'border-line bg-card')}>
                  {EQUIP_LABEL[v]}</button>))}
            </div></div>
          <div><span className="label">Pantry basics you have</span>
            <div className="flex flex-wrap gap-2">
              {(config?.extras ?? []).map(x => (
                <button key={x} aria-pressed={prefs.extras.includes(x)} onClick={() => setPrefs({ extras: toggle(prefs.extras, x) })}>
                  <Chip tone={prefs.extras.includes(x) ? 'brand' : 'plain'}>{prefs.extras.includes(x) ? '✓ ' : ''}{x}</Chip></button>))}
            </div></div>
        </>
      )}
      <div className="grid gap-5 sm:grid-cols-2">
        <div><span className="label">Diet</span>
          <Segmented label="Diet" value={prefs.diet} onChange={v => setPrefs({ diet: v })} options={(config?.diets ?? ['any']).map(d => ({ value: d, label: DIET_LABEL[d] }))} /></div>
        <div><span className="label">Cooking time</span>
          <Segmented label="Max time" value={prefs.maxTime} onChange={v => setPrefs({ maxTime: v })} options={times} /></div>
      </div>
    </section>
  )
}
