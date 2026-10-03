// Frontend: the route wrapper around every /edit page, which sends a
// signed-out browser through the Cloudflare Access login before the first save
// rather than after it.
//
// Access gates /edit and /api/edit, but only a document load ever reaches it:
// a click from 食譜 to 設定 changes the page without one, so the page opens
// unchallenged and its first write - a background request - is the first thing
// Access sees. That request cannot follow the login redirect (api/session.js
// says why), and failed as a bare "Failed to fetch".
//
// So on entering the edit pages this asks the session probe, and when Access
// answers with a redirect it sends the whole window through the login and back
// to the same page. That happens as the page opens, before anything has been
// typed into it.
//
// This is not a route guard. It renders its page whatever the answer, hides
// nothing and refuses nothing; the gate is Access, in front of the box, and
// a browser that ignored this component would still be refused every write.
import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { checkEditSession, goSignIn } from '../../api/session'

export default function EditSignIn() {
  const { pathname, search } = useLocation()

  // On every edit page opened, not only the first: a session that ran out
  // while on 設定 is caught on the way into 圖片, before anything is typed
  // there. A session that runs out on an open page is what the save's own
  // error covers (api/client.js SIGN_IN_MESSAGE).
  useEffect(() => {
    let cancelled = false
    checkEditSession().then((state) => {
      if (!cancelled && state === 'signed-out') goSignIn(`${pathname}${search}`)
    })
    return () => {
      cancelled = true
    }
  }, [pathname, search])

  return <Outlet />
}
