export const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

// spec key suffix -> unit label, longest first so "_ft_lbs" wins over "_lbs"
const UNITS: [string, string][] = [
  ['_ft_lbs', 'ft-lbs'], ['_in_lbs', 'in-lbs'], ['_rpm', 'rpm'], ['_opm', 'opm'], ['_bpm', 'bpm'], ['_ipm', 'ipm'],
  ['_spm', 'spm'], ['_deg', '°'], ['_in', 'in'], ['_ft', 'ft'], ['_mm', 'mm'], ['_lbs', 'lbs'], ['_kg', 'kg'],
  ['_ah', 'Ah'], ['_wh', 'Wh'], ['_v', 'V'], ['_a', 'A'], ['_w', 'W'], ['_j', 'J'], ['_min', 'min'],
  ['_hours', 'hours'], ['_k', 'K'],
]
const WORDS: Record<string, string> = { ip: 'IP', led: 'LED', usb: 'USB', opm: 'OPM', tpi: 'TPI', sds: 'SDS' }

/** "max_fastening_torque_ft_lbs" -> { label: "Max fastening torque", unit: "ft-lbs" } */
export function specLabel(key: string): { label: string; unit: string } {
  const hit = UNITS.find(([suffix]) => key.endsWith(suffix) && key.length > suffix.length)
  const base = hit ? key.slice(0, -hit[0].length) : key
  const words = base.split('_').map((w) => WORDS[w] ?? w)
  const label = words.join(' ')
  return { label: label.charAt(0).toUpperCase() + label.slice(1), unit: hit?.[1] ?? '' }
}

export function specValue(value: string | number | boolean, unit: string): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  const v = typeof value === 'number' ? value.toLocaleString('en-US') : value
  if (!unit) return v
  return unit === '°' ? `${v}°` : `${v} ${unit}`
}

export function date(iso: string | null): string | null {
  return iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : null
}
