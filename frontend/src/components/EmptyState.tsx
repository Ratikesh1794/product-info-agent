import { useMemo } from 'react'

// Each one is checked against the catalog (backend/evals + tool tests); none are the assignment's own questions.
const SUGGESTIONS = [
  { topic: 'Compare', q: 'Compare the GDS18V-75N and GDS18V-190B impact wrenches.' },
  { topic: 'Compatibility', q: 'Which accessories fit my Dremel 4300?' },
  { topic: 'Availability', q: 'The GDS18V-190N was discontinued. What replaced it?' },
  { topic: 'Sizing', q: 'Do the women’s heated vests come in size L?' },
  { topic: 'Batteries', q: 'Which 18V batteries do you have, and what do they cost?' },
  { topic: 'Find a product', q: 'Do you sell 3D printer filament?' },
  { topic: 'Find a product', q: 'I need a green-beam 360° line laser. What are my options?' },
  { topic: 'Kit contents', q: 'What comes in the box with the GSR18V-535CB25?' },
]

/** Keep model numbers like GSR18V-535CB25 from breaking at the hyphen. */
function nowrapModels(q: string) {
  return q.split(/(\b[A-Z]{2,}\d[\w-]*)/).map((part, i) => (i % 2 ? <span key={i} className="whitespace-nowrap">{part}</span> : part))
}

function pick<T>(items: T[], n: number): T[] {
  return [...items].sort(() => Math.random() - 0.5).slice(0, n)
}

export function EmptyState({ seed, onPick }: { seed: string; onPick: (q: string) => void }) {
  // new set per conversation, stable while it's open
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const shown = useMemo(() => pick(SUGGESTIONS, 4), [seed])
  return (
    <div className="mx-auto flex max-w-3xl flex-col justify-center py-12 sm:min-h-full">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">How can I help with your project?</h1>
      <p className="mt-2 max-w-[60ch] text-muted">
        Ask about Bosch, Dremel, RotoZip and CST/berger tools, accessories and batteries. Answers come from the
        product catalog: specs, prices, compatibility, availability and where to buy.
      </p>
      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {shown.map((s) => (
          <button
            key={s.q}
            type="button"
            onClick={() => onPick(s.q)}
            className="flex flex-col items-start rounded-xl border border-line bg-surface p-4 text-left transition-colors hover:border-brand/50 hover:bg-brand-soft/40 motion-reduce:transition-none"
          >
            <span className="text-xs font-medium text-brand">{s.topic}</span>
            <span className="mt-1 block">{nowrapModels(s.q)}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
