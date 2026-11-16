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
