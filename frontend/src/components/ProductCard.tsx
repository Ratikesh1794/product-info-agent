import type { Product, Status } from '../types/chat'

const STATUS: Record<Status, { label: string; className: string }> = {
  Active: { label: 'Available', className: 'bg-ok-soft text-ok' },
  Discontinued: { label: 'Discontinued', className: 'bg-stop-soft text-stop' },
  'Temporarily Out of Stock': { label: 'Out of stock', className: 'bg-wait-soft text-wait' },
  'Coming Soon': { label: 'Coming soon', className: 'bg-soon-soft text-soon' },
}

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function ProductCard({ product: p }: { product: Product }) {
  const status = STATUS[p.status]
  return (
    <article className="flex flex-col rounded-xl border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-semibold">{p.model_number}</h3>
          <p className="text-sm text-muted">{p.brand}</p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}>{status.label}</span>
      </div>

      <p className="mt-2 line-clamp-2 text-sm">{p.product_name}</p>

      <div className="mt-auto flex items-baseline gap-3 pt-3 text-sm">
        <span className="text-base font-semibold tabular-nums">{usd.format(p.msrp_usd)}</span>
        {p.voltage_v != null && <span className="text-muted">{p.voltage_v}V</span>}
        {p.avg_rating != null && (
          <span className="text-muted" aria-label={`Rated ${p.avg_rating} out of 5`}>
            ★ {p.avg_rating.toFixed(1)}
          </span>
        )}
      </div>
      {p.available_at.length > 0 && (
        <p className="mt-1 truncate text-xs text-muted" title={p.available_at.join(', ')}>
          Sold at {p.available_at.slice(0, 3).join(', ')}
          {p.available_at.length > 3 && ` and ${p.available_at.length - 3} more`}
        </p>
      )}
    </article>
  )
}
