import { useCallback, useEffect, useState } from 'react'
import { deleteSession, listSessions } from '../api/chat'
import type { SessionSummary } from '../types/chat'

export function useSessions() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setSessions(await listSessions())
      setError(null)
    } catch {
      setError('History is unavailable right now.')
    }
  }, [])

  const remove = useCallback(async (id: string) => {
    setSessions((s) => s.filter((x) => x.id !== id)) // optimistic
    try {
      await deleteSession(id)
    } catch {
      void refresh()
    }
  }, [refresh])

  useEffect(() => {
    let live = true
    listSessions()
      .then((s) => live && setSessions(s))
      .catch(() => live && setError('History is unavailable right now.'))
    return () => {
      live = false
    }
  }, [])

  return { sessions, error, refresh, remove }
}
