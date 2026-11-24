import { Link } from 'react-router-dom'
import { Button } from '../components/ui/index.jsx'

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center text-center p-6">
      <div className="text-6xl font-display font-extrabold text-navy-200">404</div>
      <h1 className="mt-2 text-2xl font-bold">Page not found</h1>
      <Button as={Link} to="/" className="mt-6">Back home</Button>
    </div>
  )
}
