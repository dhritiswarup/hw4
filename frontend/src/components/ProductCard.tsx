import { Link } from 'react-router-dom'
import { formatPrice, shortDescription, type Product } from '../api'
import { SIZES } from '../preferences'

const LOW_STOCK = 5
const FEW_LEFT_TOTAL = 30

/** `size` = the shopper's "My size" filter; when set, the card shows stock for that size. */
export default function ProductCard({ product, size }: { product: Product; size?: string | null }) {
  const qty = size ? (product.size_stock?.[size] ?? 0) : null
  const inStock = new Set(product.sizes_in_stock ?? [])
  const badge =
    product.total_stock > 0 && product.total_stock <= FEW_LEFT_TOTAL
      ? { text: 'Few left', warn: true }
      : /harvard|the game/i.test(product.name)
        ? { text: 'The Game', warn: false }
        : null

  return (
    <Link to={`/products/${product.product_id}`} className="product-card">
      <div className="product-card-img">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        {badge && <span className={`card-badge ${badge.warn ? 'warn' : ''}`}>{badge.text}</span>}
        <span className="card-view">View details</span>
      </div>
      <div className="product-card-body">
        <p className="product-card-type">{product.garment_type}</p>
        <h3>{product.name}</h3>
        <p className="price">{formatPrice(product.price)}</p>
        {qty !== null && (
          <p className={`size-stock ${qty <= LOW_STOCK ? 'low' : ''}`}>
            {qty === 0 ? `Sold out in ${size}` : qty <= LOW_STOCK ? `Only ${qty} left in ${size}` : `${size} in stock`}
          </p>
        )}
        <div className="size-dots" aria-label={`Sizes in stock: ${[...inStock].join(', ') || 'none'}`}>
          {SIZES.map((s) => (
            <span key={s} className={`${inStock.has(s) ? '' : 'out'} ${s === size ? 'mine' : ''}`}>
              {s}
            </span>
          ))}
        </div>
        <p className="muted">{shortDescription(product.description)}</p>
      </div>
    </Link>
  )
}
