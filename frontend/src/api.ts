/** Thin fetch wrapper: client id for guests, bearer token for signed-in users, one error shape. */

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public retryAfter?: number) { super(message) }
}

let tokenProvider: () => Promise<string | null> = async () => null
export const setTokenProvider = (fn: () => Promise<string | null>) => { tokenProvider = fn }

export function clientId(): string {
  try {
    let id = localStorage.getItem('s2c_client')
    if (!id) { id = crypto.randomUUID().replace(/-/g, ''); localStorage.setItem('s2c_client', id) }
    return id
  } catch { return 'anonymous-session-' + Math.random().toString(36).slice(2, 12) }
}

interface Options { method?: string; json?: unknown; form?: FormData; signal?: AbortSignal; anonymous?: boolean }

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = { 'X-Client-Id': clientId() }
  if (!opts.anonymous) {
    const token = await tokenProvider()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  let body: BodyInit | undefined
  if (opts.json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.json) }
  else if (opts.form) body = opts.form
  let res: Response
  try {
    res = await fetch(`/api${path}`, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body, signal: opts.signal, credentials: 'same-origin' })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, 'network', 'Cannot reach the server. Check your connection and try again.')
  }
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const err = data?.error
    throw new ApiError(res.status, err?.code ?? 'error', err?.message ?? 'Something went wrong. Please try again.', err?.retry_after)
  }
  return data as T
}

/** Downscale + re-encode a photo in the browser so uploads stay small (Vercel caps request bodies at 4.5 MB). */
export async function compressImage(file: File, maxSide = 1024, quality = 0.82): Promise<Blob> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  bitmap.close()
  return new Promise((resolve, reject) => canvas.toBlob(b => (b ? resolve(b) : reject(new Error('compress failed'))), 'image/jpeg', quality))
}
