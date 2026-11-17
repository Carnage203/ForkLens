import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Session, SupabaseClient } from '@supabase/supabase-js'
import { api, setTokenProvider } from './api'
import type { AppConfig } from './types'

interface AuthCtx {
  enabled: boolean
  email: string | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<{ needsConfirmation: boolean }>
  google: () => Promise<void>
  signOut: () => Promise<void>
}

const Ctx = createContext<AuthCtx | null>(null)
export const useAuth = () => useContext(Ctx)!

/** Supabase Auth is optional: without keys the app runs fully in guest mode. The SDK is loaded lazily. */
export function AuthProvider({ config, children, onChange }: { config: AppConfig | null; children: ReactNode; onChange: () => void }) {
  const client = useRef<SupabaseClient | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const enabled = !!config?.auth.enabled

  useEffect(() => {
    if (!config) return
    if (!enabled) { setLoading(false); return }
    let unsub: (() => void) | undefined
    import('@supabase/supabase-js').then(async ({ createClient }) => {
      const sb = createClient(config.auth.url, config.auth.anon_key, { auth: { persistSession: true, autoRefreshToken: true } })
      client.current = sb
      setTokenProvider(async () => (await sb.auth.getSession()).data.session?.access_token ?? null)
      const { data } = await sb.auth.getSession()
      setSession(data.session)
      setLoading(false)
      const sub = sb.auth.onAuthStateChange((event, next) => {
        setSession(next)
        if (event === 'SIGNED_IN') api('/me/claim', { method: 'POST' }).catch(() => undefined).finally(onChange)
      })
      unsub = () => sub.data.subscription.unsubscribe()
    })
    return () => unsub?.()
  }, [config, enabled, onChange])

  const need = useCallback(() => { if (!client.current) throw new Error('Sign-in is not available right now.'); return client.current }, [])
  const value = useMemo<AuthCtx>(() => ({
    enabled, loading, email: session?.user.email ?? null,
    signIn: async (email, password) => { const { error } = await need().auth.signInWithPassword({ email, password }); if (error) throw error },
    signUp: async (email, password) => {
      const { data, error } = await need().auth.signUp({ email, password, options: { emailRedirectTo: location.origin } })
      if (error) throw error
      return { needsConfirmation: !data.session }
    },
    google: async () => { const { error } = await need().auth.signInWithOAuth({ provider: 'google', options: { redirectTo: location.origin } }); if (error) throw error },
    signOut: async () => { await need().auth.signOut(); onChange() },
  }), [enabled, loading, session, need, onChange])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
