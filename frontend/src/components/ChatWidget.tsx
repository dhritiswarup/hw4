import { useEffect, useRef, useState, type FormEvent } from 'react'
import Markdown from 'react-markdown'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  clearChatHistory,
  fetchChatHistory,
  formatPrice,
  sendChatMessage,
  type ChatMessage,
  type PageContext,
  type PageResults,
  type ProductCardData,
} from '../api'
import { useAuth } from '../auth'
import { useChatResults, type ShownResults } from '../chatResults'
import { usePreferredSize, type Size } from '../preferences'
import { onAskChat } from '../askChat'
import HandsomeDan from './HandsomeDan'

const PAGE_TYPES: Record<string, PageContext['page']> = {
  '/': 'home',
  '/products': 'products',
  '/about': 'about',
  '/login': 'login',
  '/signup': 'signup',
}

/** Describe the current page for the agent, e.g. which product "this" is and the shopper's size. */
function pageContext(pathname: string, results: ShownResults | null, size: Size | null): PageContext {
  const productMatch = pathname.match(/^\/products\/([^/]+)$/)
  const ctx: PageContext = productMatch
    ? { path: pathname, page: 'product', product_id: decodeURIComponent(productMatch[1]) }
    : { path: pathname, page: PAGE_TYPES[pathname] ?? 'other' }
  if (ctx.page === 'products' && results) {
    ctx.results_title = results.title
    ctx.results_filters = results.filters
  }
  if (size) ctx.preferred_size = size
  return ctx
}

/** Quick-start chips (Problem 9): what a shopper is likely to ask on this page. */
function starterChips(page: PageContext['page'], hasResults: boolean, size: Size | null): string[] {
  if (page === 'product') {
    return [
      size ? `Is this in stock in ${size}?` : 'What sizes are in stock?',
      'What colors does this come in?',
      'Show me similar items',
      'How much is this?',
    ]
  }
  if (page === 'products' && hasResults) {
    return [size ? `Only show ones in ${size}` : 'Which of these are in stock in M?', 'Which is the cheapest?', 'Any with a bulldog?']
  }
  return ['What hoodies do you have?', 'Gift ideas for a Yale parent', 'Tees under $40', 'Anything with a bulldog?']
}

const greeting = (name?: string): ChatMessage => ({
  role: 'assistant',
  content: name
    ? `Hey ${name}, welcome back! 👋 What are we shopping for today? New hoodie, a gift, something for game day?`
    : "Hey! 👋 I'm the Campus Customs assistant. Think of me as the friend down the hall who knows every hoodie in the shop. What are you looking for?",
})

function ChatProductCard({ product }: { product: ProductCardData }) {
  return (
    <Link to={`/products/${product.product_id}`} className="chat-card">
      <img src={product.image_url} alt={product.name} />
      <div>
        <strong>{product.name}</strong>
        <span className="price">{formatPrice(product.price)}</span>
        <span className="muted">
          {product.sizes_in_stock.length ? `Sizes: ${product.sizes_in_stock.join(', ')}` : 'Sold out'}
        </span>
      </div>
    </Link>
  )
}

