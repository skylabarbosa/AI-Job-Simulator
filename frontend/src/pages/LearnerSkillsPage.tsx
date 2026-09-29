import { useEffect, useState } from 'react'
import { CheckCircle2, CircleDashed, Sparkles } from 'lucide-react'

import { Button } from '../components/ui/button'
import { getLearnerSkills, type LearnerSkillsResponse } from '../services/api/learner'

function skillKindLabel(kind: 'competency' | 'concept') {
  return kind === 'competency' ? 'Capability' : 'Topic'
}

export function LearnerSkillsPage() {
  const [response, setResponse] = useState<LearnerSkillsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let cancelled = false

    void getLearnerSkills()
      .then((data) => {
        if (!cancelled) setResponse(data)
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : 'Unable to load learner skills.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [retryCount])

  return (
    <main className="learner-dashboard">
      <div className="learner-decor learner-decor-one" aria-hidden="true" />
      <div className="learner-decor learner-decor-two" aria-hidden="true" />
      <div className="learner-dashboard-inner">
        <section className="learner-welcome" aria-labelledby="learner-skills-title">
          <div>
            <div className="learner-eyebrow">Learner skills</div>
            <h1 id="learner-skills-title">Skills</h1>
            <p>Review the capabilities your work has demonstrated across the projects and tasks you have completed.</p>
          </div>
        </section>

        {error && (
          <div className="learner-alert" role="alert">
            <p>Your skills couldn’t be loaded.</p>
            <Button variant="outline" onClick={() => { setLoading(true); setError(null); setResponse(null); setRetryCount((count) => count + 1) }}>Retry</Button>
          </div>
        )}
        {loading && (
          <div className="learner-loading" aria-live="polite" aria-label="Loading your skills">
            <p>Gathering your demonstrated skills...</p>
            <div className="learner-skeleton learner-skeleton-project" aria-hidden="true" />
          </div>
        )}

        {!loading && !error && response && (
          <section className="learner-section" aria-labelledby="skills-overview-heading">
            <div className="learner-section-heading">
              <div>
                <div className="learner-eyebrow">Overview</div>
                <h2 id="skills-overview-heading">Skill summary</h2>
              </div>
            </div>
            <div className="learner-metric-grid">
              <article className="learner-metric-card">
                <span className="learner-metric-label">Total skills</span>
                <strong>{response.totals.total_skills}</strong>
              </article>
              <article className="learner-metric-card">
                <span className="learner-metric-label">Demonstrated</span>
                <strong>{response.totals.demonstrated_skills}</strong>
              </article>
              <article className="learner-metric-card">
                <span className="learner-metric-label">Average score</span>
                <strong>{response.totals.average_score}%</strong>
              </article>
            </div>

            {response.skills.length ? (
              <>
                {response.skills.filter((skill) => skill.demonstrated).sort((a, b) => b.score - a.score).slice(0, 1).map((skill) => (
                  <article className="learner-featured-skill" key={`${skill.kind}-${skill.id}`}>
                    <div className="learner-skill-heading"><span>Featured demonstrated skill</span><CheckCircle2 size={18} aria-label="Demonstrated" /></div>
                    <div className="learner-skill-heading">
                      <h3>{skill.name}</h3>
                      <strong className="learner-featured-score">{skill.score}%</strong>
                    </div>
                    <div className="learner-progress-track" role="progressbar" aria-label={`${skill.name} progress`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={skill.score}><span style={{ width: `${Math.min(100, Math.max(0, skill.score))}%` }} /></div>
                    {skill.evidence_count !== undefined && <p>{skill.evidence_count} {skill.evidence_count === 1 ? 'piece' : 'pieces'} of task evidence</p>}
                  </article>
                ))}
                <div className="learner-skills-list" aria-label="Other skills">
                  {response.skills.filter((skill) => !skill.demonstrated || skill.id !== response.skills.filter((item) => item.demonstrated).sort((a, b) => b.score - a.score)[0]?.id).map((skill) => (
                    <div className="learner-skill-row" key={`${skill.kind}-${skill.id}`}>
                      <div className="learner-skill-heading"><span>{skill.name}</span><strong>{skill.score}%</strong></div>
                      <div className="learner-progress-track" role="progressbar" aria-label={`${skill.name} progress`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={skill.score}><span style={{ width: `${Math.min(100, Math.max(0, skill.score))}%` }} /></div>
                      <div className="learner-project-tags">
                        <span>{skillKindLabel(skill.kind)}</span>
                        <span>{skill.demonstrated ? <><CheckCircle2 size={13} aria-hidden="true" /> Demonstrated</> : <><CircleDashed size={13} aria-hidden="true" /> Not yet demonstrated</>}</span>
                        {skill.evidence_count !== undefined && <span>{skill.evidence_count} evidence {skill.evidence_count === 1 ? 'item' : 'items'}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="learner-empty-state">
                <span className="learner-empty-icon"><Sparkles size={20} aria-hidden="true" /></span>
                <p>No skill evidence has been recorded yet. Start a task from Projects to demonstrate a capability.</p>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  )
}
