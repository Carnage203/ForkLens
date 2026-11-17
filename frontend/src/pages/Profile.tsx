import { useState, type FormEvent } from 'react'
import { Award, BookOpen, ChefHat, Flame, LogOut, Mail } from 'lucide-react'
import { useAuth } from '../auth'
import { useStore } from '../store'
import { Spinner, Stat } from '../components/ui'

export default function Profile() {
  const { me, config, toast } = useStore()
  const auth = useAuth()
  const [mode, setMode] = useState<'in' | 'up'>('in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true)
    try {
      if (mode === 'in') { await auth.signIn(email, password); toast('Welcome back!') }
      else { const r = await auth.signUp(email, password); toast(r.needsConfirmation ? 'Check your email to confirm your account' : 'Account created') }
    } catch (err) { toast((err as Error).message, 'error') } finally { setBusy(false) }
  }
  const stats = me?.stats

  return (
    <div className="space-y-6">
      <div><h1 className="text-3xl font-bold">{me?.kind === 'user' ? `Hi${me.name ? ', ' + me.name.split(' ')[0] : ''}!` : 'Your kitchen stats'}</h1>
        <p className="text-muted">{me?.kind === 'user' ? me.email : 'You are using Snap2Cook as a guest. Sign in to sync your cookbook across devices.'}</p></div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Cook points" value={stats?.points ?? 0} icon={<Award size={16} />} hint="10 per meal cooked" />
        <Stat label="Day streak" value={stats?.streak ?? 0} icon={<Flame size={16} />} hint="Cook on consecutive days" />
        <Stat label="Meals cooked" value={stats?.cooked ?? 0} icon={<ChefHat size={16} />} />
        <Stat label="Saved recipes" value={stats?.saved ?? 0} icon={<BookOpen size={16} />} />
      </div>
      {me && <p className="text-xs text-muted">Recipe limit: {me.generation_limit} per {config?.limits.window_minutes} minutes{me.kind === 'guest' && ' (higher when signed in)'}.</p>}

      {auth.enabled && me?.kind === 'guest' && (
        <form onSubmit={submit} className="card max-w-md space-y-3">
          <h2 className="text-xl font-bold">{mode === 'in' ? 'Sign in' : 'Create your account'}</h2>
          <p className="text-sm text-muted">Everything you saved as a guest on this device moves into your account.</p>
          <label className="block"><span className="label">Email</span><input className="input" type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} /></label>
          <label className="block"><span className="label">Password</span><input className="input" type="password" required minLength={8} autoComplete={mode === 'in' ? 'current-password' : 'new-password'} value={password} onChange={e => setPassword(e.target.value)} /></label>
          <button className="btn-primary w-full" disabled={busy}>{busy ? <Spinner /> : <Mail size={16} />}{mode === 'in' ? 'Sign in' : 'Sign up'}</button>
          <button type="button" className="btn-ghost w-full" onClick={() => auth.google().catch(err => toast(err.message, 'error'))}>Continue with Google</button>
          <button type="button" className="w-full text-center text-sm text-brand-600 underline" onClick={() => setMode(mode === 'in' ? 'up' : 'in')}>
            {mode === 'in' ? 'New here? Create an account' : 'Have an account? Sign in'}</button>
        </form>
      )}
      {!auth.enabled && me?.kind === 'guest' && <p className="card max-w-md text-sm text-muted">Accounts are not enabled on this deployment. Your data is stored against this browser.</p>}
      {me?.kind === 'user' && <button className="btn-ghost" onClick={() => auth.signOut()}><LogOut size={16} />Sign out</button>}
    </div>
  )
}