export default function ChatWidget() {
  const { user } = useAuth()
  const { results, show } = useChatResults()
  const [preferredSize] = usePreferredSize()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([greeting()])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  // Page the latest reply was given on: its suggestions go stale once the shopper navigates away.
  const [replyPath, setReplyPath] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  // Swap conversations when the shopper logs in or out: saved history for users, fresh chat for guests.
  useEffect(() => {
    if (!user) {
      setMessages([greeting()])
      return
    }
    let cancelled = false
    fetchChatHistory()
      .then((saved) => !cancelled && setMessages([greeting(user.first_name), ...saved]))
      .catch(() => !cancelled && setMessages([greeting(user.first_name)]))
    return () => {
      cancelled = true
    }
  }, [user])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking, open])

  // Buttons elsewhere on the site ("Ask the CC assistant", "Find a look-alike") open the chat with a question.
  const sendRef = useRef<(text: string) => void>(() => {})
  useEffect(
    () =>
      onAskChat((question) => {
        setOpen(true)
        sendRef.current(question)
      }),
    [],
  )

  async function handleClear() {
    if (!user || !window.confirm('Clear your saved chat history? The assistant will forget past conversations.')) return
    try {
      await clearChatHistory()
      setMessages([greeting(user.first_name)])
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: `Couldn't clear history: ${(err as Error).message}` }])
    }
  }

  const onProductPage = /^\/products\/[^/]+$/.test(location.pathname)
  // Page-aware quick starts show whenever the agent hasn't offered its own next steps.
  const last = messages[messages.length - 1]
  const agentOffered =
    last.role === 'assistant' && (last.suggestions?.length ?? 0) > 0 && replyPath === location.pathname
  const starters =
    thinking || agentOffered
      ? []
      : starterChips(pageContext(location.pathname, results, preferredSize).page, !!results, preferredSize)

  /** Put a result set on the Products page (navigating there if needed); the chat stays open. */
  function showOnPage(results: PageResults) {
    show(results)
    if (location.pathname !== '/products') navigate('/products')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    send(input)
  }

  async function send(raw: string) {
    const text = raw.trim()
    if (!text || thinking) return
    // The greeting (index 0) is UI-only and isn't sent as history.
    const history: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setMessages(history)
    setInput('')
    setThinking(true)
    try {
      const reply = await sendChatMessage(history.slice(1), pageContext(location.pathname, results, preferredSize))
      setMessages((m) => [...m, reply])
      setReplyPath(reply.page_results ? '/products' : location.pathname)
      if (reply.page_results) showOnPage(reply.page_results)
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: (err as Error).message || 'Sorry, something went wrong.' }])
    } finally {
      setThinking(false)
    }
  }
  sendRef.current = send

  return (
    <div className="chat-root">
      {open && (
        <section className="chat-panel" aria-label="Campus Customs chat">
          <header className="chat-header">
            <div className="chat-header-id">
              <HandsomeDan size={42} />
              <div>
                <strong>Ask CC</strong>
                <span className="chat-status">{user ? 'AI shop assistant · chat saved' : 'AI shop assistant · online'}</span>
              </div>
            </div>
            <div className="chat-header-actions">
              {user && (
                <button className="chat-clear" onClick={handleClear} title="Clear saved chat history">
                  Clear
                </button>
              )}
              <button className="icon-btn" onClick={() => setOpen(false)} aria-label="Close chat">
                ×
              </button>
            </div>
          </header>
          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={i} className={`chat-turn ${m.role}`}>
                {m.role === 'assistant' && <HandsomeDan size={30} className="chat-avatar" />}
                <div className={`bubble ${m.role}`}>
                  {m.role === 'assistant' ? <Markdown>{m.content}</Markdown> : m.content}
                </div>
                {m.page_results && (
                  <button className="page-results-chip" onClick={() => showOnPage(m.page_results!)}>
                    ▦ {m.page_results.products.length} {m.page_results.title} · show on page
                  </button>
                )}
                {m.products && m.products.length > 0 && (
                  <div className="chat-cards">
                    {m.products.map((p) => (
                      <ChatProductCard key={p.product_id} product={p} />
                    ))}
                  </div>
                )}
                {/* Agent-suggested next steps (Problem 9), only under the latest reply */}
                {i === messages.length - 1 && !thinking && agentOffered && m.suggestions && (
                  <div className="suggestions" aria-label="Suggested replies">
                    {m.suggestions.map((s) => (
                      <button key={s} className="suggestion" onClick={() => send(s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {thinking && (
              <div className="chat-turn assistant">
                <HandsomeDan size={30} className="chat-avatar" />
                <div className="bubble assistant typing" aria-label="Assistant is typing">
                  <span />
                  <span />
                  <span />
                  <em>checking the shelves…</em>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
          {starters.length > 0 && (
            <div className="starters" aria-label="Quick questions">
              <span className="starters-label">Try</span>
              {starters.map((s) => (
                <button key={s} className="suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
          <form className="chat-input" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={onProductPage ? 'Ask about this item…' : 'Ask about products…'}
              aria-label="Message"
              maxLength={1000}
              autoFocus
            />
            <button type="submit" disabled={!input.trim() || thinking}>
              Send
            </button>
          </form>
          <p className="chat-disclaimer">AI assistant · prices &amp; stock come live from the CC inventory</p>
        </section>
      )}
      <button
        className={`chat-toggle ${open ? 'is-open' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Close chat' : 'Open chat'}
      >
        {open ? (
          '×'
        ) : (
          <>
            <HandsomeDan size={44} />
            <span className="pulse" />
            Ask CC
          </>
        )}
      </button>
    </div>
  )
}
