// Getting the browser through the Cloudflare Access login, which this app
// never sees and cannot perform.
//
// Access gates /api/edit (and the /edit pages) in front of the box. A
// signed-out request there is answered with a redirect to Access's login on
// another origin. A top-level navigation follows it and comes back signed in;
// a fetch() cannot - the browser refuses the cross-origin hop and the request
// dies as a bare "Failed to fetch", with no status to explain itself. So
// api/client.js sends every request under /api/edit with `redirect: 'manual'`,
// and turns the `opaqueredirect` that comes back into an error carrying
// `signInRequired`. This file is what the edit pages do about it.
//
// Nothing in this file is a gate. It decides nothing about who may write; it
// only notices that Access has asked for a sign-in and sends the browser where
// Access can ask properly.

import { fetchJson } from './client'
import { endpoints } from './endpoints'

// How long after sending the browser to sign in a second redirect is refused.
// If the probe still fails straight after a sign-in - cookies blocked, a
// mis-set Access policy - another redirect would only loop.
export const SIGN_IN_RETRY_MS = 60_000
const LAST_SIGN_IN_KEY = 'food.signInRedirectAt'

/** Where to send the browser so Access signs it in and the app returns it to `path`. */
export function signInUrl(path) {
  return `${endpoints.session()}?next=${encodeURIComponent(path)}`
}

/** 'signed-in', 'signed-out', or 'unknown' when the probe itself failed. */
export async function checkEditSession() {
  try {
    await fetchJson(endpoints.session())
    return 'signed-in'
  } catch (error) {
    return error?.signInRequired ? 'signed-out' : 'unknown'
  }
}

// Browser storage can be absent or throw (a private window, blocked site
// data); the loop guard then simply does not apply, which errs towards
// letting the person sign in.
function lastSignInAt() {
  try {
    return Number(window.sessionStorage.getItem(LAST_SIGN_IN_KEY)) || 0
  } catch {
    return 0
  }
}

function rememberSignInAt(now) {
  try {
    window.sessionStorage.setItem(LAST_SIGN_IN_KEY, String(now))
  } catch {
    // See lastSignInAt.
  }
}

/**
 * Send the browser through the Access login and back to `path`. Returns false,
 * and does nothing, when it already did so within SIGN_IN_RETRY_MS.
 */
export function goSignIn(path, now = Date.now()) {
  if (now - lastSignInAt() < SIGN_IN_RETRY_MS) return false
  rememberSignInAt(now)
  window.location.assign(signInUrl(path))
  return true
}
