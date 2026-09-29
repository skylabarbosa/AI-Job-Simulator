import type { CSSProperties, HTMLAttributes, ReactNode } from 'react'

import { cn } from 'cn'

interface ContainerProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export function Container({ className, children, ...props }: ContainerProps) {
  return <div className={cn('ui-container', className)} {...props}>{children}</div>
}

interface PageHeaderProps extends HTMLAttributes<HTMLElement> {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}

export function PageHeader({ eyebrow, title, description, action, className, ...props }: PageHeaderProps) {
  return (
    <header className={cn('ui-page-header', className)} {...props}>
      <div>
        {eyebrow && <p className="ui-eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="ui-page-header-description">{description}</p>}
      </div>
      {action && <div className="ui-page-header-action">{action}</div>}
    </header>
  )
}

interface LayoutProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export function Grid({ className, children, ...props }: LayoutProps) {
  return <div className={cn('ui-grid', className)} {...props}>{children}</div>
}

export function Stack({ className, children, ...props }: LayoutProps) {
  return <div className={cn('ui-stack', className)} {...props}>{children}</div>
}

export function Surface({ className, children, ...props }: LayoutProps) {
  return <section className={cn('ui-surface', className)} {...props}>{children}</section>
}

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode
  tone?: 'neutral' | 'success' | 'warning' | 'danger'
}

export function Badge({ tone = 'neutral', className, children, ...props }: BadgeProps) {
  return <span className={cn('ui-badge', `ui-badge-${tone}`, className)} {...props}>{children}</span>
}

interface ProgressBarProps extends HTMLAttributes<HTMLDivElement> {
  value: number
  label?: string
}

export function ProgressBar({ value, label = 'Progress', className, ...props }: ProgressBarProps) {
  const safeValue = Math.min(100, Math.max(0, value))
  return (
    <div
      className={cn('ui-progress-bar', className)}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={safeValue}
      {...props}
    >
      <span style={{ width: `${safeValue}%` }} />
    </div>
  )
}

interface ProgressRingProps extends HTMLAttributes<HTMLDivElement> {
  value: number
  label?: string
  size?: 'sm' | 'md' | 'lg'
}

export function ProgressRing({ value, label = 'Progress', size = 'md', className, ...props }: ProgressRingProps) {
  const safeValue = Math.min(100, Math.max(0, value))
  return (
    <div
      className={cn('ui-progress-ring', `ui-progress-ring-${size}`, className)}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={safeValue}
      style={{ '--progress-value': `${safeValue * 3.6}deg` } as CSSProperties}
      {...props}
    >
      <span>{safeValue}%</span>
    </div>
  )
}
