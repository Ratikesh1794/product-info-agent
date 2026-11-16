import { useCallback, useRef, useState } from 'react'
import { getSession, streamChat } from '../api/chat'
import type { AgentEvent, Message } from '../types/chat'

const newId = (): string => crypto.randomUUID()

/** One active conversation. `onSaved` fires after a turn completes (the backend has persisted it). */
export function useChat(onSaved: () => void) {
  const [sessionId, setSessionId] = useState(newId)
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)

  const patch = (id: string, fn: (m: Message) => Message) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? fn(m) : m)))

  const apply = (id: string, ev: AgentEvent) => {
    switch (ev.type) {
      case 'token':
        return patch(id, (m) => ({ ...m, text: m.text + ev.text }))
      case 'tool_call':
        return patch(id, (m) => ({ ...m, steps: [...m.steps, { name: ev.name, args: ev.args }] }))
      case 'tool_result':
        return patch(id, (m) => {
          const i = m.steps.findIndex((s) => s.name === ev.name && s.summary === undefined)
          return { ...m, steps: m.steps.map((s, j) => (j === i ? { ...s, summary: ev.summary, ms: ev.ms } : s)) }
        })
      case 'products':
        return patch(id, (m) => ({ ...m, products: ev.items }))
      case 'error':
        return patch(id, (m) => ({ ...m, error: ev.message }))
    }
  }

  const send = useCallback(
    async (text: string) => {
      const message = text.trim()
      if (busy || loading || !message) return
      const botId = newId()
      setMessages((ms) => [
        ...ms,
        { id: newId(), role: 'user', text: message, products: [], steps: [] },
        { id: botId, role: 'assistant', text: '', products: [], steps: [], pending: true },
      ])
      setBusy(true)
      const controller = new AbortController()
      abort.current = controller
      let ok = false
      try {
        await streamChat(sessionId, message, (ev) => apply(botId, ev), controller.signal)
        ok = true
      } catch (e) {
        if (controller.signal.aborted) patch(botId, (m) => ({ ...m, stopped: true }))
        else patch(botId, (m) => ({ ...m, error: e instanceof Error ? e.message : 'Something went wrong.' }))
      } finally {
        patch(botId, (m) => ({ ...m, pending: false }))
        setBusy(false)
        if (ok) onSaved()
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [busy, loading, sessionId, onSaved],
  )

  const stop = useCallback(() => abort.current?.abort(), [])

  const newChat = useCallback(() => {
    abort.current?.abort()
    setSessionId(newId())
    setMessages([])
    setLoadError(null)
  }, [])

  const open = useCallback(async (id: string) => {
    abort.current?.abort()
    setSessionId(id)
    setMessages([])
    setLoadError(null)
    setLoading(true)
    try {
      setMessages((await getSession(id)).messages)
    } catch {
      setLoadError('This conversation couldn’t be loaded.')
    } finally {
      setLoading(false)
    }
  }, [])

  return { sessionId, messages, busy, loading, loadError, send, stop, newChat, open }
}
