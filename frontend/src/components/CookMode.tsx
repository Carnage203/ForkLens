import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Pause, Play, Timer, Volume2, VolumeX, X, PartyPopper } from 'lucide-react'
import { api } from '../api'
import { useStore } from '../store'
import type { Recipe, Saved, TierId } from '../types'
import { cn } from './ui'

/** First duration mentioned in a step ("boil for 3-4 minutes" -> 240 s). Uses the upper bound of a range. */
export function parseSeconds(step: string): number | null {
  const m = step.match(/(\d+)(?:\s*(?:-|to)\s*(\d+))?\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b/i)
  if (!m) return null
  const n = Number(m[2] ?? m[1])
  const unit = m[3].toLowerCase()
  return n * (unit.startsWith('h') ? 3600 : unit.startsWith('m') ? 60 : 1)
}

function beep() {
  try {
    const ctx = new AudioContext()
    ;[0, 0.35, 0.7].forEach(t => {
      const osc = ctx.createOscillator(); const gain = ctx.createGain()
      osc.frequency.value = 880; gain.gain.value = 0.2
      osc.connect(gain).connect(ctx.destination); osc.start(ctx.currentTime + t); osc.stop(ctx.currentTime + t + 0.2)
    })
  } catch { /* audio unavailable */ }
}

interface Props { recipe: Recipe; tier: TierId; saved: Saved | null; onSaved: (s: Saved) => void; onClose: () => void }

/** Full-screen, hands-free friendly cooking: big text, per-step timers, read-aloud and screen wake lock. */
export default function CookMode({ recipe, tier, saved, onSaved, onClose }: Props) {
  const { toast, refreshMe } = useStore()
  const [index, setIndex] = useState(0)
  const [voice, setVoice] = useState(false)
  const [left, setLeft] = useState<number | null>(null)
  const [running, setRunning] = useState(false)
  const done = index >= recipe.steps.length
  const lock = useRef<WakeLockSentinel | null>(null)
  const seconds = done ? null : parseSeconds(recipe.steps[index])

  useEffect(() => {
    navigator.wakeLock?.request('screen').then(l => { lock.current = l }).catch(() => undefined)
    return () => { lock.current?.release().catch(() => undefined); speechSynthesis?.cancel() }
  }, [])
  useEffect(() => { setLeft(null); setRunning(false) }, [index])
  useEffect(() => {
    if (voice && !done && 'speechSynthesis' in window) {
      speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(`Step ${index + 1}. ${recipe.steps[index]}`))
    }
  }, [voice, index, done, recipe.steps])
  useEffect(() => {
    if (!running || left === null) return
    if (left <= 0) { setRunning(false); beep(); toast('Timer done!'); return }
    const t = setTimeout(() => setLeft(l => (l ?? 1) - 1), 1000)
    return () => clearTimeout(t)
  }, [running, left, toast])

  const finish = useCallback(async () => {
    try {
      const s = saved ?? await api<Saved>('/saved', { json: { recipe, tier } })
      onSaved(s)
      await api(`/saved/${s.id}/cooked`, { method: 'POST' })
      toast('Nice! +10 cook points'); refreshMe(); onClose()
    } catch (e) { toast((e as Error).message, 'error') }
  }, [saved, recipe, tier, onSaved, onClose, toast, refreshMe])

  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-surface animate-rise" role="dialog" aria-modal="true" aria-label={`Cooking ${recipe.title}`}>
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div><p className="text-xs font-bold uppercase tracking-wider text-muted">Cooking</p><h2 className="text-lg font-bold">{recipe.title}</h2></div>
        <div className="flex gap-2">
          <button className="btn-ghost !p-2.5" onClick={() => setVoice(v => !v)} aria-label="Toggle read aloud">{voice ? <Volume2 size={18} /> : <VolumeX size={18} />}</button>
          <button className="btn-ghost !p-2.5" onClick={onClose} aria-label="Close cooking mode"><X size={18} /></button>
        </div>
      </div>
      <div className="h-1.5 bg-line"><div className="h-full bg-brand-500 transition-all" style={{ width: `${(Math.min(index, recipe.steps.length) / recipe.steps.length) * 100}%` }} /></div>
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 px-6 py-8">
        {done ? (
          <div className="text-center">
            <PartyPopper size={56} className="mx-auto text-brand-500" />
            <h3 className="mt-4 text-3xl font-bold">Enjoy your meal!</h3>
            <p className="mt-2 text-muted">Tap below to log it. Cooking on consecutive days builds your streak.</p>
            <button className="btn-primary mt-6 !px-8 !py-3.5 text-base" onClick={finish}>I cooked it</button>
          </div>
        ) : (
          <>
            <p className="text-sm font-bold text-brand-600">Step {index + 1} of {recipe.steps.length}</p>
            <p className="font-display text-3xl font-semibold leading-snug md:text-4xl">{recipe.steps[index]}</p>
            {seconds && (
              <div className="flex items-center gap-3 rounded-2xl border border-line bg-card p-4">
                <Timer className="text-brand-500" />
                <span className="font-display text-3xl font-bold tabular-nums">{mmss(left ?? seconds)}</span>
                <button className="btn-soft ml-auto" onClick={() => { if (left === null) setLeft(seconds); setRunning(r => !r) }}>
                  {running ? <><Pause size={16} />Pause</> : <><Play size={16} />{left === null ? 'Start timer' : 'Resume'}</>}
                </button>
              </div>
            )}
          </>
        )}
      </div>
      {!done && (
        <div className="grid grid-cols-2 gap-3 border-t border-line p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
          <button className={cn('btn-ghost !py-4', index === 0 && 'invisible')} onClick={() => setIndex(i => i - 1)}><ChevronLeft />Back</button>
          <button className="btn-primary !py-4" onClick={() => setIndex(i => i + 1)}>{index === recipe.steps.length - 1 ? 'Finish' : 'Next'}<ChevronRight /></button>
        </div>
      )}
    </div>
  )
}
