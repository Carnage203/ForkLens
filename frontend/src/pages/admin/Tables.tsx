import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import { adm, type Page } from './adminApi'
import { Skeleton, cn } from '../../components/ui'

const PAGE = 25
const time = (iso: string) => new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })

function Table<T>({ path, columns, filters, rowKey }: { path: string; columns: { head: string; cell: (r: T) => ReactNode }[]; filters?: ReactNode; rowKey: (r: T) => string | number }) {
  const [page, setPage] = useState(0)
  const [data, setData] = useState<Page<T> | null>(null)
  const [error, setError] = useState('')
  const sep = path.includes('?') ? '&' : '?'
  const load = useCallback(() => { setError(''); adm<Page<T>>(`${path}${sep}limit=${PAGE}&offset=${page * PAGE}`).then(setData).catch(e => setError(e.message)) }, [path, sep, page])
  useEffect(load, [load])
  useEffect(() => setPage(0), [path])
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">{filters}<button className="btn-ghost ml-auto !py-2" onClick={load}><RefreshCw size={14} />Refresh</button></div>
      {error && <p className="text-red-600">{error}</p>}
      {!data ? <Skeleton className="h-48" /> : (
        <div className="card overflow-x-auto !p-0">
          <table className="w-full min-w-[640px] text-sm"><thead className="bg-line/40 text-left text-xs uppercase tracking-wider text-muted"><tr>{columns.map(c => <th key={c.head} className="px-3 py-2.5">{c.head}</th>)}</tr></thead>
            <tbody>{data.rows.map(r => <tr key={rowKey(r)} className="border-t border-line align-top">{columns.map(c => <td key={c.head} className="px-3 py-2">{c.cell(r)}</td>)}</tr>)}
              {!data.rows.length && <tr><td colSpan={columns.length} className="px-3 py-8 text-center text-muted">Nothing here yet</td></tr>}</tbody></table>
        </div>
      )}
      <div className="flex items-center justify-between text-sm text-muted"><span>{data?.total ?? 0} total</span>
        <div className="flex items-center gap-2"><button className="btn-ghost !p-2" disabled={page === 0} onClick={() => setPage(p => p - 1)} aria-label="Previous"><ChevronLeft size={16} /></button>
          <span>{page + 1} / {pages}</span><button className="btn-ghost !p-2" disabled={page + 1 >= pages} onClick={() => setPage(p => p + 1)} aria-label="Next"><ChevronRight size={16} /></button></div></div>
    </div>
  )
}

const status = (s: number) => <span className={cn('rounded-md px-1.5 py-0.5 font-mono text-xs font-bold', s >= 500 ? 'bg-red-100 text-red-700' : s >= 400 ? 'bg-amber-100 text-amber-800' : 'bg-leaf-50 text-leaf-700')}>{s}</span>
const mono = (s: string | null) => <span className="font-mono text-xs">{s ?? '-'}</span>

interface Req { id: number; ts: string; request_id: string; method: string; path: string; status: number; ms: number; owner: string | null; error: string | null }
export function RequestsTab() {
  const [filter, setFilter] = useState('all')
  const [path, setPath] = useState('')
  const min = filter === 'errors' ? 500 : filter === 'failed' ? 400 : 0
  return <Table<Req> path={`/requests?min_status=${min}&path=${encodeURIComponent(path)}`} rowKey={r => r.id}
    filters={<><select className="input !w-auto !py-2" value={filter} onChange={e => setFilter(e.target.value)} aria-label="Status filter"><option value="all">All</option><option value="failed">4xx and 5xx</option><option value="errors">5xx only</option></select>
      <input className="input !w-48 !py-2" placeholder="Filter path..." value={path} onChange={e => setPath(e.target.value)} /></>}
    columns={[{ head: 'Time', cell: r => time(r.ts) }, { head: 'Request', cell: r => <><b>{r.method}</b> <span className="font-mono text-xs">{r.path}</span></> }, { head: 'Status', cell: r => status(r.status) },
      { head: 'ms', cell: r => r.ms }, { head: 'Owner', cell: r => mono(r.owner?.slice(0, 14) ?? null) }, { head: 'Id', cell: r => mono(r.request_id) }, { head: 'Error', cell: r => <span className="text-xs text-red-600">{r.error ?? ''}</span> }]} />
}

interface User { id: string; kind: string; email: string | null; name: string | null; country: string | null; created: string; last_seen: string; requests: number; recipes: number; saved: number }
export function UsersTab() {
  const [kind, setKind] = useState('')
  return <Table<User> path={`/users?kind=${kind}`} rowKey={u => u.id}
    filters={<select className="input !w-auto !py-2" value={kind} onChange={e => setKind(e.target.value)} aria-label="Kind"><option value="">All</option><option value="user">Registered</option><option value="guest">Guests</option></select>}
    columns={[{ head: 'Who', cell: u => <><b>{u.email ?? u.name ?? (u.kind === 'guest' ? 'Guest' : 'User')}</b><br />{mono(u.id.slice(0, 18))}</> }, { head: 'Kind', cell: u => u.kind }, { head: 'Country', cell: u => u.country ?? '-' },
      { head: 'Requests', cell: u => u.requests }, { head: 'Recipes', cell: u => u.recipes }, { head: 'Saved', cell: u => u.saved }, { head: 'Joined', cell: u => time(u.created) }, { head: 'Last seen', cell: u => time(u.last_seen) }]} />
}

interface Run { id: string; ts: string; tier: string; diet: string; ingredients: string[]; title: string | null; ms: number; model: string | null; fallback: boolean; cache: boolean }
export function RunsTab() {
  return <Table<Run> path="/runs" rowKey={r => r.id} columns={[{ head: 'Time', cell: r => time(r.ts) }, { head: 'Recipe', cell: r => r.title ?? <i className="text-muted">no dish possible</i> },
    { head: 'Ingredients', cell: r => <span className="text-xs">{r.ingredients.join(', ')}</span> }, { head: 'Kitchen', cell: r => `${r.tier} / ${r.diet}` }, { head: 'ms', cell: r => r.ms },
    { head: 'Model', cell: r => mono(r.cache ? 'cache' : r.model ?? 'verbatim') }, { head: 'Flags', cell: r => (r.fallback ? 'fallback' : '') }]} />
}

interface Fb { id: number; ts: string; rating: number; category: string; comment: string; owner: string }
export function FeedbackTab() {
  return <Table<Fb> path="/feedback" rowKey={r => r.id} columns={[{ head: 'Time', cell: r => time(r.ts) }, { head: 'Rating', cell: r => '★'.repeat(r.rating) + '☆'.repeat(5 - r.rating) },
    { head: 'Type', cell: r => r.category }, { head: 'Comment', cell: r => r.comment || <span className="text-muted">-</span> }, { head: 'Owner', cell: r => mono(r.owner.slice(0, 14)) }]} />
}
