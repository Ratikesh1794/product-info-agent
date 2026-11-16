import { useEffect, useRef, useState } from 'react'
import { ChatMessage } from './components/ChatMessage'
import { Composer } from './components/Composer'
import { EmptyState } from './components/EmptyState'
import { Sidebar } from './components/Sidebar'
import { useChat } from './hooks/useChat'
import { useSessions } from './hooks/useSessions'

export default function App() {
  const history = useSessions()
  const chat = useChat(history.refresh)
  const [menu, setMenu] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)

  const title = history.sessions.find((s) => s.id === chat.sessionId)?.title ?? 'New conversation'

  // follow the stream, unless the visitor has scrolled up to read
  useEffect(() => {
    const el = scroller.current
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 200) el.scrollTop = el.scrollHeight
  }, [chat.messages])

  const close = (fn: () => void) => () => {
    fn()
    setMenu(false)
  }

  const sidebar = (
    <Sidebar
      sessions={history.sessions}
      activeId={chat.sessionId}
      error={history.error}
      onNew={close(chat.newChat)}
      onOpen={(id) => close(() => void chat.open(id))()}
      onDelete={(id) => {
        void history.remove(id)
        if (id === chat.sessionId) chat.newChat()
      }}
    />
  )

  return (
    <div className="flex h-full">
      <aside className="hidden w-72 shrink-0 border-r border-line bg-sidebar md:block">{sidebar}</aside>

      {menu && (
        <div className="fixed inset-0 z-20 md:hidden">
          <div aria-hidden className="absolute inset-0 bg-ink/30" onClick={() => setMenu(false)} />
          <aside className="absolute inset-y-0 left-0 w-[min(18rem,85vw)] bg-sidebar shadow-xl">{sidebar}</aside>
        </div>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface px-4">
          <button
            type="button"
            onClick={() => setMenu(true)}
            aria-label="Open conversations"
            className="rounded-md p-1.5 text-muted hover:bg-sidebar md:hidden"
          >
            <svg aria-hidden viewBox="0 0 16 16" className="size-5">
              <path d="M2.5 4h11M2.5 8h11M2.5 12h11" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </button>
          <h1 className="min-w-0 truncate font-medium">{title}</h1>
          <span className="ml-auto hidden text-sm text-muted sm:block">Product assistant</span>
        </header>

        <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-6">
          {chat.loading ? (
            <p className="mx-auto max-w-3xl py-10 text-muted">Loading conversation…</p>
          ) : chat.loadError ? (
            <p role="alert" className="mx-auto max-w-3xl py-10 text-stop">{chat.loadError}</p>
          ) : chat.messages.length === 0 ? (
            <EmptyState seed={chat.sessionId} onPick={(q) => void chat.send(q)} />
          ) : (
            <div role="log" aria-label="Conversation" className="mx-auto max-w-3xl space-y-8 py-8">
              {chat.messages.map((m) => (
                <ChatMessage key={m.id} message={m} />
              ))}
            </div>
          )}
        </div>

        <div className="px-4 pb-4 sm:px-6">
          <div className="mx-auto max-w-3xl">
            <Composer busy={chat.busy} disabled={chat.loading} onSend={(q) => void chat.send(q)} onStop={chat.stop} />
            <p className="mt-2 text-center text-xs text-muted">
              Prices are MSRP. Stock isn’t tracked, so check with the retailer before you go.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
