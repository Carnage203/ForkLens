import { useEffect, useState } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity, AlertTriangle, Clock, Star, Users, Zap } from 'lucide-react'
import { adm, type Overview } from './adminApi'
import { Segmented, Skeleton, Stat } from '../../components/ui'

const COLORS = ['#f96a12', '#22a14d', '#3b82f6', '#a855f7', '#eab308', '#ef4444']
const tip = { contentStyle: { background: 'rgb(var(--card))', border: '1px solid rgb(var(--line))', borderRadius: 16, color: 'rgb(var(--ink))' } }
const short = (d: string) => d.slice(5)

function Panel({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) {
  return <div className={`card ${className}`}><h3 className="mb-3 text-base font-bold">{title}</h3><div className="text-muted">{children}</div></div>
}

function Bars({ data, empty = 'No data yet' }: { data: Record<string, number>; empty?: string }) {
  const rows = Object.entries(data).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...rows.map(r => r[1]))
  if (!rows.length) return <p className="text-sm">{empty}</p>
  return <ul className="space-y-2">{rows.map(([k, v]) => (
    <li key={k} className="text-sm"><div className="flex justify-between text-ink"><span className="truncate">{k}</span><b>{v}</b></div>
      <div className="mt-1 h-1.5 rounded-full bg-line"><div className="h-full rounded-full bg-brand-500" style={{ width: `${(v / max) * 100}%` }} /></div></li>))}</ul>
}

export default function OverviewTab() {
  const [days, setDays] = useState(14)
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { setData(null); adm<Overview>(`/overview?days=${days}`).then(setData).catch(e => setError(e.message)) }, [days])
  if (error) return <p className="text-red-600">{error}</p>
  if (!data) return <div className="grid gap-3 md:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
  const r = data.recipes
  const tiers = Object.entries(r.tiers).map(([name, value]) => ({ name, value }))
  const rate = (n: number) => (r.total ? `${Math.round((n / r.total) * 100)}%` : '0%')
  const gen = data.latency['/api/recipes/generate']
  const scan = data.latency['/api/scan']

  return (
    <div className="space-y-5">
      <Segmented value={days} onChange={setDays} label="Range" options={[7, 14, 30, 90].map(d => ({ value: d, label: `${d} days` }))} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Stat label="Users" value={data.users.total} icon={<Users size={16} />} hint={`${data.users.registered} registered`} />
        <Stat label="Active 24h" value={data.users.active_24h} hint={`${data.users.active_7d} in 7d`} />
        <Stat label="Requests" value={data.requests.total} icon={<Activity size={16} />} hint={`${data.requests.rate_limited} rate-limited`} />
        <Stat label="Error rate" value={`${(data.requests.error_rate * 100).toFixed(1)}%`} icon={<AlertTriangle size={16} />} hint={`${data.requests.errors} server errors`} />
        <Stat label="Recipes" value={r.total} icon={<Zap size={16} />} hint={`${rate(r.cache_hits)} cached`} />
        <Stat label="Rating" value={data.feedback.avg || '-'} icon={<Star size={16} />} hint={`${data.feedback.count} votes`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Traffic and errors"><ResponsiveContainer width="100%" height={240}>
          <AreaChart data={data.series}><CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.15} /><XAxis dataKey="day" tickFormatter={short} stroke="currentColor" fontSize={11} /><YAxis stroke="currentColor" fontSize={11} allowDecimals={false} /><Tooltip {...tip} /><Legend />
            <Area dataKey="requests" stroke="#f96a12" fill="#f96a12" fillOpacity={0.2} /><Area dataKey="errors" stroke="#ef4444" fill="#ef4444" fillOpacity={0.25} /></AreaChart></ResponsiveContainer></Panel>
        <Panel title="Product activity"><ResponsiveContainer width="100%" height={240}>
          <BarChart data={data.series}><CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.15} /><XAxis dataKey="day" tickFormatter={short} stroke="currentColor" fontSize={11} /><YAxis stroke="currentColor" fontSize={11} allowDecimals={false} /><Tooltip {...tip} /><Legend />
            <Bar dataKey="scans" fill="#3b82f6" /><Bar dataKey="recipes" fill="#f96a12" /><Bar dataKey="cooked" fill="#22a14d" /><Bar dataKey="new_users" fill="#a855f7" /></BarChart></ResponsiveContainer></Panel>
        <Panel title="Kitchen tiers">{tiers.length ? <ResponsiveContainer width="100%" height={220}><PieChart><Pie data={tiers} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} label>{tiers.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip {...tip} /><Legend /></PieChart></ResponsiveContainer> : <p className="text-sm">No recipes yet</p>}</Panel>
        <Panel title="Top ingredients"><Bars data={Object.fromEntries(data.top_ingredients.map(i => [i.name, i.count]))} /></Panel>
        <Panel title="Latency (successful calls)">
          <table className="w-full text-sm text-ink"><thead className="text-left text-xs text-muted"><tr><th>Endpoint</th><th>p50</th><th>p95</th><th>n</th></tr></thead><tbody>
            {[['Scan photo', scan], ['Generate recipe', gen]].map(([name, v]) => { const x = v as typeof scan; return <tr key={name as string} className="border-t border-line"><td className="py-2">{name as string}</td><td>{x?.p50 ?? 0} ms</td><td>{x?.p95 ?? 0} ms</td><td>{x?.count ?? 0}</td></tr> })}</tbody></table>
          <div className="mt-4 grid grid-cols-2 gap-3 text-ink"><div><p className="text-xs text-muted">Scans today (quota)</p><b className="text-xl">{data.quota_today.scan}</b></div><div><p className="text-xs text-muted">Generations today</p><b className="text-xl">{data.quota_today.generation}</b></div></div>
        </Panel>
        <Panel title="AI providers"><div className="grid gap-4 sm:grid-cols-2"><div><p className="mb-2 text-xs font-bold uppercase">Vision</p><Bars data={data.vision_models} /></div><div><p className="mb-2 text-xs font-bold uppercase">Generation</p><Bars data={r.gen_models} /></div></div>
          <p className="mt-3 flex items-center gap-2 text-sm"><Clock size={14} />Fallback recipes: <b className="text-ink">{r.fallback}</b> - No dish possible: <b className="text-ink">{r.no_recipe}</b></p></Panel>
        <Panel title="Busiest endpoints"><table className="w-full text-sm text-ink"><thead className="text-left text-xs text-muted"><tr><th>Path</th><th>Calls</th><th>Avg</th><th>5xx</th></tr></thead><tbody>
          {data.endpoints.map(e => <tr key={e.path} className="border-t border-line"><td className="py-1.5 font-mono text-xs">{e.path}</td><td>{e.count}</td><td>{e.avg_ms} ms</td><td className={e.errors ? 'font-bold text-red-600' : ''}>{e.errors}</td></tr>)}</tbody></table></Panel>
        <Panel title="Where users are"><Bars data={Object.fromEntries(data.countries.map(c => [c.country, c.users]))} empty="Country appears once deployed on Vercel" /></Panel>
      </div>
    </div>
  )
}
