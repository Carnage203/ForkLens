import { NavLink, Outlet } from 'react-router-dom'
import { ChefHat, Bookmark, Refrigerator, ShoppingBasket, User, Moon, Sun, CheckCircle2, AlertTriangle } from 'lucide-react'
import { useStore } from '../store'
import { cn } from './ui'

const NAV = [
  { to: '/', label: 'Cook', icon: ChefHat },
  { to: '/pantry', label: 'Pantry', icon: Refrigerator },
  { to: '/saved', label: 'Saved', icon: Bookmark },
  { to: '/shopping', label: 'Shopping', icon: ShoppingBasket },
  { to: '/profile', label: 'Me', icon: User },
]

export function Logo() {
  return (
    <span className="flex items-center gap-2 font-display text-xl font-bold">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-500 text-white shadow-soft"><ChefHat size={20} /></span>
      Snap<span className="text-brand-500">2</span>Cook
    </span>
  )
}

export default function Layout() {
  const { dark, toggleDark, toasts, config, configError } = useStore()
  const link = ({ isActive }: { isActive: boolean }) =>
    cn('flex flex-col items-center gap-0.5 rounded-2xl px-3 py-1.5 text-[11px] font-bold md:flex-row md:gap-2 md:px-4 md:py-2 md:text-sm',
      isActive ? 'text-brand-600 md:bg-brand-50 dark:md:bg-brand-900/30' : 'text-muted hover:text-ink')
  return (
    <div className="min-h-screen pb-24 md:pb-10">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <NavLink to="/"><Logo /></NavLink>
          <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
            {NAV.map(n => <NavLink key={n.to} to={n.to} end={n.to === '/'} className={link}><n.icon size={18} />{n.label}</NavLink>)}
          </nav>
          <div className="flex items-center gap-2">
            {config?.mode === 'mock' && <span className="pill !bg-amber-100 !text-amber-800" title="No AI key configured: demo data is used">Demo mode</span>}
            <button onClick={toggleDark} aria-label="Toggle dark mode" className="rounded-full border border-line p-2 hover:bg-line/50">{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
          </div>
        </div>
      </header>
      {configError && <div className="mx-auto mt-4 max-w-5xl px-4"><div className="card flex items-center gap-3 !border-red-300 text-red-700"><AlertTriangle size={18} />{configError}</div></div>}
      <main className="mx-auto max-w-5xl px-4 py-6"><Outlet /></main>
      <footer className="mx-auto hidden max-w-5xl px-4 pb-6 text-center text-xs text-muted md:block">
        ForkLens v{config?.version ?? '2'} - made for students who just want to eat. <NavLink to="/about" className="underline">About</NavLink>
      </footer>
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden" aria-label="Main mobile">
        <div className="mx-auto flex max-w-md justify-around px-2 py-1.5">
          {NAV.map(n => <NavLink key={n.to} to={n.to} end={n.to === '/'} className={link}><n.icon size={22} />{n.label}</NavLink>)}
        </div>
      </nav>
      <div className="pointer-events-none fixed inset-x-0 bottom-24 z-50 flex flex-col items-center gap-2 px-4 md:bottom-8" aria-live="polite">
        {toasts.map(t => (
          <div key={t.id} className={cn('pointer-events-auto flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold text-white shadow-soft animate-rise', t.kind === 'ok' ? 'bg-leaf-600' : 'bg-red-600')}>
            {t.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}{t.text}
          </div>
        ))}
      </div>
    </div>
  )
}
