import type { ToolStep } from '../types/chat'
import { STEP_LABEL } from './steps'

function pretty(args: string): string {
  try {
    return JSON.stringify(JSON.parse(args), null, 2)
  } catch {
    return args
  }
}

/** Collapsed by default: the catalog lookups behind an answer, with the exact filters used. */
export function Sources({ steps }: { steps: ToolStep[] }) {
  const ms = steps.reduce((sum, s) => sum + (s.ms ?? 0), 0)
  return (
    <details className="group text-sm">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded text-muted hover:text-ink">
        <svg aria-hidden viewBox="0 0 16 16" className="size-3.5 transition-transform group-open:rotate-90 motion-reduce:transition-none">
          <path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
        Based on {steps.length} catalog {steps.length === 1 ? 'lookup' : 'lookups'}
      </summary>
      <ol className="mt-2 space-y-2 border-l border-line pl-4">
        {steps.map((s, i) => (
          <li key={i}>
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-medium">{STEP_LABEL[s.name] ?? s.name}</span>
              {s.summary && <span className="text-muted">{s.summary}</span>}
              {s.ms != null && <span className="text-xs text-muted tabular-nums">{s.ms} ms</span>}
            </div>
            <pre className="mt-1 overflow-x-auto rounded-md bg-sidebar px-3 py-2 font-mono text-xs leading-relaxed">
              {s.name}({pretty(s.args)})
            </pre>
          </li>
        ))}
      </ol>
      {ms > 0 && <p className="mt-2 pl-4 text-xs text-muted">{ms} ms in the catalog in total</p>}
    </details>
  )
}
