import { useEffect, useState } from 'react'
import { CheckCircle2, Trash2, XCircle } from 'lucide-react'
import { adm } from './adminApi'
import { Skeleton } from '../../components/ui'
import { useStore } from '../../store'

interface System {
  env: string; database: string; mode: string; corpus: string; recipes: number; today: string; now: string
  keys: Record<string, boolean>; models: { vision: string[]; generation: string[] }; rows: Record<string, number>
}

export default function SystemTab() {
  const { toast } = useStore()
  const [data, setData] = useState<System | null>(null)
  useEffect(() => { adm<System>('/system').then(setData).catch(e => toast(e.message, 'error')) }, [toast])
  const purge = async () => { const r = await adm<Record<string, number>>('/purge?days=30', {}); toast(`Deleted ${r.request_logs_deleted} logs, ${r.cache_deleted} cache rows`) }
  if (!data) return <Skeleton className="h-48" />
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="card space-y-2 text-sm"><h3 className="text-base font-bold">Runtime</h3>
        {[['Environment', data.env], ['Database', data.database], ['AI mode', data.mode], ['Corpus', `${data.corpus} (${data.recipes} recipes)`], ['Server time (UTC)', data.now]].map(([k, v]) =>
          <p key={k} className="flex justify-between border-b border-line py-1.5"><span className="text-muted">{k}</span><b>{v}</b></p>)}</div>
      <div className="card space-y-2 text-sm"><h3 className="text-base font-bold">Integrations</h3>
        {Object.entries(data.keys).map(([k, ok]) => <p key={k} className="flex items-center justify-between border-b border-line py-1.5"><span className="capitalize">{k.replace('_', ' ')}</span>
          {ok ? <span className="flex items-center gap-1 font-bold text-leaf-600"><CheckCircle2 size={15} />configured</span> : <span className="flex items-center gap-1 font-bold text-muted"><XCircle size={15} />not set</span>}</p>)}
        <p className="pt-2 text-xs text-muted">Vision chain: {data.models.vision.join(' -> ')}<br />Generation chain: {data.models.generation.join(' -> ')}</p></div>
      <div className="card space-y-2 text-sm"><h3 className="text-base font-bold">Table sizes</h3>
        {Object.entries(data.rows).map(([k, v]) => <p key={k} className="flex justify-between border-b border-line py-1.5"><span className="font-mono text-xs">{k}</span><b>{v}</b></p>)}</div>
      <div className="card space-y-3 text-sm"><h3 className="text-base font-bold">Maintenance</h3>
        <p className="text-muted">A daily cron already trims logs older than 30 days and events older than 90 days. Run it now:</p>
        <button className="btn-danger" onClick={purge}><Trash2 size={16} />Purge old logs and expired cache</button></div>
    </div>
  )
}
