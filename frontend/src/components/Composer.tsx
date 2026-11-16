import { useState, type FormEvent, type KeyboardEvent } from 'react'

const LIMIT = 2000

interface Props {
  busy: boolean
  disabled?: boolean
  onSend: (text: string) => void
  onStop: () => void
}

export function Composer({ busy, disabled, onSend, onStop }: Props) {
  const [text, setText] = useState('')
  const tooLong = text.length > LIMIT

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (busy || disabled || !text.trim() || tooLong) return
    onSend(text)
    setText('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) submit(e)
  }

  return (
    <form
      onSubmit={submit}
      className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 shadow-sm focus-within:border-brand/60"
    >
      <label htmlFor="question" className="sr-only">
        Ask about a product
      </label>
      <textarea
        id="question"
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask about a tool, accessory or battery…"
        className="field-sizing-content max-h-48 min-h-10 flex-1 resize-none bg-transparent px-3 py-2 outline-none placeholder:text-muted focus-visible:outline-none"
      />
      {text.length > LIMIT * 0.9 && (
        <span className={`self-center text-xs tabular-nums ${tooLong ? 'text-stop' : 'text-muted'}`}>{LIMIT - text.length}</span>
      )}
      {busy ? (
        <button
          type="button"
          onClick={onStop}
          className="h-10 rounded-xl border border-line-strong px-4 font-medium hover:bg-sidebar"
        >
          Stop
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !text.trim() || tooLong}
          aria-label="Send"
          className="grid size-10 place-items-center rounded-xl bg-brand text-white hover:bg-brand-strong disabled:bg-line-strong"
        >
          <svg aria-hidden viewBox="0 0 16 16" className="size-4">
            <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
          </svg>
        </button>
      )}
    </form>
  )
}
