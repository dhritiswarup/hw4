import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'
import { CATEGORIES, categoryOf } from '../categories'
import { useChatResults } from '../chatResults'
import HandsomeDan from '../components/HandsomeDan'
import ProductCard from '../components/ProductCard'
import { SIZES, usePreferredSize, type Size } from '../preferences'

type SortKey = 'featured' | 'price-asc' | 'price-desc' | 'name'
const SORTS: { key: SortKey; label: string }[] = [
  { key: 'featured', label: 'Featured' },
  { key: 'price-asc', label: 'Price: low to high' },
  { key: 'price-desc', label: 'Price: high to low' },
  { key: 'name', label: 'Name A–Z' },
]

/** Apply the "My size" filter and the sort to any product list (catalogue or chat results). */
function arrange(list: Product[], size: Size | null, sort: SortKey): Product[] {
  const inSize = size ? list.filter((p) => p.sizes_in_stock?.includes(size)) : list
  const sorted = [...inSize]
  if (sort === 'price-asc') sorted.sort((a, b) => a.price - b.price || a.name.localeCompare(b.name))
  if (sort === 'price-desc') sorted.sort((a, b) => b.price - a.price || a.name.localeCompare(b.name))
  if (sort === 'name') sorted.sort((a, b) => a.name.localeCompare(b.name))
  return sorted
}

function CountLine({ shown, total, size }: { shown: number; total: number; size: Size | null }) {
  return (
    <p className="muted small">
      {size ? `${shown} of ${total} items in stock in ${size}` : `${total} items`}
    </p>
  )
}

export default function Products() {
  const { results, clear } = useChatResults()
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()
  const categoryParam = params.get('category')
  const [category, setCategory] = useState(
    CATEGORIES.some((c) => c.label === categoryParam) ? categoryParam! : 'All',
  )
  const [query, setQuery] = useState('')

  // Home tiles / footer links arrive as /products?category=Hoodies.
  useEffect(() => {
    if (categoryParam && CATEGORIES.some((c) => c.label === categoryParam)) {
      setCategory(categoryParam)
      clear()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryParam])
  const [size, setSize] = usePreferredSize()
  const [sort, setSort] = useState<SortKey>('featured')

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch((e: Error) => setError(e.message))
  }, [])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (products ?? []).filter((p) => {
      if (category !== 'All' && categoryOf(p) !== category) return false
      if (!q) return true
      return [p.name, p.description, ...p.colors, ...p.search_tags].some((s) => s.toLowerCase().includes(q))
    })
  }, [products, category, query])
  const shownCatalogue = useMemo(() => arrange(visible, size, sort), [visible, size, sort])
  const shownResults = useMemo(() => (results ? arrange(results.products, size, sort) : []), [results, size, sort])

  // Using the page's own filters hands control back from the chat results to the full catalogue.
  function pickCategory(c: string) {
    clear()
    setCategory(c)
    setParams(c === 'All' ? {} : { category: c }, { replace: true })
  }
  function typeQuery(q: string) {
    clear()
    setQuery(q)
  }

  return (
    <>
      <div className="section-head">
        <div>
          <p className="eyebrow">The Campus Customs shop</p>
          <h1>{category === 'All' || results ? 'Shop all' : category}</h1>
          <p className="muted">Hoodies, crewnecks, tees and more, all in Bulldog blue (and then some).</p>
        </div>
        <input
          className="search"
          type="search"
          placeholder="Search e.g. bulldog, hockey, gray"
          value={query}
          onChange={(e) => typeQuery(e.target.value)}
        />
      </div>

      <div className="chips">
        {['All', ...CATEGORIES.map((c) => c.label)].map((c) => (
          <button
            key={c}
            className={`chip ${!results && c === category ? 'active' : ''}`}
            onClick={() => pickCategory(c)}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="toolbar">
        <div className="size-picker" role="group" aria-label="My size">
          <span className="toolbar-label">My size</span>
          <button className={`size-opt ${size === null ? 'active' : ''}`} onClick={() => setSize(null)}>
            Any
          </button>
          {SIZES.map((s) => (
            <button key={s} className={`size-opt ${size === s ? 'active' : ''}`} onClick={() => setSize(s)}>
              {s}
            </button>
          ))}
        </div>
        <label className="sort">
          <span className="toolbar-label">Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort products">
            {SORTS.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {results ? (
        <section className="chat-results" aria-live="polite">
          <div className="chat-results-head">
            <div className="found">
              <HandsomeDan size={64} />
              <div>
              <p className="eyebrow">Fetched by the CC assistant</p>
              <h2>{results.title}</h2>
              <div className="tags">
                {results.filters.map((f) => (
                  <span key={f} className="tag">
                    {f}
                  </span>
                ))}
                <CountLine shown={shownResults.length} total={results.products.length} size={size} />
              </div>
              </div>
            </div>
            <button className="btn btn-ghost" onClick={clear}>
              Show all products
            </button>
          </div>
          {/* key forces a fresh mount (and the fade-in) for every new result set */}
          <div className="product-grid results-grid" key={results.id} data-testid="chat-results-grid">
            {shownResults.map((p, i) => (
              <div key={p.product_id} className="fade-in" style={{ animationDelay: `${Math.min(i, 12) * 40}ms` }}>
                <ProductCard product={p} size={size} />
              </div>
            ))}
          </div>
          {shownResults.length === 0 && (
            <p className="muted">
              None of these are in stock in {size}.{' '}
              <button className="link-btn" onClick={() => setSize(null)}>
                Show all sizes
              </button>
            </p>
          )}
        </section>
      ) : (
        <>
          {error && <p className="error">Couldn't load products ({error}). Is the backend running on port 8000?</p>}
          {!products && !error && <p className="muted">Loading products…</p>}
          {products && (
            <>
              <CountLine shown={shownCatalogue.length} total={visible.length} size={size} />
              <div className="product-grid">
                {shownCatalogue.map((p) => (
                  <ProductCard key={p.product_id} product={p} size={size} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </>
  )
}
