export type Status = 'Active' | 'Discontinued' | 'Temporarily Out of Stock' | 'Coming Soon'

/** Product card payload from the backend `products` event. */
export interface Product {
  model_number: string
  product_name: string
  brand: string
  category: string
  msrp_usd: number
  status: Status
  avg_rating: number | null
  available_at: string[]
  voltage_v: number | null
}

/** One catalog lookup the agent made while answering. */
export interface ToolStep {
  name: string
  args: string
  summary?: string
  ms?: number
}

/** SSE events streamed by POST /api/chat (mirrors backend app/services/agent.py). */
export type AgentEvent =
  | { type: 'token'; text: string }
  | { type: 'tool_call'; name: string; args: string }
  | { type: 'tool_result'; name: string; ms: number; summary: string }
  | { type: 'products'; items: Product[] }
  | { type: 'error'; message: string }
  | { type: 'done' }

export interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  products: Product[]
  steps: ToolStep[]
  error?: string
  pending?: boolean
  stopped?: boolean
}

export interface SessionSummary {
  id: string
  title: string
  updated_at: string
}

export interface RelatedProduct {
  model_number: string
  product_name: string
  status: Status
  msrp_usd: number
}

/** GET /api/products/:model (backend app/schemas/product.py). */
export interface ProductDetail extends Omit<Product, 'category'> {
  sku: string
  category: string
  subcategory: string
  product_type: string
  product_line: string
  launch_date: string | null
  discontinued_date: string | null
  short_description: string
  long_description: string
  key_features: string[]
  whats_in_the_box: string[]
  power_source: string | null
  battery_platform: string | null
  battery_included: boolean | null
  motor_type: string | null
  weight_lbs: number | null
  dimensions_in: string | null
  compatible_with: string[]
  specs: Record<string, string | number | boolean>
  warranty: string | null
  review_count: number | null
  replacement: RelatedProduct | null
  replaces: RelatedProduct[]
}
