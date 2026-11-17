import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import type { Recipe, TierId } from '../types'
import RecipeView from '../components/RecipeView'
import { Empty, Skeleton } from '../components/ui'
import { ChefHat } from 'lucide-react'

export default function Shared() {
  const { token } = useParams()
  const [data, setData] = useState<{ title: string; tier: TierId; recipe: Recipe } | null>(null)
  const [missing, setMissing] = useState(false)
  useEffect(() => { api<{ title: string; tier: TierId; recipe: Recipe }>(`/shared/${token}`, { anonymous: true }).then(setData).catch(() => setMissing(true)) }, [token])
  if (missing) return <Empty icon={<ChefHat />} title="This recipe is no longer shared" action={<Link to="/" className="btn-primary">Make your own</Link>} />
  if (!data) return <Skeleton className="h-64" />
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <RecipeView recipe={data.recipe} tier={data.tier} readOnly />
      <div className="card text-center"><p className="font-semibold">Got ingredients but no idea what to cook?</p><Link to="/" className="btn-primary mt-3">Try Snap2Cook</Link></div>
    </div>
  )
}
