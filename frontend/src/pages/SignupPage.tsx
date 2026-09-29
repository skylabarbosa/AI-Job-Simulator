import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Eye, EyeOff, Lock, Mail, User } from 'lucide-react'

import { Button } from '../components/ui/button'
import { type AppRole } from '../auth/context'
import { useAuth } from '../auth/useAuth'
import { AuthBrandPanel, RoleSelector } from './LoginPage'

type SignupRole = Exclude<AppRole, 'admin'>

const roleJourney: Record<SignupRole, { heading: string; steps: string[] }> = {
  learner: {
    heading: 'Your learning path',
    steps: ['Pick a project', 'Do real tasks', 'Build skills'],
  },
  business: {
    heading: 'Your project flow',
    steps: ['Pick a project', 'Do real tasks', 'Build skills'],
  },
}

export function SignupPage() {
  const { signUp, clearError } = useAuth()
  const navigate = useNavigate()
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<SignupRole>('learner')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [confirmationRequired, setConfirmationRequired] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const journey = roleJourney[role]

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    clearError()
    setFormError(null)
    setSubmitting(true)
    try {
      const needsConfirmation = await signUp(email, password, displayName, role)
      if (needsConfirmation) { setConfirmationRequired(true) }
      else { navigate('/app', { replace: true }) }
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Unable to create your account.')
    } finally {
      setSubmitting(false)
    }
  }

  /* Email confirmation screen */
  if (confirmationRequired) {
    return (
      <main className="su-shell">
        <AuthBrandPanel />
        <section className="su-form-panel" aria-labelledby="confirm-title">
          <div className="su-form-panel__leaf" aria-hidden="true" />
          <div className="su-form-panel__inner">
            <Link to="/" className="su-form__logo-link" aria-label="SkillUp home">
              <img src="/assets/brand/skillup-logo.png" alt="SkillUp" className="su-form__logo" />
            </Link>
            <h1 id="confirm-title" className="su-form__heading">Check your email</h1>
            <p className="su-form__sub">Confirm your email address, then return here to sign in.</p>
            <Link className="su-submit su-submit--link" to="/login">Continue to sign in</Link>
          </div>
        </section>
      </main>
    )
  }

  return (
    <main className="su-shell su-shell--signup">
      <AuthBrandPanel />

      <section className="su-form-panel su-form-panel--signup" aria-labelledby="signup-title">
        <div className="su-form-panel__leaf" aria-hidden="true" />

        <div className="su-form-panel__inner">
          <Link to="/" className="su-form__logo-link" aria-label="SkillUp home">
            <img src="/assets/brand/skillup-logo.png" alt="SkillUp" className="su-form__logo" />
          </Link>
          <h1 id="signup-title" className="su-form__heading">Create your account</h1>
          <p className="su-form__sub">Pick your path and start in minutes.</p>

          <RoleSelector value={role} onChange={setRole} signup />

          {/* Journey steps box */}
          <aside className="su-journey" aria-live="polite">
            <p className="su-journey__eyebrow">After you join</p>
            <strong className="su-journey__heading">{journey.heading}</strong>
            <ol className="su-journey__steps">
              {journey.steps.map((step, i) => (
                <li key={step} className="su-journey__step">
                  <span className="su-journey__num">{i + 1}</span>
                  {step}
                </li>
              ))}
            </ol>
          </aside>

          <form className="su-form" onSubmit={handleSubmit} noValidate>
            <div className="su-field">
              <label htmlFor="signup-name" className="su-field__label">Name</label>
              <div className="su-field__wrap">
                <User className="su-field__icon" size={15} />
                <input
                  id="signup-name"
                  className="su-field__input"
                  placeholder="Enter your name"
                  autoComplete="name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="su-field">
              <label htmlFor="signup-email" className="su-field__label">Email address</label>
              <div className="su-field__wrap">
                <Mail className="su-field__icon" size={15} />
                <input
                  id="signup-email"
                  type="email"
                  className="su-field__input"
                  placeholder="Enter your email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="su-field">
              <label htmlFor="signup-password" className="su-field__label">Password</label>
              <div className="su-field__wrap">
                <Lock className="su-field__icon" size={15} />
                <input
                  id="signup-password"
                  type={showPassword ? 'text' : 'password'}
                  className="su-field__input su-field__input--pw"
                  placeholder="Create a password"
                  autoComplete="new-password"
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  aria-describedby="signup-pw-hint"
                />
                <button
                  type="button"
                  className="su-field__eye"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <span id="signup-pw-hint" className="su-field__hint">At least 8 characters.</span>
            </div>

            {formError && <p className="su-error" role="alert">{formError}</p>}

            <Button className="su-submit" type="submit" disabled={submitting}>
              {submitting ? 'Creating account…' : <> Create account <ArrowRight size={16} /> </>}
            </Button>
          </form>

          <p className="su-switch">
            Already have an account?{' '}
            <Link to="/login" className="su-switch__link">Sign in</Link>
          </p>
        </div>
      </section>
    </main>
  )
}
