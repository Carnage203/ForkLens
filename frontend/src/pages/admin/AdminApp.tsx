import { useEffect, useState, type FormEvent } from 'react'
import { Activity, Cog, Lock, LogOut, MessageSquare, ScrollText, Users, UtensilsCrossed } from 'lucide-react'
import { ApiError } from '../../api'
import { Spinner, cn } from '../../components/ui'
import { Logo } from '../../components/Layout'
import { adm } from './adminApi'
import OverviewTab from './Overview'
import { FeedbackTab, RequestsTab, RunsTab, UsersTab } from './Tables'
import SystemTab from './System'

const TABS = [
  { id: 'overview', label: 'Overview', icon: Activity, view: <OverviewTab /> },
  { id: 'requests', label: 'Requests', icon: ScrollText, view: <RequestsTab /> },
  { id: 'users', label: 'Users', icon: Users, view: <UsersTab /> },
  { id: 'runs', label: 'Recipes', icon: UtensilsCrossed, view: <RunsTab /> },
  { id: 'feedback', label: 'Feedback', icon: MessageSquare, view: <FeedbackTab /> },
  { id: 'system', label: 'System', icon: Cog, view: <SystemTab /> },
]

function Login({ onDone }: { onDone: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError('')
    try { await adm('/login', { username, password }); onDone() }
    catch (err) { setError(err instanceof ApiError && err.status === 429 ? 'Too many attempts. Try again later.' : 'Invalid credentials.') }
    finally { setBusy(false) }
  }
  return (
    <div className="grid min-h-[70vh] place-items-center">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4">
        <Logo /><h1 className="flex items-center gap-2 text-xl font-bold"><Lock size={18} />Operations console</h1>
        <input className="input" placeholder="Username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required />
        <input className="input" type="password" placeholder="Password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
        {error && <p role="alert" className="text-sm font-semibold text-red-600">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? <Spinner /> : 'Sign in'}</button>
      </form>
    </div>
  )
}

export default function AdminApp() {
  const [state, setState] = useState<'checking' | 'out' | 'in'>('checking')
  const [tab, setTab] = useState('overview')
  const check = () => adm('/session').then(() => setState('in')).catch(() => setState('out'))
  useEffect(() => { check() }, [])
  useEffect(() => { const meta = Object.assign(document.createElement('meta'), { name: 'robots', content: 'noindex,nofollow' }); document.head.appendChild(meta); return () => { meta.remove() } }, [])
  if (state === 'checking') return <div className="grid min-h-[60vh] place-items-center"><Spinner className="h-8 w-8" /></div>
  if (state === 'out') return <Login onDone={check} />
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-3xl font-bold">Operations console</h1>
        <button className="btn-ghost" onClick={() => adm('/logout', {}).finally(() => setState('out'))}><LogOut size={16} />Sign out</button></div>
      <div className="flex gap-1 overflow-x-auto border-b border-line" role="tablist">
        {TABS.map(t => <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
          className={cn('flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-semibold', tab === t.id ? 'border-brand-500 text-brand-600' : 'border-transparent text-muted hover:text-ink')}><t.icon size={16} />{t.label}</button>)}
      </div>
      {TABS.find(t => t.id === tab)?.view}
    </div>
  )
}
