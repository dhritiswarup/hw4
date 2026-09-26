import { useEffect } from 'react'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import ChatWidget from './components/ChatWidget'
import HandsomeDan from './components/HandsomeDan'
import Navbar from './components/Navbar'
import About from './pages/About'
import Home from './pages/Home'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import ProductPage from './pages/ProductPage'
import Products from './pages/Products'
import Signup from './pages/Signup'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Navbar />
      <main className="page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductPage />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <HandsomeDan size={54} />
            <div>
              <strong>Campus Customs</strong>
              <p>Officially licensed Yale apparel, made to be worn from first-year move-in to your fifth reunion.</p>
            </div>
          </div>
          <div>
            <h4>Shop</h4>
            <Link to="/products?category=Hoodies">Hoodies</Link>
            <Link to="/products?category=Crewnecks">Crewnecks</Link>
            <Link to="/products?category=T-shirts">T-shirts</Link>
            <Link to="/products?category=Quarter-zips">Quarter-zips</Link>
            <Link to="/products?category=Jackets">Jackets</Link>
          </div>
          <div>
            <h4>Campus Customs</h4>
            <Link to="/about">Our story</Link>
            <Link to="/login">Log in</Link>
            <Link to="/signup">Create account</Link>
          </div>
          <div>
            <h4>Visit</h4>
            <p style={{ margin: 0 }}>
              57 Broadway
              <br />
              New Haven, CT 06511
            </p>
          </div>
        </div>
        <div className="footer-bottom">© {new Date().getFullYear()} Campus Customs · Boola Boola, Bulldogs.</div>
      </footer>
      <ChatWidget />
    </>
  )
}
