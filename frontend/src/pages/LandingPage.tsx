import { ArrowRight, BarChart3, BookOpen, BriefcaseBusiness, CheckCircle2, ChevronRight, GraduationCap, Layers, MessageSquare, Sparkles, Star, TrendingUp, Users, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'

const features = [
  {
    icon: <BriefcaseBusiness size={22} />,
    title: 'Real-World Projects',
    description: 'Work on authentic workplace challenges sourced directly from businesses, not hypothetical exercises.',
    color: 'feature-card-teal',
  },
  {
    icon: <Sparkles size={22} />,
    title: 'AI-Powered Guidance',
    description: 'Get personalised feedback and intelligent hints tailored to your progress and learning style.',
    color: 'feature-card-blue',
  },
  {
    icon: <BarChart3 size={22} />,
    title: 'Skill Analytics',
    description: 'Track your growth across competencies with detailed progress insights and performance metrics.',
    color: 'feature-card-violet',
  },
  {
    icon: <Users size={22} />,
    title: 'Business Partnership',
    description: 'Businesses publish projects; learners gain real experience. A true two-sided talent marketplace.',
    color: 'feature-card-emerald',
  },
  {
    icon: <BookOpen size={22} />,
    title: 'Adaptive Learning Path',
    description: "Your journey adapts to your pace. Get harder tasks as you improve, with AI scaffolding along the way.",
    color: 'feature-card-amber',
  },
  {
    icon: <TrendingUp size={22} />,
    title: 'Career-Ready Skills',
    description: 'Build a verifiable portfolio of completed work that demonstrates real capability to employers.',
    color: 'feature-card-rose',
  },
]

const steps = [
  {
    step: '01',
    title: 'Choose a project',
    description: 'Browse real workplace challenges published by businesses across industries.',
    icon: <Layers size={20} />,
  },
  {
    step: '02',
    title: 'Complete tasks with AI',
    description: 'Work through structured tasks with intelligent hints and real-time feedback.',
    icon: <Zap size={20} />,
  },
  {
    step: '03',
    title: 'Build your portfolio',
    description: 'Every completed task adds to your verified skill record and career profile.',
    icon: <CheckCircle2 size={20} />,
  },
]

const stats = [
  { label: 'Projects Available', value: '50+' },
  { label: 'Skills Tracked', value: '200+' },
  { label: 'Learner Rating', value: '4.9/5' },
  { label: 'Task Completion Rate', value: '92%' },
]

const testimonials = [
  {
    quote: "SkillUp gave me the hands-on experience I couldn't get from online courses. I landed my first data analyst role within 3 months.",
    name: 'Priya Sharma',
    role: 'Data Analyst, FinTech Co.',
    initials: 'PS',
    color: 'avatar-teal',
  },
  {
    quote: "As a business, we found incredible talent through SkillUp. The quality of work from learners genuinely surprised us.",
    name: 'James Okonkwo',
    role: 'Head of Product, ScaleUp Ltd.',
    initials: 'JO',
    color: 'avatar-blue',
  },
  {
    quote: "The AI feedback is like having a senior colleague review my work 24/7. My confidence has skyrocketed.",
    name: 'Mei-Lin Chen',
    role: 'Marketing Specialist',
    initials: 'ML',
    color: 'avatar-violet',
  },
]

export function LandingPage() {
  return (
    <div className="landing-shell" id="landing-page">
      {/* Nav */}
      <header className="landing-nav" role="banner">
        <div className="landing-nav-inner">
          <Link className="landing-brand" to="/" aria-label="SkillUp home">
            <span className="landing-brand-mark">S</span>
            <span className="landing-brand-name">SkillUp</span>
          </Link>
          <nav className="landing-nav-links" aria-label="Primary navigation">
            <a href="#features" className="landing-nav-link">Features</a>
            <a href="#how-it-works" className="landing-nav-link">How it works</a>
            <a href="#testimonials" className="landing-nav-link">Testimonials</a>
          </nav>
          <div className="landing-nav-actions">
            <Link className="landing-nav-signin" to="/login">Sign in</Link>
            <Link className="landing-nav-cta" to="/signup">Get started free <ArrowRight size={15} /></Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="landing-hero" aria-labelledby="hero-headline">
          <div className="landing-hero-bg" aria-hidden="true">
            <div className="landing-hero-orb landing-hero-orb-1" />
            <div className="landing-hero-orb landing-hero-orb-2" />
            <div className="landing-hero-orb landing-hero-orb-3" />
            <div className="landing-hero-grid" />
          </div>
          <div className="landing-hero-content">
            <div className="landing-hero-inner">
              <div className="landing-hero-badge">
                <Sparkles size={13} />
                <span>AI-Powered Workplace Simulation</span>
              </div>
              <h1 id="hero-headline" className="landing-hero-headline">
                Build real skills.<br />
                <span className="landing-hero-highlight">Land your dream role.</span>
              </h1>
              <p className="landing-hero-sub">
                SkillUp bridges the gap between learning and doing. Practice on authentic business projects,
                get AI-powered feedback, and build a portfolio that proves your capabilities.
              </p>
              <div className="landing-hero-actions">
                <Link className="landing-hero-cta" to="/signup" id="hero-cta">
                  Start learning for free <ArrowRight size={17} />
                </Link>
                <Link className="landing-hero-cta-secondary" to="/signup">
                  <BriefcaseBusiness size={17} />
                  I&apos;m a business
                </Link>
              </div>
              <p className="landing-hero-social-proof">
                <CheckCircle2 size={14} />
                No credit card required &middot; Free forever for learners
              </p>
            </div>

            {/* Hero cards preview */}
            <div className="landing-hero-preview" aria-hidden="true">
              <div className="hero-preview-card hero-preview-card-1">
                <div className="hero-preview-card-header">
                  <span className="hero-preview-dot" />
                  <span>Active Project</span>
                </div>
                <strong>Marketing Analytics Dashboard</strong>
                <div className="hero-preview-progress-wrap">
                  <div className="hero-preview-progress">
                    <span style={{ width: '68%' }} />
                  </div>
                  <span>68%</span>
                </div>
                <div className="hero-preview-tags">
                  <span>SQL</span><span>Data Viz</span><span>Analytics</span>
                </div>
              </div>
              <div className="hero-preview-card hero-preview-card-2">
                <div className="hero-preview-feedback">
                  <MessageSquare size={14} />
                  <span>AI Feedback</span>
                </div>
                <p>&ldquo;Great approach! Your query handles NULL values correctly. Consider adding an index for performance.&rdquo;</p>
                <div className="hero-preview-score">
                  {Array.from({ length: 4 }).map((_, i) => <Star key={i} size={13} fill="currentColor" />)}
                  <Star size={13} />
                  <span>4.0 / 5.0</span>
                </div>
              </div>
              <div className="hero-preview-card hero-preview-card-3">
                <p className="hero-preview-skills-title">Skill progress</p>
                <div className="hero-preview-skills">
                  {[
                    { label: 'SQL', pct: 85 },
                    { label: 'Data Analysis', pct: 72 },
                    { label: 'Visualization', pct: 60 },
                  ].map(({ label, pct }) => (
                    <div className="hero-skill-bar" key={label}>
                      <div className="hero-skill-header"><span>{label}</span><span>{pct}%</span></div>
                      <div className="hero-skill-track"><span style={{ width: `${pct}%` }} /></div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Stats bar */}
        <section className="landing-stats" aria-label="Platform statistics">
          <div className="landing-stats-inner">
            {stats.map(({ label, value }) => (
              <div className="landing-stat" key={label}>
                <strong>{value}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Features */}
        <section className="landing-section" id="features" aria-labelledby="features-heading">
          <div className="landing-section-inner">
            <div className="landing-section-header">
              <div className="landing-eyebrow">Everything you need</div>
              <h2 id="features-heading">A complete learning platform built for the real world</h2>
              <p>SkillUp is a simulation environment where learning meets doing — not just another e-learning tool.</p>
            </div>
            <div className="landing-features-grid">
              {features.map(({ icon, title, description, color }) => (
                <article className={`landing-feature-card ${color}`} key={title}>
                  <span className="landing-feature-icon">{icon}</span>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="landing-section landing-how-section" id="how-it-works" aria-labelledby="how-heading">
          <div className="landing-section-inner">
            <div className="landing-section-header">
              <div className="landing-eyebrow">Simple process</div>
              <h2 id="how-heading">From learner to job-ready in three steps</h2>
              <p>A path designed to keep you in motion — always learning, always building.</p>
            </div>
            <div className="landing-steps">
              {steps.map(({ step, title, description, icon }) => (
                <div className="landing-step" key={step}>
                  <div className="landing-step-icon-wrap">{icon}</div>
                  <div className="landing-step-num">{step}</div>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Dual roles */}
        <section className="landing-section landing-roles-section" aria-labelledby="roles-heading">
          <div className="landing-section-inner">
            <div className="landing-section-header">
              <div className="landing-eyebrow">Two sides, one platform</div>
              <h2 id="roles-heading">For learners and businesses</h2>
            </div>
            <div className="landing-roles-grid">
              <div className="landing-role-card landing-role-learner">
                <div className="landing-role-icon"><GraduationCap size={28} /></div>
                <h3>For Learners</h3>
                <p>Practice on real projects, get AI feedback, and build a portfolio that proves your skills to employers.</p>
                <ul className="landing-role-list">
                  <li><CheckCircle2 size={15} /> Free access to all projects</li>
                  <li><CheckCircle2 size={15} /> AI-powered task feedback</li>
                  <li><CheckCircle2 size={15} /> Skill progress tracking</li>
                  <li><CheckCircle2 size={15} /> Verifiable completion records</li>
                </ul>
                <Link className="landing-role-cta landing-role-cta-learner" to="/signup">
                  Start learning free <ChevronRight size={16} />
                </Link>
              </div>
              <div className="landing-role-card landing-role-business">
                <div className="landing-role-icon"><BriefcaseBusiness size={28} /></div>
                <h3>For Businesses</h3>
                <p>Turn your workplace challenges into structured learning projects and discover talented candidates.</p>
                <ul className="landing-role-list">
                  <li><CheckCircle2 size={15} /> Publish custom projects</li>
                  <li><CheckCircle2 size={15} /> AI-generated project blueprints</li>
                  <li><CheckCircle2 size={15} /> Access to skilled learner pool</li>
                  <li><CheckCircle2 size={15} /> Branded project workspace</li>
                </ul>
                <Link className="landing-role-cta landing-role-cta-business" to="/signup">
                  Publish your project <ChevronRight size={16} />
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Testimonials */}
        <section className="landing-section landing-testimonials-section" id="testimonials" aria-labelledby="testimonials-heading">
          <div className="landing-section-inner">
            <div className="landing-section-header">
              <div className="landing-eyebrow">Real results</div>
              <h2 id="testimonials-heading">What our community says</h2>
              <p>Thousands of learners and businesses already use SkillUp to bridge the talent gap.</p>
            </div>
            <div className="landing-testimonials-grid">
              {testimonials.map(({ quote, name, role, initials, color }) => (
                <blockquote className="landing-testimonial" key={name}>
                  <div className="landing-testimonial-stars" aria-label="5 out of 5 stars">
                    {Array.from({ length: 5 }).map((_, i) => <Star key={i} size={14} fill="currentColor" />)}
                  </div>
                  <p>&ldquo;{quote}&rdquo;</p>
                  <footer>
                    <span className={`landing-testimonial-avatar ${color}`}>{initials}</span>
                    <div>
                      <strong>{name}</strong>
                      <span>{role}</span>
                    </div>
                  </footer>
                </blockquote>
              ))}
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="landing-final-cta" aria-labelledby="final-cta-heading">
          <div className="landing-final-cta-bg" aria-hidden="true">
            <div className="landing-cta-orb-1" />
            <div className="landing-cta-orb-2" />
          </div>
          <div className="landing-final-cta-inner">
            <h2 id="final-cta-heading">Ready to bridge the gap?</h2>
            <p>Join thousands of learners and businesses already building the workforce of tomorrow.</p>
            <div className="landing-hero-actions">
              <Link className="landing-hero-cta" to="/signup" id="bottom-cta">
                Get started for free <ArrowRight size={17} />
              </Link>
              <Link className="landing-hero-cta-secondary landing-cta-light" to="/login">
                Sign in to your account
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="landing-footer" role="contentinfo">
        <div className="landing-footer-inner">
          <div className="landing-footer-top">
            <div className="landing-footer-brand">
              <span className="landing-brand-mark landing-brand-mark-sm">S</span>
              <span className="landing-brand-name">SkillUp</span>
            </div>
            <p>AI-powered workplace simulation &amp; adaptive learning platform.</p>
          </div>
          <div className="landing-footer-links">
            <Link to="/login">Sign in</Link>
            <Link to="/signup">Get started</Link>
            <a href="#features">Features</a>
            <a href="#how-it-works">How it works</a>
            <a href="#testimonials">Testimonials</a>
          </div>
          <p className="landing-footer-legal">&copy; {new Date().getFullYear()} SkillUp. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
