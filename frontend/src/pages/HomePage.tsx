import { Link } from 'react-router-dom'

export function HomePage() {
  return (
    <main className="foundation-shell">
      <section className="foundation-content" aria-labelledby="page-title">
        <div className="foundation-mark" aria-hidden="true">
          AI
        </div>
        <h1 id="page-title">AI Job Simulator</h1>
        <p>AI-powered workplace simulation and adaptive learning platform.</p>
        <div className="foundation-status">Project foundation ready</div>
        <div className="foundation-actions">
          <Link className="auth-link-button" to="/login">Sign in</Link>
          <Link className="auth-link-button auth-link-button-muted" to="/signup">Create account</Link>
        </div>
      </section>
    </main>
  )
}