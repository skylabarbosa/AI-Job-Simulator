import { Link } from 'react-router-dom'

export function UnauthorizedPage() {
  return (
    <main className="auth-shell unauthorized-shell">
      <section className="auth-panel unauthorized-panel" aria-labelledby="unauthorized-title">
        <div className="unauthorized-mark" aria-hidden="true">!</div>
        <div className="auth-eyebrow">Access boundary</div>
        <h1 id="unauthorized-title">That workspace is restricted</h1>
        <p className="auth-lede">Your account is signed in, but its role does not include this route.</p>
        <Link className="auth-link-button" to="/app">Return to workspace</Link>
      </section>
    </main>
  )
}
