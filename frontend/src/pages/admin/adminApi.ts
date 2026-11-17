import { api } from '../../api'

/** Admin calls rely on the httpOnly session cookie, never on the guest/user identity headers. */
export const adm = <T,>(path: string, json?: unknown, method?: string) => api<T>(`/admin${path}`, { anonymous: true, json, method })

export interface Overview {
  days: number
  users: { total: number; registered: number; new: number; active_24h: number; active_7d: number }
  requests: { total: number; errors: number; rate_limited: number; error_rate: number }
  latency: Record<string, { p50: number; p95: number; count: number }>
  series: { day: string; requests: number; errors: number; scans: number; recipes: number; cooked: number; new_users: number }[]
  quota_today: { scan: number; generation: number }
  recipes: { total: number; tiers: Record<string, number>; diets: Record<string, number>; fallback: number; cache_hits: number; no_recipe: number; gen_models: Record<string, number> }
  vision_models: Record<string, number>
  top_ingredients: { name: string; count: number }[]
  endpoints: { path: string; count: number; avg_ms: number; errors: number }[]
  countries: { country: string; users: number }[]
  feedback: { avg: number; count: number }
}

export interface Page<T> { total: number; rows: T[] }
