import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from './api'
import { AuthProvider } from './auth'
import type { AppConfig, Me, Prefs } from './types'

const DEFAULT_PREFS: Prefs = { tier: 'hostel', equipment: [], extras: [], diet: 'any', maxTime: null }
interface Toast { id: number; text: string; kind: 'ok' | 'error' }

interface Store {
  config: AppConfig | null
  configError: string | null
  prefs: Prefs
  setPrefs: (p: Partial<Prefs>) => void
  me: Me | null
  refreshMe: () => void
  dark: boolean
  toggleDark: () => void
  toast: (text: string, kind?: 'ok' | 'error') => void
  toasts: Toast[]
}

const Ctx = createContext<Store | null>(null)
export const useStore = () => useContext(Ctx)!

function load<T>(key: string, fallback: T): T {
  try { const raw = localStorage.getItem(key); return raw ? { ...fallback, ...JSON.parse(raw) } : fallback } catch { return fallback }
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)
  const [prefs, setPrefsState] = useState<Prefs>(() => load('s2c_prefs', DEFAULT_PREFS))
  const [me, setMe] = useState<Me | null>(null)
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => { api<AppConfig>('/config', { anonymous: true }).then(setConfig).catch(e => setConfigError(e.message)) }, [])
  const refreshMe = useCallback(() => { api<Me>('/me').then(setMe).catch(() => setMe(null)) }, [])
  useEffect(() => { if (config) refreshMe() }, [config, refreshMe])

  const setPrefs = useCallback((p: Partial<Prefs>) => {
    setPrefsState(prev => { const next = { ...prev, ...p }; try { localStorage.setItem('s2c_prefs', JSON.stringify(next)) } catch { /* private mode */ } return next })
  }, [])
  const toggleDark = useCallback(() => {
    setDark(prev => {
      document.documentElement.classList.toggle('dark', !prev)
      try { localStorage.setItem('s2c_theme', prev ? 'light' : 'dark') } catch { /* private mode */ }
      return !prev
    })
  }, [])
  const toast = useCallback((text: string, kind: 'ok' | 'error' = 'ok') => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, text, kind }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3800)
  }, [])

  const value = useMemo(() => ({ config, configError, prefs, setPrefs, me, refreshMe, dark, toggleDark, toast, toasts }),
    [config, configError, prefs, setPrefs, me, refreshMe, dark, toggleDark, toast, toasts])
  return (
    <Ctx.Provider value={value}>
      <AuthProvider config={config} onChange={refreshMe}>{children}</AuthProvider>
    </Ctx.Provider>
  )
}
