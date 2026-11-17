import { Link } from 'react-router-dom'
import { Camera, Database, Filter, Sparkles, ShieldCheck } from 'lucide-react'

const STEPS = [
  { icon: Camera, title: 'Vision', text: 'A vision model (Groq, Gemini or OpenRouter, whichever answers first) lists what is in your photo. You can correct it.' },
  { icon: Filter, title: 'Kitchen rules', text: 'Hostel, PG or Home decides which recipes are even allowed: equipment, techniques, diet and time are hard filters.' },
  { icon: Database, title: 'Retrieval', text: 'Semantic search over a curated recipe library, then a reranker scores how much of each recipe you can really make.' },
  { icon: Sparkles, title: 'Grounded writing', text: 'An LLM adapts the best matches. Its answer is validated: no invented ingredients, no techniques your kitchen cannot do.' },
  { icon: ShieldCheck, title: 'Safe by design', text: 'Every recipe carries a safety note. If nothing sensible can be made, we say so and suggest the one cheapest thing to add.' },
]

export default function About() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="space-y-3"><h1 className="text-4xl font-bold">Cooking for people <span className="text-brand-500">without a kitchen</span></h1>
        <p className="text-lg text-muted">Most recipe apps assume a full kitchen. Snap2Cook treats your kitchen as an input, so a hostel student with only a kettle gets kettle-safe recipes, and an honest answer when there are none.</p></div>
      <div className="grid gap-3 sm:grid-cols-2">
        {STEPS.map(s => <div key={s.title} className="card"><s.icon className="text-brand-500" /><h3 className="mt-2 text-lg font-bold">{s.title}</h3><p className="text-sm text-muted">{s.text}</p></div>)}
      </div>
      <Link to="/" className="btn-primary">Start cooking</Link>
    </div>
  )
}
