import { FolderKanban } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { buildProjectIllustrationAltText, getProjectIllustrationSource } from './ProjectIllustrationData'

export type ProjectIllustrationProps = {
  projectName: string
  src?: string
  alt?: string
  className?: string
  fallbackIcon?: ReactNode
}

export { getProjectIllustrationSource }

export function ProjectIllustration({
  projectName,
  src,
  alt,
  className,
  fallbackIcon,
}: ProjectIllustrationProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const resolvedAlt = buildProjectIllustrationAltText(projectName, alt)
  const resolvedSrc = src?.trim() ?? ''
  const showFallback = !resolvedSrc || imageFailed

  return (
    <div
      className={showFallback ? `project-illustration project-illustration-fallback ${className ?? ''}`.trim() : `project-illustration ${className ?? ''}`.trim()}
      role={showFallback ? 'img' : undefined}
      aria-label={showFallback ? `${projectName} project illustration` : undefined}
    >
      {showFallback ? (
        <>
          <span className="project-illustration-shell" aria-hidden="true" />
          <span className="project-illustration-icon" aria-hidden="true">{fallbackIcon ?? <FolderKanban size={28} />}</span>
          <span className="project-illustration-name" aria-hidden="true">{projectName}</span>
        </>
      ) : (
        <img
          src={resolvedSrc}
          alt={resolvedAlt}
          loading="lazy"
          onError={() => setImageFailed(true)}
        />
      )}
    </div>
  )
}
