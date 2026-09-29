import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, BriefcaseBusiness, GraduationCap, Lock, Mail, Eye, EyeOff } from 'lucide-react'

import { Button } from '../components/ui/button'
import { type AppRole } from '../auth/context'
import { useAuth } from '../auth/useAuth'
import { loginRoleMismatchMessage } from '../auth/profileResolution'

type AuthRole = Exclude<AppRole, 'admin'>

const roleDetails: Record<AuthRole, { label: string; description: string; icon: typeof GraduationCap }> = {
  learner: { label: 'Learner', description: 'Build skills with real projects', icon: GraduationCap },
  business: { label: 'Business', description: 'Post projects, find talent', icon: BriefcaseBusiness },
}

/* ── Shared brand panel (reused by both pages) ─────────────────────────── */
export function AuthBrandPanel() {
  return (
    <section className="su-brand" aria-label="About SkillUp">
      <div className="su-brand__overlay" aria-hidden="true" />
      <div className="su-brand__content">
        <Link to="/" className="su-brand__logo-link" aria-label="SkillUp home">
          <span className="su-brand__logo-plate">
            <img src="/assets/brand/skillup-logo.png" alt="SkillUp" className="su-brand__logo-img" />
          </span>
        </Link>
        <p className="su-brand__eyebrow">LEARN BY DOING</p>
        <h2 className="su-brand__heading">
          Build your<br />brighter future.
        </h2>
        <p className="su-brand__sub">
          Work on real projects, get expert feedback, and build a portfolio that gets you noticed.
        </p>
        <div className="su-brand__pills" aria-hidden="true">
          <span>Real projects</span>
          <span>Expert feedback</span>
          <span>Career-ready portfolio</span>
        </div>
      </div>
    </section>
  )
}

/* ── Role selector (shared) ────────────────────────────────────────────── */
export function RoleSelector({
  value,
  onChange,
  signup = false,
}: {
  value: AuthRole
  onChange: (role: AuthRole) => void
  signup?: boolean
}) {
  return (
    <div className="su-roles" role="radiogroup" aria-label="Account type">
      {(Object.keys(roleDetails) as AuthRole[]).map((r) => {
        const d = roleDetails[r]
        const Icon = d.icon
        const desc = signup
          ? r === 'learner'
            ? 'Build skills with real projects'
            : 'Post projects, find talent'
          : d.description
        return (
          <button
            key={r}
            className={`su-role${value === r ? ' su-role--active' : ''}`}
            type="button"
            role="radio"
            aria-checked={value === r}
            onClick={() => onChange(r)}
          >
            <span className="su-role__icon"><Icon size={16} /></span>
            <span className="su-role__text">
              <strong>{d.label}</strong>
              <small>{desc}</small>
            </span>
          </button>
        )
      })}
    </div>
  )
}

/* ── Login page ─────────────────────────────────────────────────────────── */
export function LoginPage() {
  const { signIn, signOut, error, clearError } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<AuthRole>('learner')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const from = (location.state as { from?: string } | null)?.from ?? '/app'

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    clearError()
    setFormError(null)
    setSubmitting(true)
    try {
      const profile = await signIn(email, password)
      const mismatch = loginRoleMismatchMessage(role, profile.role)
      if (mismatch) { await signOut(); setFormError(mismatch); return }
      navigate(from, { replace: true })
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Unable to sign in.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="su-shell su-shell--login">
      <AuthBrandPanel />

      <section className="su-form-panel" aria-labelledby="login-title">
        {/* leaf accent */}
        <div className="su-form-panel__leaf" aria-hidden="true" />

        <div className="su-form-panel__inner">
          <Link to="/" className="su-form__logo-link" aria-label="SkillUp home">
            <img src="/assets/brand/skillup-logo.png" alt="SkillUp" className="su-form__logo" />
          </Link>
          <h1 id="login-title" className="su-form__heading">Welcome back!</h1>
          <p className="su-form__sub">
            Pick up where you left off.
          </p>

          <RoleSelector value={role} onChange={(r) => { setRole(r); setFormError(null) }} />

          <form className="su-form" onSubmit={handleSubmit} noValidate>
            <div className="su-field">
              <label htmlFor="login-email" className="su-field__label">
                {role === 'learner' ? 'Email address' : 'Business email'}
              </label>
              <div className="su-field__wrap">
                <Mail className="su-field__icon" size={15} />
                <input
                  id="login-email"
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
              <div className="su-field__label-row">
                <label htmlFor="login-password" className="su-field__label">Password</label>
                {role === 'learner' && (
                  <button type="button" className="su-forgot">Forgot password?</button>
                )}
              </div>
              <div className="su-field__wrap">
                <Lock className="su-field__icon" size={15} />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  className="su-field__input su-field__input--pw"
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
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
            </div>

            {(formError || error) && (
              <p className="su-error" role="alert">{formError ?? error}</p>
            )}

            <Button className="su-submit" type="submit" disabled={submitting}>
              {submitting ? 'Signing in…' : <> Log In <ArrowRight size={16} /> </>}
            </Button>
          </form>

          <p className="su-switch">
            Don't have an account?{' '}
            <Link to="/signup" className="su-switch__link">Sign up</Link>
          </p>
        </div>
      </section>
    </main>
  )
}
