import type { AgentEvent, Message, ProductDetail, SessionSummary } from '../types/chat'

const API = import.meta.env.VITE_API_URL ?? '/api'
const KEY = 'product-assistant.client-id'

let memoryId: string | null = null

/** Anonymous id for this browser: scopes which conversations it can list. Falls back to memory if storage is blocked. */
function clientId(): string {
  try {
    let id = localStorage.getItem(KEY)
    if (!id) localStorage.setItem(KEY, (id = crypto.randomUUID()))
    return id
  } catch {
    return (memoryId ??= crypto.randomUUID())
  }
}

const headers = (extra: Record<string, string> = {}) => ({ 'X-Client-Id': clientId(), ...extra })

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`Request failed (HTTP ${res.status}).`)
  return res.json() as Promise<T>
}

/** POST a message and feed each SSE event to onEvent. (EventSource can't POST, so the stream is parsed by hand.) */
export async function streamChat(
  sessionId: string,
  message: string,
  onEvent: (ev: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API}/chat`, {
    method: 'POST',
    headers: headers({ 'content-type': 'application/json' }),
    body: JSON.stringify({ session_id: sessionId, message }),
    signal,
  })
  if (res.status === 422) throw new Error('That message can’t be sent. Keep it under 2,000 characters.')
  if (res.status === 404) throw new Error('This conversation no longer exists. Start a new one.')
  if (!res.ok || !res.body) throw new Error(`The assistant isn’t reachable (HTTP ${res.status}). Check that the backend is running.`)

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += value
    let end: number
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const data = buffer
        .slice(0, end)
        .split('\n')
        .find((line) => line.startsWith('data: '))
      buffer = buffer.slice(end + 2)
      if (data) onEvent(JSON.parse(data.slice(6)) as AgentEvent)
    }
  }
}

export const listSessions = () => fetch(`${API}/sessions`, { headers: headers() }).then(json<SessionSummary[]>)

export class NotFoundError extends Error {}

export const getSession = (id: string) =>
  fetch(`${API}/sessions/${id}`, { headers: headers() }).then((res) => {
    if (res.status === 404) throw new NotFoundError()
    return json<SessionSummary & { messages: Message[] }>(res)
  })

export const deleteSession = (id: string) =>
  fetch(`${API}/sessions/${id}`, { method: 'DELETE', headers: headers() }).then((r) => {
    if (!r.ok && r.status !== 404) throw new Error(`Couldn’t delete (HTTP ${r.status}).`)
  })

const productCache = new Map<string, Promise<ProductDetail>>()

/** Catalog detail for the product modal. Cached per model: catalog data doesn't change while the page is open. */
export function getProduct(model: string): Promise<ProductDetail> {
  const key = model.toUpperCase()
  let p = productCache.get(key)
  if (!p) {
    p = fetch(`${API}/products/${encodeURIComponent(model)}`).then((res) => {
      if (res.status === 404) throw new NotFoundError()
      return json<ProductDetail>(res)
    })
    p.catch(() => productCache.delete(key)) // don't cache failures
    productCache.set(key, p)
  }
  return p
}
