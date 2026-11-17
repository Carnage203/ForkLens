export type TierId = 'hostel' | 'pg' | 'home'
export type Diet = 'any' | 'veg' | 'vegan' | 'egg' | 'non-veg'

export interface AppConfig {
  version: string
  mode: 'live' | 'mock'
  max_photos: number
  extras: string[]
  vocabulary: string[]
  diets: Diet[]
  time_options: number[]
  limits: { guest_per_window: number; user_per_window: number; window_minutes: number }
  auth: { enabled: boolean; url: string; anon_key: string }
}

export interface Recipe {
  title: string
  time_min: number
  ingredients_used: string[]
  extra_needed: string[]
  techniques_used: string[]
  steps: string[]
  substitutions: string[]
  safety_note: string
  source_recipe_ids: string[]
  meta?: { calories: number; cuisine: string; diet: string; difficulty: string } | null
}

export interface Detected { name: string; confidence: number }
export interface ScanResponse { ingredients: Detected[]; empty_photos: number; model: string | null; latency_ms: number }

export interface GenerateResponse {
  run_id: string
  recipe: Recipe | null
  alternatives: Recipe[]
  suggestions: string[]
  fallback_used: boolean
  mode: string
  latency_ms: number
  cache_hits: { recipe: boolean; query_embedding: boolean }
  scores: Record<string, number>
  timings: Record<string, number>
}

export interface Saved { id: string; title: string; tier: TierId; recipe: Recipe; cooked_count: number; created_at: string; share_token: string | null }
export interface HistoryItem { id: string; ts: string; tier: TierId; diet: Diet; ingredients: string[]; recipe: Recipe }
export interface PantryItem { name: string; use_by: string | null }
export interface ShoppingItem { id: string; name: string; checked: boolean; source: string | null }
export interface Me {
  kind: 'user' | 'guest'; email: string | null; name: string | null
  stats: { saved: number; cooked: number; recipes: number; streak: number; points: number }
  generation_limit: number
}

export interface Prefs { tier: TierId; equipment: string[]; extras: string[]; diet: Diet; maxTime: number | null }
