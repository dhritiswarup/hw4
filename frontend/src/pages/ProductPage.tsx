import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchProduct, formatPrice, type ProductDetail } from '../api'
import { useChatResults } from '../chatResults'
import { usePreferredSize } from '../preferences'
import { askChat } from '../askChat'
import HandsomeDan from '../components/HandsomeDan'

export default function ProductPage() {
  const { productId = '' } = useParams()
  const { results } = useChatResults()
  const [preferred] = usePreferredSize()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [size, setSize] = useState<string | null>(null)

  useEffect(() => {
    setProduct(null)
    setError(null)
    setSize(null)
    fetchProduct(productId)
      .then((p) => {
        setProduct(p)
        // Pre-select the shopper's "My size" so its stock shows straight away.
        if (preferred && p.inventory.some((s) => s.size === preferred)) setSize(preferred)
      })
      .catch((e: Error) => setError(e.message))
  }, [productId, preferred])

  if (error) {
    return (
      <div className="empty">
        <h1>Product not found</h1>
        <p className="muted">We couldn't find that item ({error}).</p>
        <Link to="/products" className="btn">
          Back to products
        </Link>
      </div>
    )
  }
  if (!product) return <p className="muted">Loading…</p>

  const selected = product.inventory.find((s) => s.size === size)

  return (
    <>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/products" className="back">
          {results ? `← Back to "${results.title}"` : '← All products'}
        </Link>
        <span>/</span>
        <span>{product.name}</span>
      </nav>
      <div className="detail">
        <div className="detail-img">
          <img src={product.image_url} alt={product.name} />
        </div>
        <div className="detail-info">
          <p className="eyebrow">{product.garment_type}</p>
          <h1>{product.name}</h1>
          <p className="detail-price">{formatPrice(product.price)}</p>
          <p>{product.description}</p>

          <h4>Colors</h4>
          <div className="tags">
            {product.colors.map((c) => (
              <span key={c} className="tag">
                {c}
              </span>
            ))}
          </div>

          <h4>Sizes</h4>
          <div className="sizes">
            {product.inventory.map((s) => (
              <button
                key={s.size}
                className={`size ${size === s.size ? 'active' : ''}`}
                disabled={s.quantity === 0}
                onClick={() => setSize(s.size)}
                title={s.quantity === 0 ? 'Sold out' : `${s.quantity} in stock`}
              >
                {s.size}
              </button>
            ))}
          </div>
          <p className="muted small">
            {selected
              ? selected.quantity === 0
                ? `Sold out in your size (${selected.size}). Ask the assistant for similar items in ${selected.size}.`
                : `${selected.quantity} in stock in size ${selected.size}.`
              : `${product.total_stock} in stock across all sizes. Crossed-out sizes are sold out.`}
          </p>

          <table className="stock-table">
            <thead>
              <tr>
                {product.inventory.map((s) => (
                  <th key={s.size}>{s.size}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {product.inventory.map((s) => (
                  <td key={s.size} className={s.quantity === 0 ? 'sold-out' : ''}>
                    {s.quantity === 0 ? 'Sold out' : s.quantity}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>

          <button
            className="ask-dan"
            onClick={() =>
              askChat(
                selected && selected.quantity === 0
                  ? `Show me similar items in ${selected.size}`
                  : 'Show me similar items',
              )
            }
          >
            <HandsomeDan size={42} />
            <div>
              {selected && selected.quantity === 0 ? `Sold out in ${selected.size}? Find a look-alike` : 'Not quite right?'}
              <span>Ask the CC assistant for similar styles that are in stock.</span>
            </div>
          </button>

          <div className="trust">
            <div>
              <strong>Officially licensed</strong>
              Authentic Yale marks
            </div>
            <div>
              <strong>Live stock</strong>
              Counts straight from our inventory
            </div>
            <div>
              <strong>57 Broadway</strong>
              Try it on in New Haven
            </div>
          </div>

          <h4>Tags</h4>
          <div className="tags">
            {product.search_tags.map((t) => (
              <span key={t} className="tag subtle">
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
