import { useEffect, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import HandsomeDan from './HandsomeDan'

const links = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Shop' },
  { to: '/about', label: 'About Us' },
]

export default function Navbar() {
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <>
      <div className="announce">
        <strong>Officially licensed Yale apparel</strong>
        <span className="announce-more">
          <span className="sep">|</span>
          Visit us at 57 Broadway, New Haven
          <span className="sep">|</span>
          Boola Boola!
        </span>
      </div>
      <header className={`navbar ${scrolled ? 'scrolled' : ''}`}>
        <Link to="/" className="brand" aria-label="Campus Customs home">
          <HandsomeDan size={46} />
          <span className="brand-text">
            <span className="brand-name">Campus Customs</span>
            <span className="brand-sub">Yale · New Haven</span>
          </span>
        </Link>
        <nav className="nav-links">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end}>
              {l.label}
            </NavLink>
          ))}
          {loading ? null : user ? (
            <>
              <span className="nav-user">Hi, {user.first_name}</span>
              <button className="nav-btn" onClick={handleLogout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login">Log in</NavLink>
              <NavLink to="/signup" className="nav-cta">
                <span className="cta-long">Create account</span>
                <span className="cta-short">Sign up</span>
              </NavLink>
            </>
          )}
        </nav>
      </header>
    </>
  )
}
