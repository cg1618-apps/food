// Frontend: a redirect that carries the route's params and query string.
//
// The first routes were /library/ingredient, /ingredient/:id and
// /edit/vocabularies. Bookmarks to them - a category filter included - must
// land on the page that replaced them, so the redirect rewrites the path and
// keeps `?category=...` rather than dropping it as a bare <Navigate> does.
// `to` is a function of the matched params.
import { Navigate, useLocation, useParams } from 'react-router-dom'

export default function Redirect({ to }) {
  const params = useParams()
  const { search, hash } = useLocation()
  return <Navigate to={`${to(params)}${search}${hash}`} replace />
}
