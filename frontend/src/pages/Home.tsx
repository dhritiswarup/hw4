import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'
import { askChat } from '../askChat'
import { categoryOf } from '../categories'
import HandsomeDan from '../components/HandsomeDan'
import ProductCard from '../components/ProductCard'
import Reveal from '../components/Reveal'

const FEATURED_IDS = [
  'basic-hoodie-big-yale',
  'district-vit-hoodie-vintage-bulldog',
  'baseball-left-chest-crewneck',
  '2025-yale-vs-harvard-t-shirt',
]

const CATEGORIES = [
  { label: 'Hoodies', image: 'basic-hoodie-big-yale' },
  { label: 'Crewnecks', image: 'super-heavyweight-crewneck-arched-yale-crest' },
  { label: 'T-shirts', image: 'boola-boola-t-shirt' },
  { label: 'Quarter-zips', image: 'branford-1-4-zip' },
  { label: 'Jackets', image: 'brooks-brothers-bomber-jacket-yale' },
]

const highlights = [
  {
    icon: '🏛',
    title: 'Your college, your colors',
    text: 'From Benjamin Franklin to Trumbull, there is gear for every residential college, so you can rep your house as well as your school.',
  },
  {
    icon: '🏒',
    title: 'Game-day ready',
    text: 'Crew, fencing, hockey, sailing and more. Team-specific pieces for the stands, the practice field, or the long walk back from the Bowl.',
  },
  {
    icon: '🎓',
    title: 'For the whole family',
    text: 'Proud parent? Loyal alum? Cheering from afar? Find something that says "my Bulldog" for everyone who shows up in the cheering section.',
  },
]

export default function Home() {
  const [products, setProducts] = useState<Product[]>([])

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(() => setProducts([]))
  }, [])

  const featured = products.filter((p) => FEATURED_IDS.includes(p.product_id))
  const count = (label: string) => products.filter((p) => categoryOf(p) === label).length

  return (
    <>
      <section className="hero-home">
        <div>
          <p className="eyebrow">New Haven · 57 Broadway</p>
          <h1>
            Wear your <em>Bulldog pride</em> every day of the year.
          </h1>
          <p className="lead">
            Campus Customs has been outfitting Yale students, alumni, and families for decades. We make soft,
            sturdy, officially licensed apparel that looks as good at a Saturday game as in a Monday seminar.
          </p>
          <div className="hero-actions">
            <Link to="/products" className="btn btn-light">
              Shop the collection →
            </Link>
            <button className="btn btn-outline-light" onClick={() => askChat('Help me find a gift for a Yale parent')}>
              Help me find a gift
            </button>
          </div>
          <div className="stats">
            <div className="stat">
              <strong>{products.length || 102}</strong>
              <span>styles in stock</span>
            </div>
            <div className="stat">
              <strong>14</strong>
              <span>residential colleges</span>
            </div>
            <div className="stat">
              <strong>40+</strong>
              <span>years in New Haven</span>
            </div>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <span className="ring" />
          <HandsomeDan size={270} animated />
          <span className="hero-stamp">Handsome Dan approved</span>
        </div>
      </section>

      <section>
        <Reveal>
          <div className="section-head">
            <div>
              <p className="eyebrow">Shop by category</p>
              <h2>Find your fit</h2>
            </div>
            <Link to="/products" className="link">
              Browse everything →
            </Link>
          </div>
          <div className="category-grid">
            {CATEGORIES.map((c) => (
              <Link key={c.label} to={`/products?category=${encodeURIComponent(c.label)}`} className="category-tile">
                <div className="img">
                  <img src={`/media/products/${c.image}.jpg`} alt="" loading="lazy" />
                </div>
                <div className="label">
                  {c.label}
                  {products.length > 0 && <span>{count(c.label)} styles</span>}
                </div>
              </Link>
            ))}
          </div>
        </Reveal>
      </section>

      {featured.length > 0 && (
        <section>
          <Reveal>
            <div className="section-head">
              <div>
                <p className="eyebrow">Campus favorites</p>
                <h2>What Bulldogs are wearing</h2>
              </div>
              <Link to="/products" className="link">
                See all →
              </Link>
            </div>
            <div className="product-grid">
              {featured.map((p) => (
                <ProductCard key={p.product_id} product={p} />
              ))}
            </div>
          </Reveal>
        </section>
      )}

      <section className="highlights">
        {highlights.map((h, i) => (
          <Reveal key={h.title} delay={i * 90}>
            <article className="highlight">
              <div className="icon">{h.icon}</div>
              <h3>{h.title}</h3>
              <p className="muted">{h.text}</p>
            </article>
          </Reveal>
        ))}
      </section>

      <section>
        <Reveal>
          <div className="callout">
            <HandsomeDan size={110} />
            <div>
              <h2>Not sure what to pick?</h2>
              <p className="muted">
                Our chat assistant knows every hoodie, crewneck and tee in the shop, and which sizes are on the
                shelf right now.
              </p>
              <button className="btn" onClick={() => askChat('What would you recommend for a first-year?')}>
                Ask the CC assistant
              </button>
            </div>
          </div>
        </Reveal>
      </section>
    </>
  )
}
