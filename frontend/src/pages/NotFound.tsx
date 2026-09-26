import { Link } from 'react-router-dom'
import HandsomeDan from '../components/HandsomeDan'

export default function NotFound() {
  return (
    <div className="empty">
      <HandsomeDan size={140} animated />
      <h1>Page not found</h1>
      <p className="muted">This page wandered off like a bulldog on Cross Campus.</p>
      <Link to="/" className="btn">
        Go home
      </Link>
    </div>
  )
}
