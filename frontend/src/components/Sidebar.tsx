import { Link } from 'react-router'
import type { SessionSummary } from '../types/chat'

const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

function ago(iso: string): string {
  const mins = Math.round((Date.parse(iso) - Date.now()) / 60000)
  if (mins > -1) return 'Just now'
  if (mins > -60) return rtf.format(mins, 'minute')
  if (mins > -1440) return rtf.format(Math.round(mins / 60), 'hour')
  return rtf.format(Math.round(mins / 1440), 'day')
}

interface Props {
  sessions: SessionSummary[]
  activeId: string
  error: string | null
  onNavigate: () => void
  onDelete: (id: string) => void
}

export function Sidebar({ sessions, activeId, error, onNavigate, onDelete }: Props) {
  return (
    <nav aria-label="Conversations" className="flex h-full flex-col">
      <div className="p-3">
        <Link
          to="/"
          onClick={onNavigate}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-3 py-2 font-medium text-white hover:bg-brand-strong"
        >
          <svg aria-hidden viewBox="0 0 16 16" className="size-4">
            <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.8" />
          </svg>
          New conversation
        </Link>
      </div>

      <h2 className="px-4 pt-2 pb-1 text-xs font-medium text-muted">History</h2>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {error && <p className="px-2 py-1 text-sm text-muted">{error}</p>}
        {!error && sessions.length === 0 && (
          <p className="px-2 py-1 text-sm text-muted">Your conversations will appear here.</p>
        )}
        <ul className="space-y-0.5">
          {sessions.map((s) => {
            const active = s.id === activeId
            return (
              <li key={s.id} className="group relative">
                <Link
                  to={`/c/${s.id}`}
                  onClick={onNavigate}
                  aria-current={active ? 'page' : undefined}
                  className={`block w-full rounded-lg py-2 pr-9 pl-3 ${active ? 'bg-surface shadow-[0_0_0_1px_var(--color-line)]' : 'hover:bg-surface/60'}`}
                >
                  <span className="block truncate text-sm">{s.title}</span>
                  <span className="block text-xs text-muted">{ago(s.updated_at)}</span>
                </Link>
                <button
                  type="button"
                  onClick={() => onDelete(s.id)}
                  aria-label={`Delete “${s.title}”`}
                  className="absolute top-2 right-2 rounded p-1 text-muted opacity-0 group-hover:opacity-100 hover:bg-line hover:text-ink focus-visible:opacity-100"
                >
                  <svg aria-hidden viewBox="0 0 16 16" className="size-4">
                    <path d="M3 4.5h10M6.5 4.5V3h3v1.5M5 4.5l.6 8.5h4.8l.6-8.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
                  </svg>
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </nav>
  )
}
