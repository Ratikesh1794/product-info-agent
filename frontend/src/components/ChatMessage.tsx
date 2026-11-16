import { useState } from 'react'
import Markdown from 'react-markdown'
import type { Message } from '../types/chat'
import { ProductCard } from './ProductCard'
import { Sources } from './Sources'
import { STEP_PROGRESS } from './steps'

const md = {
  p: (props: object) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
  ul: (props: object) => <ul className="my-2 list-disc space-y-1 pl-5 marker:text-line-strong" {...props} />,
  ol: (props: object) => <ol className="my-2 list-decimal space-y-1 pl-5 marker:text-muted" {...props} />,
  strong: (props: object) => <strong className="font-semibold" {...props} />,
  a: (props: object) => <span {...props} />, // catalog URLs are fake: never render links
}

const VISIBLE_CARDS = 4

export function ChatMessage({ message, onOpenProduct }: { message: Message; onOpenProduct: (model: string) => void }) {
  const [allCards, setAllCards] = useState(false)

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[80%] rounded-2xl rounded-br-md bg-brand px-4 py-2.5 whitespace-pre-wrap text-white">
          {message.text}
        </p>
      </div>
    )
  }

  const running = message.steps.at(-1)
  const cards = allCards ? message.products : message.products.slice(0, VISIBLE_CARDS)
  return (
    <div className="space-y-4" aria-busy={message.pending}>
      {message.pending && !message.text && (
        <p className="flex items-center gap-2 text-muted">
          <span aria-hidden className="size-2 rounded-full bg-brand motion-safe:animate-pulse" />
          {running ? `${STEP_PROGRESS[running.name] ?? 'Working'}…` : 'Thinking…'}
        </p>
      )}

      {message.text && (
        <div className="max-w-[70ch]">
          <Markdown components={md}>{message.text}</Markdown>
        </div>
      )}

      {message.error && (
        <p role="alert" className="rounded-lg border border-stop/30 bg-stop-soft px-3 py-2 text-sm text-stop">
          {message.error}
        </p>
      )}
      {message.stopped && <p className="text-sm text-muted">You stopped this answer.</p>}

      {message.products.length > 0 && (
        <section aria-label="Products mentioned">
          <div className="grid gap-3 sm:grid-cols-2">
            {cards.map((p) => (
              <ProductCard key={p.model_number} product={p} onOpen={onOpenProduct} />
            ))}
          </div>
          {message.products.length > VISIBLE_CARDS && (
            <button
              type="button"
              onClick={() => setAllCards((v) => !v)}
              className="mt-2 rounded text-sm font-medium text-brand hover:text-brand-strong"
            >
              {allCards ? 'Show fewer products' : `Show all ${message.products.length} products`}
            </button>
          )}
        </section>
      )}

      {!message.pending && message.steps.length > 0 && <Sources steps={message.steps} />}
    </div>
  )
}
