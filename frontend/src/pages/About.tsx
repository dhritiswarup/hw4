import { Link } from 'react-router-dom'
import HandsomeDan from '../components/HandsomeDan'
import Reveal from '../components/Reveal'

const values = [
  {
    title: 'Built to be worn',
    text: 'We pick heavyweight fleece, soft tri-blends and sturdy stitching, so your sweatshirt makes it through finals week and your fifth reunion.',
  },
  {
    title: 'Officially licensed',
    text: 'Every crest, wordmark and bulldog we print is authorized by Yale, so the pride you wear is the real thing.',
  },
  {
    title: 'Rooted in New Haven',
    text: "We're a local shop, a short walk from Old Campus. Our neighbors are also our customers.",
  },
]

export default function About() {
  return (
    <>
      <section className="hero compact">
        <p className="eyebrow">About Us</p>
        <h1>
          A New Haven shop with <span className="accent">deep blue roots</span>.
        </h1>
        <p className="lead">
          More than forty years ago, Campus Customs made its first replica Yale letter sweater. It's still one of
          our best-loved pieces. Since then we've grown into the go-to spot for Bulldog apparel, but the idea
          hasn't changed: make gear people are proud to put on.
        </p>
      </section>

      <section className="about-grid">
        <article>
          <h2>Who we dress</h2>
          <p className="muted">
            First-years picking out their first Yale hoodie. Seniors hunting for a class-year tee. Grad and
            professional students from the Law School to the School of Nursing. Parents, grandparents, siblings,
            and alumni who want to cheer from anywhere. If you love the Bulldogs, you belong here.
          </p>
        </article>
        <article>
          <h2>What we carry</h2>
          <p className="muted">
            Hoodies, crewnecks, quarter-zips, tees and jackets, with collections for every residential college
            and dozens of varsity sports. Our lineup runs from vintage bulldog graphics to clean left-chest
            wordmarks, so there's a look for every style.
          </p>
        </article>
      </section>

      <section className="highlights">
        {values.map((v, i) => (
          <Reveal key={v.title} delay={i * 90}>
            <article className="highlight">
              <h3>{v.title}</h3>
              <p className="muted">{v.text}</p>
            </article>
          </Reveal>
        ))}
      </section>

      <section>
        <Reveal>
          <div className="callout">
            <HandsomeDan size={110} animated />
            <div>
              <h2>Come say hi</h2>
              <p className="muted">57 Broadway, New Haven, CT 06511. Or shop online any time.</p>
              <Link to="/products" className="btn">
                Browse products →
              </Link>
            </div>
          </div>
        </Reveal>
      </section>
    </>
  )
}
