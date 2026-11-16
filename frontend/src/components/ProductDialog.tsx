import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getProduct, NotFoundError } from '../api/chat'
import { date, specLabel, specValue, usd } from '../lib/format'
import type { ProductDetail, RelatedProduct } from '../types/chat'
import { StatusPill } from './ProductCard'

interface Props {
  model: string
  onClose: () => void
  onOpen: (model: string) => void // jump to a related product (replacement / replaces)
}

type State = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; p: ProductDetail }

/** Native <dialog>: focus trap, Esc to close and inert background come from the browser. */
export function ProductDialog({ model, onClose, onOpen }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    const d = ref.current
    if (d && !d.open) d.showModal()
  }, [])

  useEffect(() => {
    let live = true
    getProduct(model)
      .then((p) => live && setState({ kind: 'ready', p }))
      .catch((e) =>
        live && setState({ kind: 'error', message: e instanceof NotFoundError ? `${model} isn’t in the catalog.` : 'Product details couldn’t be loaded.' }),
      )
    return () => {
      live = false
    }
  }, [model])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && ref.current?.close()} // click on the backdrop
      aria-labelledby="product-title"
      className="m-auto max-h-[min(88vh,52rem)] w-[min(46rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-line bg-surface p-0 text-ink shadow-2xl backdrop:bg-ink/40"
    >
      <div className="flex max-h-[inherit] flex-col">
        <header className="flex items-start gap-4 border-b border-line px-6 py-4">
          <div className="min-w-0 flex-1">
            {state.kind === 'ready' ? (
              <>
                <p className="text-sm text-muted">
                  {state.p.brand} · {state.p.subcategory}
                </p>
                <h2 id="product-title" className="text-xl font-semibold">{state.p.model_number}</h2>
                <p className="mt-0.5">{state.p.product_name}</p>
              </>
            ) : (
              <h2 id="product-title" className="text-xl font-semibold">{model}</h2>
            )}
          </div>
          <button
            type="button"
            onClick={() => ref.current?.close()}
            aria-label="Close"
            className="-mr-2 rounded-lg p-2 text-muted hover:bg-sidebar hover:text-ink"
          >
            <svg aria-hidden viewBox="0 0 16 16" className="size-4">
              <path d="M3.5 3.5l9 9m0-9l-9 9" stroke="currentColor" strokeWidth="1.6" />
            </svg>
          </button>
        </header>

        <div className="overflow-y-auto px-6 py-5">
          {state.kind === 'loading' && <p className="text-muted">Loading product details…</p>}
          {state.kind === 'error' && <p role="alert">{state.message}</p>}
          {state.kind === 'ready' && <Body p={state.p} onOpen={onOpen} />}
        </div>
      </div>
    </dialog>
  )
}

function Body({ p, onOpen }: { p: ProductDetail; onOpen: (m: string) => void }) {
  const facts: [string, ReactNode][] = [
    ['Voltage', p.voltage_v ? `${p.voltage_v}V` : null],
    ['Battery platform', p.battery_platform],
    ['Battery included', p.battery_included == null ? null : p.battery_included ? 'Yes' : 'No'],
    ['Power source', p.power_source],
    ['Motor', p.motor_type],
    ['Weight', p.weight_lbs != null ? `${p.weight_lbs} lbs` : null],
    ['Dimensions', p.dimensions_in ? `${p.dimensions_in} in` : null],
    ['Warranty', p.warranty],
    ['Launched', date(p.launch_date)],
    ['Discontinued', date(p.discontinued_date)],
    ['SKU', p.sku],
  ]
  const specs = Object.entries(p.specs)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span>
          <span className="text-2xl font-semibold tabular-nums">{usd.format(p.msrp_usd)}</span>
          <span className="ml-1.5 text-sm text-muted">MSRP</span>
        </span>
        <StatusPill status={p.status} />
        {p.avg_rating != null && (
          <span className="text-sm text-muted">
            ★ {p.avg_rating.toFixed(1)}
            {p.review_count ? ` (${p.review_count.toLocaleString('en-US')} reviews)` : ''}
          </span>
        )}
      </div>

      {p.replacement && (
        <Related label="Replaced by" product={p.replacement} onOpen={onOpen} tone="notice" />
      )}
      {p.status === 'Discontinued' && !p.replacement && (
        <p className="rounded-lg bg-stop-soft px-3 py-2 text-sm text-stop">Discontinued. No replacement is listed in the catalog.</p>
      )}

      <p className="max-w-[70ch]">{p.long_description || p.short_description}</p>

      {p.key_features.length > 0 && (
        <Section title="Key features">
          <ul className="list-disc space-y-1 pl-5 marker:text-line-strong">
            {p.key_features.map((f) => <li key={f}>{f}</li>)}
          </ul>
        </Section>
      )}

      {specs.length > 0 && (
        <Section title="Technical specifications">
          <Table rows={specs.map(([k, v]) => {
            const { label, unit } = specLabel(k)
            return [label, specValue(v, unit)]
          })} />
        </Section>
      )}

      <Section title="Product details">
        <Table rows={facts.filter((f): f is [string, ReactNode] => f[1] != null && f[1] !== '')} />
      </Section>

      {p.whats_in_the_box.length > 0 && (
        <Section title="In the box">
          <ul className="list-disc space-y-1 pl-5 marker:text-line-strong">
            {p.whats_in_the_box.map((x) => <li key={x}>{x}</li>)}
          </ul>
        </Section>
      )}

      {p.compatible_with.length > 0 && (
        <Section title="Works with">
          <ul className="flex flex-wrap gap-2">
            {p.compatible_with.map((c) => (
              <li key={c} className="rounded-full bg-sidebar px-3 py-1 text-sm">{c}</li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Where to buy">
        <p className="text-sm">
          {p.available_at.join(', ')}
          <span className="text-muted"> · stock isn’t tracked, so check with the retailer.</span>
        </p>
      </Section>

      {p.replaces.length > 0 && (
        <Section title="Replaces">
          <div className="space-y-2">
            {p.replaces.map((r) => <Related key={r.model_number} product={r} onOpen={onOpen} />)}
          </div>
        </Section>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 font-semibold">{title}</h3>
      {children}
    </section>
  )
}

function Table({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 overflow-hidden rounded-lg border border-line text-sm sm:grid-cols-[minmax(10rem,auto)_1fr]">
      {rows.map(([k, v], i) => (
        <div key={k} className={`contents ${i % 2 ? '' : '[&>*]:bg-canvas'}`}>
          <dt className="px-3 pt-2 text-muted sm:py-2">{k}</dt>
          <dd className="px-3 pb-2 sm:py-2">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function Related({ label, product, onOpen, tone }: { label?: string; product: RelatedProduct; onOpen: (m: string) => void; tone?: 'notice' }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(product.model_number)}
      className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm hover:border-brand/50 ${tone === 'notice' ? 'border-wait/30 bg-wait-soft' : 'border-line'}`}
    >
      <span className="min-w-0">
        {label && <span className="font-medium">{label} </span>}
        <span className="font-semibold">{product.model_number}</span>
        <span className="block truncate text-muted">{product.product_name}</span>
      </span>
      <span className="shrink-0 text-right">
        <span className="block font-medium tabular-nums">{usd.format(product.msrp_usd)}</span>
        <StatusPill status={product.status} />
      </span>
    </button>
  )
}
