# ForkLens

Photo of the food you have in, a recipe that fits your kitchen out. Built for students: **Hostel** (kettle only), **PG** (one appliance) or **Home** (full kitchen).

- **Frontend:** React + TypeScript + Tailwind (Vite), installable PWA
- **Backend:** FastAPI, stateless, runs as a Vercel Python Function
- **Database:** PostgreSQL on Supabase (SQLite locally); shared cache and rate limiting live in the DB
- **AI:** Groq / Gemini / OpenRouter fallback chain for vision and generation, Gemini embeddings, grounded and validated output
- **Features:** photo scan with editable ingredients, kitchen-aware recipes with alternatives, step-by-step cook mode with timers and voice, saved recipes and history, pantry with use-by dates, shopping list, share links, cook points and streaks, guest mode plus optional login, hidden admin console

## Run locally

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env            # fill in what you have; everything is optional locally
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
cd frontend; npm install; npm run dev     # http://localhost:5173
```

Without any keys the app runs in **demo mode** (mock vision, stored recipes) against a local SQLite file.

```powershell
.\.venv\Scripts\python.exe -m pytest -q   # 67 tests, no network
cd frontend; npm run build                # type-check + production build
```

## Deploy (Vercel + Supabase)

1. Create a Supabase project, copy the *transaction pooler* connection string and the API URL / anon key.
2. Push this repo to GitHub and import it in Vercel (settings come from `vercel.json`).
3. Add the variables from `.env.example` in Vercel (Production). Never commit `.env`.
4. Check `https://<your-domain>/api/health`.

The admin console lives at the secret path in `VITE_ADMIN_PATH`; it is not linked anywhere and returns 404 until you sign in with `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

## Layout

`frontend/` React app, `backend/` FastAPI app, `forklens/` framework-free domain core (tiers, RAG pipeline, vision, caches, exceptions, file I/O), `data/` recipe corpus, `api/index.py` Vercel entrypoint, `scripts/` DB init, demo seed, corpus tools, `tests/`.

## Limitations

Free-tier AI quotas (guarded by rate limits and caching), a 90-recipe corpus, vision can misread items (hence the editable list), and the Vercel Python bundle is close to its size limit because of pandas.
