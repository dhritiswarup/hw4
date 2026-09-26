export interface SizeStock {
  size: string
  quantity: number
}

export interface Product {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  image_url: string
  price: number
  total_stock: number
  sizes_in_stock: string[]
  size_stock: Record<string, number>
}

export interface ProductDetail extends Product {
  inventory: SizeStock[]
}

/** Product card attached to an assistant reply (backend models.ProductCard). */
export interface ProductCardData {
  product_id: string
  name: string
  garment_type: string
  price: number
  image_url: string
  colors: string[]
  sizes_in_stock: string[]
  total_stock: number
}

/** Search results the agent wants shown on the Products page (backend models.PageResults). */
export interface PageResults {
  title: string
  filters: string[]
  products: Product[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  products?: ProductCardData[]
  page_results?: PageResults | null
  suggestions?: string[]
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const fetchProducts = () => getJson<Product[]>('/api/products')

export const fetchProduct = (id: string) =>
  getJson<ProductDetail>(`/api/products/${encodeURIComponent(id)}`)

// ---------- auth (session is an HttpOnly cookie set by the backend) ----------

export interface User {
  id: number
  first_name: string
  last_name: string
  email: string
}

export interface SignupInput {
  first_name: string
  last_name: string
  email: string
  password: string
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
    // FastAPI validation errors: [{loc, msg}, ...]
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((d: { loc: string[]; msg: string }) => `${d.loc[d.loc.length - 1]}: ${d.msg}`)
        .join('; ')
    }
  } catch {
    /* non-JSON error body */
  }
  return `${res.status} ${res.statusText}`
}

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await errorMessage(res))
  return (res.status === 204 ? undefined : await res.json()) as T
}

export const signup = (input: SignupInput) => postJson<User>('/api/auth/signup', input)

export const login = (email: string, password: string) => postJson<User>('/api/auth/login', { email, password })

export const logout = () => postJson<void>('/api/auth/logout')

export async function fetchMe(): Promise<User | null> {
  const res = await fetch('/api/auth/me', { credentials: 'same-origin' })
  return res.ok ? ((await res.json()) as User) : null
}

export const formatPrice = (price: number) => `$${price.toFixed(2)}`

/** First sentence of a description, for product cards. */
export const shortDescription = (text: string) => text.split(/(?<=\.)\s/)[0]

/**
 * Send the latest message to the PydanticAI agent (POST /api/chat).
 * `history` is everything before the latest message; the backend ignores it for logged-in
 * users and uses their saved conversation instead.
 */
export async function sendChatMessage(history: ChatMessage[], page: PageContext): Promise<ChatMessage> {
  const last = history[history.length - 1]
  const prior = history
    .slice(0, -1)
    .slice(-20)
    .map(({ role, content }) => ({ role, content }))
  return postJson<ChatMessage>('/api/chat', { message: last.content, history: prior, page })
}

/** Where the shopper is when they send a message (backend models.PageContext). */
export interface PageContext {
  path: string
  page: 'home' | 'products' | 'product' | 'about' | 'login' | 'signup' | 'other'
  product_id?: string
  results_title?: string
  results_filters?: string[]
  preferred_size?: string
}

/** Saved conversation for the logged-in shopper (empty for guests). */
export const fetchChatHistory = () => getJson<ChatMessage[]>('/api/chat/history')

export async function clearChatHistory(): Promise<void> {
  const res = await fetch('/api/chat/history', { method: 'DELETE', credentials: 'same-origin' })
  if (!res.ok) throw new Error(await errorMessage(res))
}
